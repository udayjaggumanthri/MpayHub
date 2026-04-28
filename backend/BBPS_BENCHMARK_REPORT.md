# BBPS Benchmark Report (Baseline)

## Scope
- Backend API latency sampling for:
  - fetch bill
  - pay bill
  - poll status
  - transaction query
- Frontend UX responsiveness spot-check for:
  - category->biller selection
  - fetch->quote render
  - complaint register/track actions

## Notes
- This baseline is measured in current development environment and should be re-run in UAT.
- Entitlement/IP allowlist failures can inflate API timing and must be treated separately from app latency.

## Suggested command set
- Backend unit suite:
  - `python manage.py test apps.bbps.tests --keepdb --noinput`
- Manual API timing samples:
  - `Measure-Command` or Postman collection runner with response time export.
- Frontend timing:
  - Browser Performance panel, capture interaction traces for BBPS journeys.

## Current run observations
- Lint diagnostics for changed files: no new linter errors.
- Automated test run currently blocked by environment system check (`django_ratelimit` shared-cache requirement in test env), not by BBPS assertion failures.

## Production/UAT benchmark acceptance suggestions
- p95 fetch/pay API under 2.5s for successful responses.
- p95 transaction query under 2s.
- first interactive render for bill payment screen under 1.5s on standard desktop profile.
