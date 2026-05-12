"""BBPS module-level constants (keep tiny to avoid import cycles with services ↔ catalog)."""

# BillAvenue / NPCI billerStatus values treated as billable in partner flows.
ALLOWED_BILLER_STATUSES: frozenset[str] = frozenset({'ACTIVE', 'ENABLED', 'FLUCTUATING'})
