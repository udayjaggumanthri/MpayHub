"""PayU order creation (placeholder — extend with PayU v2 / hash flow)."""
import logging

from django.conf import settings

logger = logging.getLogger(__name__)


def payu_is_configured():
    return bool(getattr(settings, 'PAYU_MERCHANT_KEY', '') and getattr(settings, 'PAYU_MERCHANT_SALT', ''))


def create_payu_hash_payload(*, amount_inr, transaction_id, customer_name, customer_email, customer_phone):
    """Return dict for frontend PayU Bolt / redirect or None if not implemented."""
    if not payu_is_configured():
        return None, 'not_configured'
    logger.info('PayU order stub for txn %s — implement merchant hash per PayU docs', transaction_id)
    return None, 'not_implemented'
