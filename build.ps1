# Builds the executable with PyInstaller. Run from the project folder, with the .venv environment (Python 3.12):
#   powershell -ExecutionPolicy Bypass -File build.ps1            -> dist\WFVendorOverlay folder (recommended)
#   powershell -ExecutionPolicy Bypass -File build.ps1 -Console   -> with a console window (to see errors)
#   powershell -ExecutionPolicy Bypass -File build.ps1 -OneFile   -> single .exe (slower startup)
param([switch]$Console, [switch]$OneFile)
$ErrorActionPreference = "Stop"
$py = ".venv\Scripts\python.exe"
if (-not (Test-Path $py)) { throw ".venv environment not found. Create it with: py -3.12 -m venv .venv" }

& $py -m pip install --upgrade pyinstaller
Write-Host "Checking the OCR models..."
& $py prepare_models.py

$piArgs = @("--noconfirm", "--clean", "--name", "WFVendorOverlay",
            "--collect-all", "rapidocr", "--collect-all", "onnxruntime",
            "--hidden-import", "pynput.keyboard._win32", "--hidden-import", "pynput.mouse._win32",
            "--add-data", "vendors.json;.", "--add-data", "gamenames.json;.")
if ($OneFile) { $piArgs += "--onefile" } else { $piArgs += "--onedir" }
if (-not $Console) { $piArgs += "--noconsole" }
$piArgs += "main.py"

& $py -m PyInstaller @piArgs
Write-Host "Done. Executable in: dist\WFVendorOverlay"
