# BillAvenue BBPS Rollout Playbook

## Phase 0 - Feature Toggle Preparation
- Keep active config in `mock` mode with `enabled=true`.
- Run DB migrations and verify new admin pages load.
- Validate callback endpoint security controls and replay-safe event storage.

## Phase 1 - UAT
- Create UAT config in BillAvenue settings and store encrypted secrets.
- Run biller sync and verify MDM cache freshness.
- Execute fetch -> validate -> pay matrix for sample billers from UAT CSV fixtures.
- Verify reports/passbook invariants: debit only on success, transaction row created once.

## Phase 2 - Dual Run / Shadow
- Enable live fetch/validate while keeping payment initiation in controlled cohort.
- Compare mocked vs live payload outcomes in audit logs.
- Reconcile AWAITED attempts with manual status polling.

## Phase 3 - Production Activation
- Toggle production config `is_active=true` from admin settings.
- Monitor `BbpsApiAuditLog`, `BbpsPaymentAttempt`, and callback events every 15 minutes.
- Use ops console for complaint/deposit/plan checks.

## Rollback
- Set active config mode to `mock` or disable config.
- Stop initiating new live payments while continuing status checks for in-flight attempts.
- Reconcile refunded/reversed entries through `BbpsStatusPollLog` and passbook entries.
