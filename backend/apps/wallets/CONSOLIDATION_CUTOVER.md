# Wallet Consolidation Cutover Runbook

Single-wallet consolidation: fold `bbps` / `commission` / `profit` into `main`,
settle every service charge into the admin main wallet + `CommissionLedger`,
and remove main→BBPS fund transfer.

## Pre-cutover checklist

1. Take a full database backup (pg_dump or managed snapshot).
2. Enable maintenance mode for **all** modules via Admin → Maintenance.
3. Deploy this release to UAT first; do not skip UAT dry-run.

## UAT dry-run (no money moved)

```bash
cd backend
source venv/bin/activate
python manage.py migrate wallets 0004_wallet_held_balance_and_merge_audit
python manage.py migrate transactions 0008_commission_ledger_revenue_fields
python manage.py migrate transactions 0009_commission_ledger_backfill
python manage.py wallet_merge_dryrun --csv /tmp/wallet_merge_dryrun.csv
```

Sign off the CSV:

- `grand_after` must equal `grand_main + grand_bbps + grand_commission + grand_profit`
- Spot-check 5 users with non-zero BBPS balances

## Production cutover

```bash
# 1. Maintenance ON (all modules)
# 2. Backup DB
# 3. Deploy code
# 4. Migrate (0005 runs the live merge inside one transaction)
python manage.py migrate
python manage.py wallet_reconcile   # MUST exit 0

# 5. Smoke tests
#    - one pay-in (package) → net on main, commission/revenue on upline main
#    - one BBPS bill pay → debit main, fee on admin main + CommissionLedger
#    - one payout with slab charge → fee on admin main + CommissionLedger
#    - confirm /bill-payments/fund-wallet returns redirect / API 410
#    - admin dashboard: Main (own), Distributed Balance, Earnings

# 6. Maintenance OFF
```

## Rollback

```bash
# Reverse data merge only (restores legacy wallet balances from WalletMergeAudit)
python manage.py migrate wallets 0004_wallet_held_balance_and_merge_audit
# Then redeploy previous application build
```

`WalletMergeAudit` rows with `status=merged` are the source of truth for rollback.

## Post-cutover ops

- `python manage.py bbps_release_stale_holds --hours 48` (cron recommended)
- `python manage.py cms_release_stale_holds`
- Revenue report: `/reports/commission` (UI label “Revenue”) and `/api/reports/revenue/`
- Unattributed revenue (admin): `/api/reports/revenue/unattributed/`

## Invariants

- Every user has exactly one live spendable balance: `Wallet(wallet_type='main')`.
- `SUM(all wallet balances) == SUM(main balances)` after merge (legacy rows archived at 0).
- Every customer service charge creates ≥1 `CommissionLedger` row and credits a platform recipient’s main wallet (or an unattributed ledger row if no recipient exists).
- Historical `PassbookEntry` rows with `wallet_type` in `{bbps,commission,profit}` are never rewritten; use Passbook “Include legacy wallets”.
