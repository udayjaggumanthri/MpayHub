"""Payout provider exceptions."""


class PayoutProviderError(Exception):
    """Base error for payout provider failures."""


class PayoutConfigurationError(PayoutProviderError):
    """Provider not configured or misconfigured in ApiMaster."""


class PayoutNotSupportedError(PayoutProviderError):
    """Optional capability not implemented by this provider."""


class PayoutInitiateError(PayoutProviderError):
    """Provider rejected or failed to accept an initiate request."""

    def __init__(self, message: str, *, code: str = '', details: dict | None = None):
        super().__init__(message)
        self.code = code
        self.details = details or {}


class PayoutCryptoError(PayoutProviderError):
    """Encrypt/decrypt failure."""
