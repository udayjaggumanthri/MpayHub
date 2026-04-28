# BBPS UAT Runbook (BillAvenue)

## 1) Prerequisites
- Active BillAvenue config in admin (`base_url`, `access_code`, `institute_id`, secrets).
- At least one enabled `BillAvenueAgentProfile`.
- BillAvenue IP allowlist/entitlement enabled for UAT source IP.
- UAT crypto profile confirmed for PI39:
  - key derivation: `md5`
  - encRequest encoding: `hex`
  - payload format: `xml` (or `json` only if explicitly enabled/validated with BillAvenue).

## 2) Setup sequence
1. Save BillAvenue config and secrets.
   - Set payload format (`api_format`) to your validated variant.
   - Keep safe fallbacks enabled for UAT diagnostics.
2. Save agent profile (channel-mapped agent id).
3. Run `/api/bbps/admin/sync-billers/`.
4. Map provider->biller in governance.
5. Configure commission rules.
6. Pull plans for plan-enabled billers (`/api/bbps/admin/plans/pull/`).

## 3) Readiness checks
- `/api/bbps/admin/integration-health/`
- `/api/bbps/admin/setup-readiness/`
- `/api/bbps/admin/uat-readiness/`

## 4) Retailer validation flow
1. Select category/provider/biller.
2. Fetch bill with MDM schema inputs.
3. Verify quote + charge split.
4. Pay with valid mode/channel pair.
5. Query status with transaction query screen.
6. Register complaint and track complaint ID.

## 5) Failure triage
- `Unauthorized Access Detected` or `Access Denied`:
  - verify source IP allowlist and entitlement with BillAvenue.
- `Invalid ENC request (DE001)`:
  - confirm `crypto_key_derivation=md5` and `enc_request_encoding=hex` for PI39 UAT.
  - verify IV and working key are saved in active config.
- Validation errors:
  - inspect biller MDM snapshot and check mode/channel/device requirements.
- Awaited status:
  - wait 15 minutes before polling status endpoint.

## 6) Go-live blockers
- Missing active config or agent profile.
- No MDM cache or provider mapping gaps.
- Entitlement probe failed.
- High stale/unmapped billers.
