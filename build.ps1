# Crea l'eseguibile con PyInstaller. Esegui dalla cartella del progetto, con l'ambiente .venv (Python 3.12):
#   powershell -ExecutionPolicy Bypass -File build.ps1            -> cartella dist\WFVendorOverlay (consigliato)
#   powershell -ExecutionPolicy Bypass -File build.ps1 -Console   -> con finestra console (per vedere gli errori)
#   powershell -ExecutionPolicy Bypass -File build.ps1 -OneFile   -> singolo .exe (avvio piu' lento)
param([switch]$Console, [switch]$OneFile)
$ErrorActionPreference = "Stop"
$py = ".venv\Scripts\python.exe"
if (-not (Test-Path $py)) { throw "Ambiente .venv non trovato. Crealo con: py -3.12 -m venv .venv" }

& $py -m pip install --upgrade pyinstaller
Write-Host "Controllo i modelli OCR..."
& $py prepare_models.py

$piArgs = @("--noconfirm", "--clean", "--name", "WFVendorOverlay",
            "--collect-all", "rapidocr", "--collect-all", "onnxruntime",
            "--hidden-import", "pynput.keyboard._win32", "--hidden-import", "pynput.mouse._win32",
            "--add-data", "vendors.json;.")
if ($OneFile) { $piArgs += "--onefile" } else { $piArgs += "--onedir" }
if (-not $Console) { $piArgs += "--noconsole" }
$piArgs += "main.py"

& $py -m PyInstaller @piArgs
Write-Host "Fatto. Eseguibile in: dist\WFVendorOverlay"
