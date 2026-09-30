# Admin profit settlement runbook (prod2)

## Prerequisites
- `PLATFORM_PAYIN_SETTLEMENT_USER_ID=43` in `backend/.env`
- Code deployed (fee_settlement, payin_settlement, BBPS wallet settlement, backfill command)

## Apply
```bash
cd /root/MpayHub/backend && source venv/bin/activate
export DJANGO_SETTINGS_MODULE=config.settings

# 1) Dry-run — expect reclass ~₹68,946.7875 (payin+bbps), bbps_booked=54 / ₹410, unify ~₹38,414.0915
python manage.py backfill_platform_admin_profit --dry-run --csv

# 2) Apply (idempotent; second run should show zeros)
python manage.py backfill_platform_admin_profit --csv

# 3) Reconcile
python manage.py wallet_reconcile

# 4) Spot-check
# - PMLM2026093049826 admin_absorbed → entry_kind=commission on user 43
# - Pre-23 Sep BBPS with charge now has commission row
# - PMPO2026093001954 still service_fee
# - User 43 main ≈ ₹69,366.7875; user 1 main ≈ 0 for moved profit
```

## Rollback
```bash
# Reverses reclass (A) + unify (C). BBPS gap credits (B): clawback_settlement per service_id.
python manage.py backfill_platform_admin_profit --rollback --csv
```

## Frontend
```bash
cd /root/MpayHub/frontend && npm run build
pm2 restart mpayhub-backend mpayhub-frontend
```
