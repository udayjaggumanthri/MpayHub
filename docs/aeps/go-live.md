# AEPS / Fingpay — Go-live runbook

## Before first money

1. **Super Admin → AEPS → Provider (Simple tab)**
   - Confirm SMID, login, password, `secret_key`
   - Egress IP → email Tapits for whitelist (+ SMID)
   - Sync banks; note `banks_last_synced_at`
   - Activate Simple profile only when credentials complete
2. **Tapits confirmation**
   - IP whitelisted
   - AEPS enabled for SMID / test merchant (clears `10027`)
   - Optional: confirm Simple path for CW/AP OTP > ₹5000
3. **Merchant journey**
   - Entitlement → Onboarding → Device → eKYC → Bank eKYC if FP097 → Daily 2FA
4. **Test txn**
   - CW ≤ ₹5000 → expect bankRRN + `00` → Status check → Ack
   - CW > threshold → Send Aadhaar OTP → capture with otp → submit with `txnOtpRequestId`
5. **Recon**
   - Admin (with grant) → Run outbound recon for yesterday (`POST /aeps/admin/recon/run/` or `python manage.py aeps_recon_push`)
   - Share UAT logs with Tapits → receive **production** recon URL → paste into provider `recon_base_url` / `recon_prod` path
6. **Hardening**
   - Turn **debug_mode off** for broad use
   - Set `callback_token` + `callback_allowed_ips` for webhooks
   - Do not activate encrypted UAT/Prod until password + secret_key + RSA cert are present

## Daily ops

- Cron / timer: `cd backend && ./venv/bin/python manage.py sync_aeps_banks` (both bank lists)
- Cron: `python manage.py aeps_recon_push` (yesterday)

## Settlement

Fingpay settles to the merchant bank account from onboarding (no separate AEPS wallet). Confirm bank credit after first successful money txn before full go-live.
