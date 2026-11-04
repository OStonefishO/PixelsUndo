$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

$python = Join-Path $root ".venv\Scripts\python.exe"
if (-not (Test-Path $python)) { throw "Missing .venv. Run the app once first." }

& $python -m PyInstaller --noconfirm --clean --windowed --name PixelsUndo `
  --icon "$root\web\assets\icon.ico" `
  --add-data "$root\web;web" `
  --add-data "$root\data\samples;data\samples" `
  --hidden-import cv2 `
  --paths "$root" `
  --distpath "$root\dist" `
  --workpath "$root\build" `
  --specpath "$root\build" `
  "$root\desktop.py"

$out = Join-Path $root "dist\PixelsUndo"
if (-not (Test-Path (Join-Path $out "PixelsUndo.exe"))) { throw "Build failed: exe not found." }

$zip = Join-Path $root "PixelsUndo-Windows.zip"
if (Test-Path $zip) { Remove-Item $zip -Force }
Add-Type -AssemblyName System.IO.Compression.FileSystem
[System.IO.Compression.ZipFile]::CreateFromDirectory(
  $out,
  $zip,
  [System.IO.Compression.CompressionLevel]::Optimal,
  $true
)
$check = [System.IO.Compression.ZipFile]::OpenRead($zip)
$hasExe = $check.Entries | Where-Object { ($_.FullName -replace "\\", "/") -eq "PixelsUndo/PixelsUndo.exe" }
$check.Dispose()
if (-not $hasExe) { throw "Zip is missing PixelsUndo.exe." }
Write-Host "Built $zip"
