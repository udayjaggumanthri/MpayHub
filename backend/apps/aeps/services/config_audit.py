"""Provider config change audit + masked snapshots (never stores secrets)."""
from __future__ import annotations

from django.utils import timezone

from apps.core.utils import decrypt_secret_payload


SECRET_FIELD_NAMES = frozenset(
    {
        'password',
        'secret_key',
        'rsa_public_key_pem',
        'public_key',
        'secrets_encrypted',
        'callback_token',
    }
)


def looks_like_pem_certificate(value: str | None) -> bool:
    """True when an RSA/PEM cert was pasted into the wrong field (e.g. secret_key)."""
    s = str(value or '').strip()
    if not s:
        return False
    upper = s.upper()
    if 'BEGIN CERTIFICATE' in upper or 'BEGIN PUBLIC KEY' in upper or 'BEGIN RSA' in upper:
        return True
    # Typical Tapits secret_key is short; PEM bodies are much longer.
    if len(s) > 400 and ('MII' in s[:80] or s.count('\n') > 5):
        return True
    return False


def assert_secret_key_not_certificate(secret_key: str | None) -> tuple[bool, str]:
    if looks_like_pem_certificate(secret_key):
        return (
            False,
            'Secret key looks like an RSA certificate. Put the certificate only under '
            'Advanced → RSA public cert. Secret key must be the short Tapits key '
            '(same style as Simple, usually under ~200 characters).',
        )
    return True, ''

TRACKED_PROVIDER_FIELDS = (
    'environment',
    'is_active',
    'api_mode',
    'onboarding_api_style',
    'debug_mode',
    'egress_ip',
    'capture_ftype_aeps',
    'capture_ftype_ekyc',
    'super_merchant_id',
    'super_merchant_login_id',
    'onboarding_base_url',
    'ekyc_base_url',
    'aeps_base_url',
    'recon_base_url',
    'bank_list_url',
    'aadhaar_pay_bank_list_url',
    'request_timeout_seconds',
    'cw_ap_otp_threshold',
    'callback_allowed_ips',
    'notes',
)


def mask_provider_row(row) -> dict:
    secrets = decrypt_secret_payload(row.secrets_encrypted or '') or {} if row else {}
    return {
        'environment': getattr(row, 'environment', '') if row else '',
        'is_active': bool(row and row.is_active),
        'api_mode': getattr(row, 'resolved_api_mode', '') if row else '',
        'onboarding_api_style': getattr(row, 'resolved_onboarding_api_style', '') if row else '',
        'debug_mode': bool(row and row.debug_mode),
        'super_merchant_id': getattr(row, 'super_merchant_id', '') if row else '',
        'super_merchant_login_id': getattr(row, 'super_merchant_login_id', '') if row else '',
        'onboarding_base_url': getattr(row, 'onboarding_base_url', '') if row else '',
        'ekyc_base_url': getattr(row, 'ekyc_base_url', '') if row else '',
        'aeps_base_url': getattr(row, 'aeps_base_url', '') if row else '',
        'recon_base_url': getattr(row, 'recon_base_url', '') if row else '',
        'cw_ap_otp_threshold': getattr(row, 'cw_ap_otp_threshold', 5000) if row else 5000,
        'callback_allowed_ips': getattr(row, 'callback_allowed_ips', '') if row else '',
        'has_password': bool(secrets.get('password')),
        'has_secret_key': bool(secrets.get('secret_key')),
        'has_public_key': bool(secrets.get('rsa_public_key_pem') or secrets.get('public_key')),
        'has_callback_token': bool(getattr(row, 'callback_token', '')),
        'gstin_set': bool(secrets.get('gstin_number') or secrets.get('gstinNumber')),
        'pan_set': bool(secrets.get('company_or_shop_pan') or secrets.get('companyOrShopPan')),
    }


def changed_field_names(before: dict, after: dict) -> list[str]:
    keys = sorted(set(before.keys()) | set(after.keys()))
    return [k for k in keys if before.get(k) != after.get(k)]


def record_config_change(
    *,
    actor,
    environment: str,
    action: str,
    before_masked: dict | None = None,
    after_masked: dict | None = None,
    changed_fields: list | None = None,
    ip=None,
    note: str = '',
):
    from apps.aeps.models import AepsConfigChangeLog

    before_masked = before_masked or {}
    after_masked = after_masked or {}
    fields = changed_fields if changed_fields is not None else changed_field_names(before_masked, after_masked)
    # Never persist anything that looks like a secret value
    safe_before = {k: v for k, v in before_masked.items() if k.lower() not in SECRET_FIELD_NAMES}
    safe_after = {k: v for k, v in after_masked.items() if k.lower() not in SECRET_FIELD_NAMES}
    return AepsConfigChangeLog.objects.create(
        actor=actor if getattr(actor, 'pk', None) else None,
        environment=(environment or '')[:16],
        action=(action or 'save')[:64],
        changed_fields=list(fields)[:100],
        before_masked=safe_before,
        after_masked=safe_after,
        ip=ip,
        note=(note or '')[:500],
    )


def encrypted_profile_ready(row, secrets: dict | None = None) -> tuple[bool, str]:
    """Block activating encrypted UAT/Prod until password + secret + RSA are present."""
    if not row:
        return False, 'Provider row missing'
    mode = getattr(row, 'resolved_api_mode', None) or row.api_mode or 'encrypted'
    if (row.environment or '').lower() == 'simple' or mode == 'simple':
        secrets = secrets if secrets is not None else (decrypt_secret_payload(row.secrets_encrypted or '') or {})
        if not row.super_merchant_id or not row.super_merchant_login_id:
            return False, 'Simple profile needs super merchant id and login id'
        if not secrets.get('password') or not secrets.get('secret_key'):
            return False, 'Simple profile needs password and secret_key before activation'
        ok_sk, sk_msg = assert_secret_key_not_certificate(secrets.get('secret_key'))
        if not ok_sk:
            return False, sk_msg
        return True, ''
    secrets = secrets if secrets is not None else (decrypt_secret_payload(row.secrets_encrypted or '') or {})
    if not row.super_merchant_id or not row.super_merchant_login_id:
        return False, 'Encrypted profile needs super merchant id and login id'
    if not secrets.get('password'):
        return False, 'Encrypted profile needs password before activation'
    if not secrets.get('secret_key'):
        return False, 'Encrypted profile needs secret_key before activation'
    ok_sk, sk_msg = assert_secret_key_not_certificate(secrets.get('secret_key'))
    if not ok_sk:
        return False, sk_msg
    if not (secrets.get('rsa_public_key_pem') or secrets.get('public_key')):
        return False, 'Encrypted profile needs RSA public certificate before activation'
    return True, ''


def grant_provider_access(*, user, actor, note: str = ''):
    from apps.aeps.models import AepsProviderAccessGrant
    from apps.core.roles import ROLE_ADMIN

    if getattr(user, 'role', None) != ROLE_ADMIN:
        raise ValueError('Grants can only be issued to Admin role users')
    now = timezone.now()
    row, created = AepsProviderAccessGrant.objects.get_or_create(
        user=user,
        defaults={
            'is_active': True,
            'granted_by': actor,
            'granted_at': now,
            'note': (note or '')[:500],
        },
    )
    if not created:
        row.is_active = True
        row.is_deleted = False
        row.granted_by = actor
        row.granted_at = now
        row.revoked_by = None
        row.revoked_at = None
        row.note = (note or row.note or '')[:500]
        row.save()
    return row


def revoke_provider_access(*, user, actor, note: str = ''):
    from apps.aeps.models import AepsProviderAccessGrant

    try:
        row = AepsProviderAccessGrant.objects.get(user=user, is_deleted=False)
    except AepsProviderAccessGrant.DoesNotExist:
        return None
    row.is_active = False
    row.revoked_by = actor
    row.revoked_at = timezone.now()
    if note:
        row.note = (note or '')[:500]
    row.save()
    return row
