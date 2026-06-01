param(
    [string]$Python = ".\.venv\Scripts\python.exe"
)

$ErrorActionPreference = "Stop"

if (-not (Test-Path -LiteralPath $Python)) {
    throw "Python not found at $Python. Run setup_and_run.bat first."
}

& $Python -m pip install -r requirements-dev.txt
& $Python -m PyInstaller `
    --noconfirm `
    --clean `
    --windowed `
    --name "PrivacyAlarm" `
    --add-data "privacy_alarm\assets\alarm.mp3;privacy_alarm\assets" `
    --add-data "privacy_alarm\assets\alarm.wav;privacy_alarm\assets" `
    --add-data "privacy_alarm\assets\kunju-hero.png;privacy_alarm\assets" `
    --collect-all pynput `
    "privacy_alarm\app.py"

Write-Host "Build complete: dist\PrivacyAlarm\PrivacyAlarm.exe"
