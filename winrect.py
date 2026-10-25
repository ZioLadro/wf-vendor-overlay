"""Where the Warframe window is (Windows only; ctypes, no extra packages).

The OCR only needs to look at the game window, and only while it is the window you are using."""
import sys

TITLE = "Warframe"
_hwnd = 0


def _user32():
    import ctypes
    return ctypes, ctypes.windll.user32


def _find_window():
    global _hwnd
    ctypes, u = _user32()
    from ctypes import wintypes
    buf = ctypes.create_unicode_buffer(256)

    def is_wf(h):
        return bool(u.IsWindow(h)) and u.IsWindowVisible(h) and u.GetWindowTextW(h, buf, 256) and buf.value == TITLE

    if _hwnd and is_wf(_hwnd):
        return _hwnd
    found = []
    proc = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)(
        lambda h, _l: (found.append(h) if is_wf(h) else None) or True)
    u.EnumWindows(proc, 0)
    _hwnd = found[0] if found else 0
    return _hwnd


def warframe_client_rect(require_foreground=True):
    """(left, top, width, height) of the game's client area in screen pixels, or None if the game is not
    running / minimised / not the foreground window. Only meaningful on Windows."""
    ctypes, u = _user32()
    from ctypes import wintypes
    try:
        u.SetProcessDPIAware()            # physical pixels (harmless if already set)
    except Exception:
        pass
    h = _find_window()
    if not h or u.IsIconic(h):
        return None
    if require_foreground and u.GetForegroundWindow() != h:
        return None
    rc = wintypes.RECT()
    if not u.GetClientRect(h, ctypes.byref(rc)):
        return None
    pt = wintypes.POINT(0, 0)
    u.ClientToScreen(h, ctypes.byref(pt))
    w, hgt = rc.right - rc.left, rc.bottom - rc.top
    return (pt.x, pt.y, w, hgt) if w > 0 and hgt > 0 else None


def capture_region(mon: dict, only_warframe: bool):
    """Part of monitor `mon` to capture: ({"left","top","width","height"}, ox, oy), or None = do not capture.
    ox/oy: offset of the region inside the monitor. Without the option (or off Windows): the whole monitor."""
    whole = ({"left": mon["left"], "top": mon["top"], "width": mon["width"], "height": mon["height"]}, 0, 0)
    if not only_warframe or sys.platform != "win32":
        return whole
    try:
        r = warframe_client_rect()
    except Exception:
        return whole                      # never block scanning because of an API problem
    if r is None:
        return None
    x0, y0 = max(r[0], mon["left"]), max(r[1], mon["top"])
    x1, y1 = min(r[0] + r[2], mon["left"] + mon["width"]), min(r[1] + r[3], mon["top"] + mon["height"])
    if x1 - x0 < 64 or y1 - y0 < 64:
        return None
    return {"left": x0, "top": y0, "width": x1 - x0, "height": y1 - y0}, x0 - mon["left"], y0 - mon["top"]
