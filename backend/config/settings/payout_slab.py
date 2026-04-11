"""Payout slab charge configuration (addition model)."""
from decimal import Decimal

# ₹1–₹24,999 → flat low charge; ₹25,000+ → high charge
PAYOUT_SLAB_LOW_MAX = Decimal('24999')
PAYOUT_CHARGE_LOW = Decimal('7')
PAYOUT_CHARGE_HIGH = Decimal('15')
