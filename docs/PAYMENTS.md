# Payments and Licensing

For a paid downloadable Windows app, use a checkout provider to collect payment and issue a license key.

## Recommended MVP Flow

1. Build `PrivacyAlarm.exe` with `build_windows.ps1`.
2. Package it with Inno Setup using `installer/PrivacyAlarm.iss`.
3. Deploy `license_server/server.py` to a host such as Render, Railway, Fly.io, or a VPS.
4. Set `privacy_alarm/product_config.py` to your deployed verify endpoint.
5. Rebuild the Windows app.
6. Sell the installer through Stripe Payment Links, Gumroad, Lemon Squeezy, or another checkout provider.
7. Configure the provider/webhook automation to call `/api/webhooks/payment`.
8. Email the generated key to the buyer.
9. The buyer activates from PowerShell:

```powershell
PrivacyAlarm.exe --activate PAL-CUSTOMER-LICENSE-KEY
```

10. Normal launches show the control window. Hidden mode is available with `--hidden`.

## License Server Hook

The app supports server validation with either `privacy_alarm/product_config.py` before build or this environment variable during development:

```powershell
$env:PRIVACY_ALARM_LICENSE_SERVER = "https://your-domain.com/api/license/verify"
```

Expected request:

```json
{"license_key":"PAL-CUSTOMER-LICENSE-KEY"}
```

Expected response:

```json
{"valid":true}
```

The repo now includes a working starter backend in `license_server/server.py`.

## Product Notes

- The app includes a 7-day local trial.
- Paid activation is stored under `%APPDATA%\SairamPrivacyAlarm\license.json`.
- Logs are stored under `%APPDATA%\SairamPrivacyAlarm\privacy-alarm.log`.
- Code-sign the installer before selling to reduce Windows SmartScreen warnings.
