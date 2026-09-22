"""
Wallet transfer operations.

Main→BBPS transfer has been removed after single-wallet consolidation.
Kept as a module stub so historical imports do not break.
"""
import logging
from decimal import Decimal

logger = logging.getLogger(__name__)


class TransferRemovedError(Exception):
    """Raised when a client still calls the deprecated main→BBPS transfer."""

    def __init__(self):
        super().__init__(
            'Main-to-BBPS wallet transfer has been removed. '
            'All bill payments debit your main wallet directly.'
        )


def transfer_main_to_bbps(user, amount: Decimal) -> dict:
    """Deprecated — raises TransferRemovedError."""
    raise TransferRemovedError()
