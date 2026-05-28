# Release Checklist

- Test on Windows 10 and Windows 11.
- Test on a standard user account, not only administrator.
- Confirm `Esc + S` stops the alarm.
- Confirm the app does not trigger during the 5-second arming delay.
- Confirm mouse movement, touchpad movement, click, scroll, and keyboard input trigger the alarm.
- Confirm a second launch does not start a duplicate listener.
- Build with `.\build_windows.ps1`.
- Package with Inno Setup using `installer\PrivacyAlarm.iss`.
- Code-sign `PrivacyAlarm.exe` and the installer.
- Deploy the license server and set `privacy_alarm/product_config.py`.
- Test a paid-license activation against the deployed server.
- Upload the installer to your paid download provider.
- Connect payment webhooks to a license server before public launch.
- Add a privacy policy explaining that key contents are not recorded.
