"""Payout provider adapters. Register new providers in registry.PAYOUT_PROVIDER_CODES."""
from apps.integrations.payout.providers.vimopay import VimopayPayoutProvider

__all__ = ['VimopayPayoutProvider']
