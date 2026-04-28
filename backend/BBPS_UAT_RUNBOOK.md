## Approval-First Governance Rollout

### Publish Sequence (Mandatory)
1. Run sync: `POST /api/bbps/admin/sync-billers/` (or management command flow).
2. Review pending catalog in admin governance console (`Provider-Biller Approval Queue`).
3. Approve required maps/providers (single approve or bulk approve).
4. Verify at least one active commission rule exists per target category.
5. Refresh provider cache: `POST /api/bbps/admin/cache/refresh-providers/`.
6. Validate retailer APIs:
   - `GET /api/bbps/categories/`
   - `GET /api/bbps/providers/<category>/`
   - `GET /api/bbps/billers/<category>/`

### Governance Block Reasons
- `no_rule`: No active commission rule for the category.
- `category_inactive`: Category not approved/active.
- `provider_inactive`: Provider not approved/active.
- `map_inactive`: Mapping not approved/active.
- `biller_status`: Biller status is not ACTIVE/ENABLED/FLUCTUATING.
- `stale`: Biller is stale and stale-blocker is enabled.

### Backfill Existing Data
- Migration `0005_backfill_approval_metadata` auto-labels legacy provider/map rows:
  - active -> `approval_status=approved`
  - inactive -> `approval_status=pending`
- One-time manual command (safe to re-run):
  - `python manage.py backfill_bbps_governance_approval`

### Troubleshooting Approval-First Visibility
- Sync success but no category/provider visible to users:
  - Check governance queue for pending maps.
  - Check `categories_missing_active_rule` in `GET /api/bbps/admin/governance/ops-summary/`.
  - Verify biller status from master is one of ACTIVE/ENABLED/FLUCTUATING.
- Fetch/Pay returns "Service unavailable until admin approval":
  - Inspect response `errors` array for exact blockers.
- Bulk approve returns blocked rows:
  - Resolve `no_rule`, `biller_status`, or `stale` first, then retry.
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
