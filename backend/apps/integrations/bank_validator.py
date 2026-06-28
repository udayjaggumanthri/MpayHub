"""
Bank account validation integration facade.
"""
from apps.integrations.banking.registry import resolve_bav_provider
from apps.integrations.banking.types import BavVerifyResult


class BankValidator:
    """Thin facade over configured BAV provider."""

    def __init__(self):
        self._provider = None

    def _get_provider(self):
        if self._provider is None:
            self._provider = resolve_bav_provider()
        return self._provider

    @property
    def provider_code(self) -> str:
        return self._get_provider().provider_code

    def validate_account(
        self,
        account_number: str,
        ifsc: str,
        *,
        user=None,
        name: str = '',
        phone: str = '',
    ) -> BavVerifyResult:
        return self._get_provider().verify(
            user=user,
            account_number=account_number,
            ifsc=ifsc,
            name=name,
            phone=phone,
        )
