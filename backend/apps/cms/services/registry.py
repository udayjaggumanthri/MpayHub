"""Active CmsProviderConfig + decrypted secrets."""
from __future__ import annotations

from dataclasses import dataclass

from django.core.cache import cache
from rest_framework.exceptions import ValidationError

from apps.cms.models import CmsProviderConfig
from apps.core.utils import decrypt_secret_payload

CACHE_KEY = 'cms_active_provider_v1'
CACHE_TTL = 30


@dataclass
class CmsActiveConfig:
    row: CmsProviderConfig
    super_merchant_id: str
    super_merchant_skey: str
    secret_key: str
    login_type: str
    cms_base_url: str
    login_path: str
    hash_template: str
    allowed_inbound_ips: list
    debug_mode: bool
    hold_ttl_hours: int
    environment: str


def invalidate_cms_config_cache() -> None:
    cache.delete(CACHE_KEY)


def get_active_cms_config(*, require_secrets: bool = True) -> CmsActiveConfig:
    cached = cache.get(CACHE_KEY)
    if cached is not None:
        return cached

    row = (
        CmsProviderConfig.objects.filter(is_active=True, is_deleted=False)
        .order_by('-updated_at')
        .first()
    )
    if not row:
        raise ValidationError(
            {
                'code': 'CMS_PROVIDER_MISSING',
                'message': 'CMS provider is not configured. Ask Admin to save Uber CMS settings.',
            }
        )

    secrets = decrypt_secret_payload(row.secrets_encrypted or '') or {}
    skey = str(secrets.get('super_merchant_skey') or secrets.get('superMerchantSkey') or '').strip()
    secret = str(secrets.get('secret_key') or secrets.get('secretKey') or '').strip()
    if require_secrets and (not skey or not secret):
        raise ValidationError(
            {
                'code': 'CMS_SECRETS_MISSING',
                'message': 'CMS provider secrets are incomplete (superMerchantSkey / secretKey).',
            }
        )

    cfg = CmsActiveConfig(
        row=row,
        super_merchant_id=str(row.super_merchant_id or '').strip(),
        super_merchant_skey=skey,
        secret_key=secret,
        login_type=str(row.login_type or '2'),
        cms_base_url=str(row.cms_base_url or '').rstrip('/'),
        login_path=str(row.login_path or '/UberCMSBC/#/login'),
        hash_template=str(row.hash_template or '{payload}{secret_key}'),
        allowed_inbound_ips=list(row.allowed_inbound_ips or []),
        debug_mode=bool(row.debug_mode),
        hold_ttl_hours=int(row.hold_ttl_hours or 24),
        environment=str(row.environment or 'uat'),
    )
    cache.set(CACHE_KEY, cfg, CACHE_TTL)
    return cfg
