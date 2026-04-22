"""Shared money quantization for fund_management (avoids circular imports with services)."""
from decimal import Decimal


def money_q(v) -> Decimal:
    """
    Quantize money to 4 dp safely (enterprise ledger / reporting).
    Accepts Decimal/float/int/str to avoid runtime errors from mixed numeric sources.
    """
    return Decimal(str(v)).quantize(Decimal('0.0001'))
