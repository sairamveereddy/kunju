# Privacy Alarm License Server

This is the small backend needed for paid activation.

## Run Locally

```powershell
cd license_server
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
$env:ADMIN_SECRET = "choose-a-long-secret"
$env:WEBHOOK_SECRET = "choose-another-long-secret"
.\.venv\Scripts\python.exe -m uvicorn server:app --host 0.0.0.0 --port 8000
```

Health check:

```text
http://localhost:8000/health
```

## Create a License Manually

```powershell
$body = @{ email = "buyer@example.com"; provider = "manual"; order_id = "manual-1" } | ConvertTo-Json
Invoke-RestMethod `
  -Method Post `
  -Uri "http://localhost:8000/api/admin/licenses" `
  -Headers @{ "X-Admin-Secret" = "choose-a-long-secret" } `
  -ContentType "application/json" `
  -Body $body
```

## Verify From the App

Set the server URL before building the Windows app:

```python
# privacy_alarm/product_config.py
LICENSE_SERVER_URL = "https://your-domain.com/api/license/verify"
```

Then rebuild:

```powershell
.\build_windows.ps1
```

Buyer activation:

```powershell
PrivacyAlarm.exe --activate PAL-EXAMPLE-LICENSE-KEY
```

## Payment Webhook

Connect your payment provider or automation tool to:

```text
POST /api/webhooks/payment
Header: X-Webhook-Secret: your-secret
Body:
{
  "email": "buyer@example.com",
  "provider": "stripe",
  "order_id": "payment-or-checkout-id"
}
```

The response contains the license key. Your payment automation should email that key to the buyer.
