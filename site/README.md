# Kunju Alarm Website

This static website can be hosted on Netlify, Vercel, GitHub Pages, Cloudflare Pages, or any normal static web host.

## Local Preview

From the repository root:

```powershell
cd site
python -m http.server 8080
```

Open:

```text
http://127.0.0.1:8080
```

## Update the Download

1. Rebuild the Windows app.
2. Recreate `dist/PrivacyAlarm-Windows.zip`.
3. Copy the new ZIP to `site/downloads/PrivacyAlarm-Windows.zip`.
4. Update the SHA256 hash in `site/index.html`.

## Payment

Replace the contact/support link in the paid launch section with a Stripe, Gumroad, or Lemon Squeezy checkout URL.
