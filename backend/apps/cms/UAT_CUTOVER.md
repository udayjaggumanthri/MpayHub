# Uber CMS — UAT / Prod cutover checklist

## Before UAT

1. Run migrations (`cms`, `core` cms_enabled fields).
2. Seed RBAC: `python manage.py seed_module_permissions` (adds `cms` module).
3. Admin → **CMS → Provider**: set UAT `cms_base_url` (e.g. `https://fpuat.tapits.in`), `super_merchant_id`, `superMerchantSkey`, `secretKey`, activate provider.
4. Share inbound URLs with Tapits:
   - `POST /api/cms/webhooks/fingpay/wallet-check/`
   - `POST /api/cms/webhooks/fingpay/wallet-debit/`
   - `POST /api/cms/webhooks/fingpay/txn-result/`
5. Confirm hash template with Tapits (default `{payload}{secret_key}`). Adjust if their sample uses a trailing `;` on the key.
6. Whitelist Tapits source IPs in provider **Allowed inbound IPs** (or leave empty for open UAT).
7. Ask Tapits to whitelist **our egress IP** for any outbound they require.
8. Maintenance → enable **CMS** module for the portal.
9. Enable CMS for a test Retailer (Admin → CMS Agents → Enable by user id).
10. Fund CMS wallet from Main on that retailer.

## UAT test script

1. Launch CMS from `/cms/launch` — new tab opens Fingpay CMS.
2. Complete a small CDC collection.
3. Confirm Wallet Check / Debit appear in **CMS Audit logs**.
4. Confirm hold → settle (or fail → release) on CMS wallet + Reports receipt.
5. Re-send the same `I` with same `fpTransactionId` — must be idempotent.
6. Run `python manage.py cms_release_stale_holds --hours=1` after planting an old initiated txn.

## Prod cutover

1. Switch provider environment to `prod`, prod base URL (`fpcorp.tapits.in` or as confirmed), prod secrets.
2. Tighten IP allowlist.
3. Turn off debug mode.
4. Schedule `cms_release_stale_holds` (cron/systemd) every hour.
5. Monitor inbound 4xx/hash failures via audit logs.

## Out of scope reminders

- Android SDK not required for web.
- AEPS / BBPS / shared wallet types unchanged.
- CMS ledger is separate; Main wallet is only used for explicit funding transfers.
