# Privacy Alarm

A small Windows privacy alarm app. Run it before you step away. It arms after 5 seconds, then keyboard activity, mouse movement, clicks, scrolls, or touchpad movement will loop the bundled alarm sound until `S` is pressed.

The included alarm sound is packaged at `privacy_alarm/assets/alarm.mp3`.

## Product Shape

- Visible control window
- Optional hidden background runtime
- 5-second arming delay to avoid launch-trigger mistakes
- Keyboard, mouse, scroll, and touchpad movement triggers
- `Esc + S` stops the alarm and exits
- Single-instance protection
- 7-day trial
- License activation command for paid customers
- Starter online license server for paid downloads
- Windows `.exe` build script
- Inno Setup installer script

## Install

Install Python 3.10 or newer from <https://www.python.org/downloads/windows/>.

Then open PowerShell in this folder and run:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python -m privacy_alarm
```

If PowerShell blocks activation scripts, use:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m privacy_alarm
```

Or install it as a command:

```powershell
pip install .
privacy-alarm
```

## How It Works

1. Run `run_privacy_alarm.bat`.
2. Click **Start Protection**.
3. After 5 seconds, keyboard activity or mouse/touchpad movement starts the alarm sound.
4. Press `Esc + S` or click **Stop Protection** to stop the alarm.

## Build a Windows App

```powershell
.\build_windows.ps1
```

The app will be created at:

```text
dist\PrivacyAlarm\PrivacyAlarm.exe
```

To package an installer, install Inno Setup and compile:

```text
installer\PrivacyAlarm.iss
```

## Payment and Activation

The app has a local 7-day trial. Paid users can activate with:

```powershell
PrivacyAlarm.exe --activate PAL-CUSTOMER-LICENSE-KEY
```

See `docs/PAYMENTS.md` for the payment/license-server plan.

The backend lives in:

```text
license_server/
```

## Notes

- Keep the computer awake. No app can run while Windows is fully asleep or powered off.
- Some security tools may warn about keyboard/mouse hooks because this app listens for key presses and pointer movement. This app does not record typed text or send anything anywhere.
- On some Windows setups, running as administrator may be needed for global input hooks to work everywhere.
