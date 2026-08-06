"""Domain exceptions for wallet adjustments (caught by views; not DRF defaults)."""


class WalletAdjustmentError(Exception):
    """Validation / business-rule failure before or during an adjustment."""

    def __init__(self, message: str, *, code: str = 'WALLET_ADJUSTMENT_INVALID'):
        super().__init__(message)
        self.code = code
