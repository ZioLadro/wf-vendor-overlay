"""Mouse-wheel detection that can never slow the cursor down.

A global mouse hook (what pynput uses) makes Windows wait for this program on EVERY mouse movement of the whole
system: when the program is busy (an OCR scan, a redraw), the cursor lags. Raw Input is different: the system just
queues the events for us and never waits, so the cursor is not affected whatever this program is doing.

WheelListener(callback).start() / .stop(). On Windows it uses Raw Input (a hidden message-only window, in its own
thread); if that cannot be set up (or on other systems) it falls back to pynput.
"""
import sys
import threading

WM_INPUT = 0x00FF
RID_INPUT = 0x10000003
RIM_TYPEMOUSE = 0
RIDEV_INPUTSINK = 0x00000100
RI_MOUSE_WHEEL = 0x0400
RI_MOUSE_HWHEEL = 0x0800
HWND_MESSAGE = -3
WM_QUIT = 0x0012
WM_USER_STOP = 0x0400 + 1


def wheel_flag(button_flags: int) -> bool:
    """True when a raw mouse event carries a (vertical or horizontal) wheel movement."""
    return bool(button_flags & (RI_MOUSE_WHEEL | RI_MOUSE_HWHEEL))


class WheelListener:
    def __init__(self, callback):
        self.callback = callback
        self._thread = None
        self._tid = 0
        self._fallback = None
        self._ready = threading.Event()
        self.mode = ""                      # "rawinput" | "pynput" | "" (not started)

    def start(self):
        if sys.platform == "win32":
            self._thread = threading.Thread(target=self._run, name="wheel-rawinput", daemon=True)
            self._thread.start()
            self._ready.wait(2.0)
            if self.mode == "rawinput":
                return
        self._start_pynput()

    def stop(self):
        if self._fallback is not None:
            try:
                self._fallback.stop()
            except Exception:
                pass
            self._fallback = None
        if self._tid:
            try:
                import ctypes
                ctypes.windll.user32.PostThreadMessageW(self._tid, WM_QUIT, 0, 0)
            except Exception:
                pass

    # ---------- fallback ----------
    def _start_pynput(self):
        try:
            from pynput import mouse
            self._fallback = mouse.Listener(on_scroll=lambda x, y, dx, dy: self.callback())
            self._fallback.start()
            self.mode = "pynput"
        except Exception:
            self.mode = ""

    # ---------- Raw Input (Windows) ----------
    def _run(self):
        try:
            import ctypes
            from ctypes import wintypes

            user32, kernel32 = ctypes.windll.user32, ctypes.windll.kernel32
            LRESULT = ctypes.c_ssize_t
            user32.CreateWindowExW.restype = wintypes.HWND
            user32.CreateWindowExW.argtypes = [
                wintypes.DWORD, wintypes.LPCWSTR, wintypes.LPCWSTR, wintypes.DWORD, ctypes.c_int, ctypes.c_int,
                ctypes.c_int, ctypes.c_int, wintypes.HWND, wintypes.HMENU, wintypes.HINSTANCE, wintypes.LPVOID]
            user32.GetMessageW.argtypes = [ctypes.POINTER(wintypes.MSG), wintypes.HWND, wintypes.UINT, wintypes.UINT]
            user32.DefWindowProcW.restype = LRESULT

            class RAWINPUTDEVICE(ctypes.Structure):
                _fields_ = [("usUsagePage", wintypes.USHORT), ("usUsage", wintypes.USHORT),
                            ("dwFlags", wintypes.DWORD), ("hwndTarget", wintypes.HWND)]

            class RAWINPUTHEADER(ctypes.Structure):
                _fields_ = [("dwType", wintypes.DWORD), ("dwSize", wintypes.DWORD),
                            ("hDevice", wintypes.HANDLE), ("wParam", wintypes.WPARAM)]

            class RAWMOUSE(ctypes.Structure):
                _fields_ = [("usFlags", wintypes.USHORT), ("usReserved", wintypes.USHORT),
                            ("usButtonFlags", wintypes.USHORT), ("usButtonData", wintypes.USHORT),
                            ("ulRawButtons", wintypes.ULONG), ("lLastX", wintypes.LONG),
                            ("lLastY", wintypes.LONG), ("ulExtraInformation", wintypes.ULONG)]

            class RAWINPUT(ctypes.Structure):
                _fields_ = [("header", RAWINPUTHEADER), ("mouse", RAWMOUSE)]

            user32.GetRawInputData.argtypes = [wintypes.HANDLE, wintypes.UINT, wintypes.LPVOID,
                                               ctypes.POINTER(wintypes.UINT), wintypes.UINT]
            user32.GetRawInputData.restype = wintypes.UINT
            user32.RegisterRawInputDevices.argtypes = [ctypes.POINTER(RAWINPUTDEVICE), wintypes.UINT, wintypes.UINT]
            user32.RegisterRawInputDevices.restype = wintypes.BOOL

            # a message-only window: invisible, no desktop presence. "STATIC" is a ready-made window class.
            hwnd = user32.CreateWindowExW(0, "STATIC", "wfvo-wheel", 0, 0, 0, 0, 0,
                                          wintypes.HWND(HWND_MESSAGE), None, None, None)
            if not hwnd:
                raise OSError("CreateWindowEx failed")
            rid = RAWINPUTDEVICE(0x01, 0x02, RIDEV_INPUTSINK, hwnd)      # generic desktop / mouse, also in background
            if not user32.RegisterRawInputDevices(ctypes.byref(rid), 1, ctypes.sizeof(rid)):
                raise OSError("RegisterRawInputDevices failed")

            self._tid = kernel32.GetCurrentThreadId()
            self.mode = "rawinput"
            self._ready.set()

            header_size = ctypes.sizeof(RAWINPUTHEADER)
            msg = wintypes.MSG()
            buf = RAWINPUT()
            while user32.GetMessageW(ctypes.byref(msg), None, 0, 0) > 0:
                if msg.message == WM_INPUT:
                    size = wintypes.UINT(ctypes.sizeof(buf))
                    got = user32.GetRawInputData(wintypes.HANDLE(msg.lParam), RID_INPUT, ctypes.byref(buf),
                                                 ctypes.byref(size), header_size)
                    if got != 0xFFFFFFFF and buf.header.dwType == RIM_TYPEMOUSE and wheel_flag(buf.mouse.usButtonFlags):
                        try:
                            self.callback()
                        except Exception:
                            pass
                else:
                    user32.TranslateMessage(ctypes.byref(msg))
                    user32.DispatchMessageW(ctypes.byref(msg))
            user32.DestroyWindow(hwnd)
        except Exception:
            self.mode = ""
        finally:
            self._tid = 0
            self._ready.set()
