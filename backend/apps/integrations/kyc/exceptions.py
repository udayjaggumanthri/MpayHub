"""KYC provider exceptions."""


class KycProviderError(Exception):
    """Base error for KYC provider failures."""


class KycConfigurationError(KycProviderError):
    """Provider not configured or misconfigured in ApiMaster."""


class KycVerificationFailed(KycProviderError):
    """Verification rejected by provider or policy."""

    def __init__(self, message: str, *, code: str = '', details: dict | None = None):
        super().__init__(message)
        self.code = code
        self.details = details or {}
