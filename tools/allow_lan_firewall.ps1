# Allow phones on the same Wi-Fi to reach the local PixelsUndo server.
# Run this once with administrator rights (the .bat next to the project does it).
$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot
$python = Join-Path $root ".venv\Scripts\python.exe"
if (-not (Test-Path $python)) {
    throw "Cannot find $python. Run the PixelsUndo launcher once first."
}

# A venv python.exe is a thin redirector: the process that actually listens may
# be the base interpreter. Allow both so LAN access works either way.
$programs = @($python)
$basePrefix = (& $python -c "import sys; print(sys.base_prefix)").Trim()
$basePython = Join-Path $basePrefix "python.exe"
if ((Test-Path $basePython) -and ($programs -notcontains $basePython)) {
    $programs += $basePython
}

# Clear older PixelsUndo rules, then recreate them for the current interpreters.
Get-NetFirewallRule -DisplayName "PixelsUndo*" -ErrorAction SilentlyContinue |
    Remove-NetFirewallRule -ErrorAction SilentlyContinue

foreach ($program in $programs) {
    $ruleName = "PixelsUndo LAN - " + (Split-Path $program -Leaf) + " - " + $program
    New-NetFirewallRule `
        -DisplayName $ruleName `
        -Direction Inbound `
        -Action Allow `
        -Protocol TCP `
        -LocalPort 8765-8775 `
        -Program $program `
        -Profile Private, Public `
        -Description "PixelsUndo local image studio: allow phone access on the same Wi-Fi." | Out-Null
}

Write-Host ""
Write-Host "PixelsUndo LAN access is now allowed for:" -ForegroundColor Green
$programs | ForEach-Object { Write-Host "  $_" }
Write-Host ""
Write-Host "Connect the phone to the same Wi-Fi and scan the QR code in the app."
Write-Host ""
Start-Sleep -Seconds 4
