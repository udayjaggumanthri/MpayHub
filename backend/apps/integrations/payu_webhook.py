"""
PayU India webhook verification (scaffold).

Pay-in checkout for PayU is not enabled yet; the HTTP view returns 501 and does not credit wallets.

When enabling:
- Map POST fields to ``LoadMoney`` (e.g. match merchant txn id to ``provider_order_id`` / ``transaction_id`` per PayU docs).
- Implement ``verify_payu_webhook_request`` using the documented reverse-hash sequence and field order,
  using ``PAYU_MERCHANT_KEY`` / ``PAYU_MERCHANT_SALT`` from Django settings.
"""
from __future__ import annotations

import logging

from django.conf import settings
from django.http import HttpRequest

logger = logging.getLogger(__name__)


def verify_payu_webhook_request(request: HttpRequest) -> bool:
    """
    Verify PayU webhook authenticity (stub).

    Returns False when salt is not configured or verification is not implemented.
    Product must supply exact field order for reverse-hash (PayU India merchant docs).
    """
    salt = (getattr(settings, 'PAYU_MERCHANT_SALT', None) or '').strip()
    if not salt:
        return False
    # TODO: build reverse hash from request.POST / JSON per PayU spec; compare to posted hash.
    return False


def log_payu_webhook_post(request: HttpRequest, *, outcome: str, verified: bool = False) -> None:
    """Warning-level log for every PayU webhook POST (outcome for ops / security monitoring)."""
    logger.warning(
        'PayU webhook POST: outcome=%s verified=%s path=%s',
        outcome,
        verified,
        getattr(request, 'path', '') or '',
    )
