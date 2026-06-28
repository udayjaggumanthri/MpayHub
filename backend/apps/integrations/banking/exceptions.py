"""Bank account verification provider exceptions."""


class BavProviderError(Exception):
    """Base error for BAV provider failures."""


class BavConfigurationError(BavProviderError):
    """Provider not configured or misconfigured in ApiMaster."""


class BavVerificationFailed(BavProviderError):
    """Verification rejected by provider or policy."""

    def __init__(self, message: str, *, code: str = '', details: dict | None = None):
        super().__init__(message)
        self.code = code
        self.details = details or {}
