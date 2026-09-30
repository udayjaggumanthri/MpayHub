"""Abstract payout provider port — adapters implement this; domain uses only these methods."""
from __future__ import annotations

from abc import ABC, abstractmethod
from decimal import Decimal
from typing import Any

from apps.integrations.payout.types import (
    MasterItem,
    PayoutCallbackEvent,
    PayoutInitiateRequest,
    PayoutInitiateResult,
)


class PayoutProvider(ABC):
    @property
    @abstractmethod
    def provider_code(self) -> str:
        ...

    def amount_limits(self) -> tuple[Decimal, Decimal]:
        """
        (min, max) principal amounts for this provider.
        Override via ApiMaster.config_json min_amount / max_amount.
        """
        cfg = getattr(getattr(self, 'master', None), 'config_json', None) or {}
        if not isinstance(cfg, dict):
            cfg = {}
        try:
            mn = Decimal(str(cfg.get('min_amount') or '100'))
        except Exception:
            mn = Decimal('100')
        try:
            mx = Decimal(str(cfg.get('max_amount') or '100000'))
        except Exception:
            mx = Decimal('100000')
        return mn, mx

    def supported_transfer_modes(self) -> frozenset[str]:
        """Uppercase modes e.g. IMPS, NEFT. Override per provider."""
        cfg = getattr(getattr(self, 'master', None), 'config_json', None) or {}
        if isinstance(cfg, dict) and cfg.get('transfer_modes'):
            raw = cfg.get('transfer_modes')
            if isinstance(raw, (list, tuple)):
                return frozenset(str(x).strip().upper() for x in raw if str(x).strip())
        return frozenset({'IMPS', 'NEFT'})

    def default_purpose_code(self) -> str:
        cfg = getattr(getattr(self, 'master', None), 'config_json', None) or {}
        if isinstance(cfg, dict):
            return str(cfg.get('default_purpose_code') or '004').strip() or '004'
        return '004'

    def normalize_beneficiary_name(self, name: str) -> str:
        """Provider-specific name cleanup before initiate. Default: strip."""
        return str(name or '').strip()

    @abstractmethod
    def list_banks(self) -> list[MasterItem]:
        ...

    @abstractmethod
    def list_states(self) -> list[MasterItem]:
        ...

    @abstractmethod
    def list_purposes(self) -> list[MasterItem]:
        ...

    @abstractmethod
    def initiate(self, request: PayoutInitiateRequest) -> PayoutInitiateResult:
        ...

    @abstractmethod
    def parse_callback(self, raw: dict[str, Any] | list | str | bytes) -> PayoutCallbackEvent:
        ...

    def inquire_status(self, merchant_ref_id: str) -> PayoutCallbackEvent:
        """Optional. Providers without inquiry raise NotSupported."""
        from apps.integrations.payout.exceptions import PayoutNotSupportedError

        raise PayoutNotSupportedError(
            f'{self.provider_code} does not support status inquiry for {merchant_ref_id}'
        )

    def test_connection(self) -> dict[str, Any]:
        """Optional health check (e.g. authorize). Returns dict with ok/detail."""
        return {'ok': True, 'detail': 'no_test'}
