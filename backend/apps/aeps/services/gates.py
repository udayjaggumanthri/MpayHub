"""AEPS permission / stage gates."""
from __future__ import annotations

from django.utils import timezone
from rest_framework.exceptions import PermissionDenied

from apps.core.financial_access import FINANCIAL_TX_BLOCKED_ROLES
from apps.core.maintenance_mode import MODULE_AEPS, assert_module_available

CODE_NOT_ENTITLED = 'NOT_ENTITLED'
CODE_EKYC_REQUIRED = 'EKYC_REQUIRED'
CODE_TWOFA_REQUIRED = 'TWOFA_REQUIRED'
CODE_DEVICE_REQUIRED = 'DEVICE_REQUIRED'
CODE_ADMIN_BLOCKED = 'AEPS_ADMIN_BLOCKED'
CODE_SUSPENDED = 'AEPS_SUSPENDED'


def _deny(code: str, message: str) -> PermissionDenied:
    return PermissionDenied(detail={'code': code, 'message': message})


def assert_aeps_module_on() -> None:
    assert_module_available(MODULE_AEPS)


def user_may_trade_aeps(user) -> bool:
    role = getattr(user, 'role', None)
    if role in FINANCIAL_TX_BLOCKED_ROLES:
        return False
    return True


def get_entitlement(user):
    from apps.aeps.models import AepsEntitlement

    try:
        return AepsEntitlement.objects.get(user=user, is_deleted=False)
    except AepsEntitlement.DoesNotExist:
        return None


def is_entitled(user) -> bool:
    ent = get_entitlement(user)
    return bool(ent and ent.enabled)


def get_merchant(user):
    from apps.aeps.models import AepsMerchantProfile

    try:
        return AepsMerchantProfile.objects.get(user=user, is_deleted=False)
    except AepsMerchantProfile.DoesNotExist:
        return None


def assert_entitled(user) -> None:
    assert_aeps_module_on()
    if not user_may_trade_aeps(user):
        raise _deny(CODE_ADMIN_BLOCKED, 'Admin accounts cannot perform AEPS transactions.')
    if not is_entitled(user):
        raise _deny(CODE_NOT_ENTITLED, 'AEPS is not enabled for your account. Request access or contact Admin.')


def assert_merchant_active(user):
    assert_entitled(user)
    merchant = get_merchant(user)
    if not merchant or merchant.stage == 'suspended':
        raise _deny(CODE_SUSPENDED, 'Your AEPS merchant is suspended or not set up.')
    if merchant.stage != 'active':
        raise _deny(CODE_EKYC_REQUIRED, 'Complete AEPS onboarding and eKYC before transacting.')
    return merchant


def assert_device_ready(merchant) -> None:
    if not merchant.device_imei or not merchant.device_ready:
        raise _deny(CODE_DEVICE_REQUIRED, 'Connect and register your Mantra fingerprint device first.')


def assert_daily_2fa(merchant) -> None:
    from apps.aeps.models import AepsDaily2FA

    today = timezone.localdate()
    ok = AepsDaily2FA.objects.filter(
        merchant=merchant,
        for_date=today,
        status='success',
    ).exists()
    if not ok:
        raise _deny(CODE_TWOFA_REQUIRED, 'Complete today’s AEPS 2FA before continuing.')


def me_status_payload(user) -> dict:
    from apps.aeps.models import AepsAccessRequest, AepsDaily2FA

    is_admin = getattr(user, 'role', None) == 'Admin'
    can_trade = user_may_trade_aeps(user)
    ent = get_entitlement(user)
    merchant = get_merchant(user)
    pending_req = None
    if user and user.is_authenticated and can_trade:
        pending_req = (
            AepsAccessRequest.objects.filter(user=user, status='pending', is_deleted=False)
            .order_by('-created_at')
            .first()
        )
    today = timezone.localdate()
    twofa_ok = False
    if merchant:
        twofa_ok = AepsDaily2FA.objects.filter(
            merchant=merchant, for_date=today, status='success'
        ).exists()

    stage = merchant.stage if merchant else ('entitled' if (ent and ent.enabled) else 'not_entitled')
    next_action = 'none'
    if is_admin or not can_trade:
        next_action = 'admin_ops'
        stage = 'admin'
    elif not ent or not ent.enabled:
        next_action = 'request_access' if not pending_req else 'await_approval'
    elif not merchant or merchant.stage in ('not_started', 'onboarding_draft'):
        next_action = 'onboarding'
    elif merchant.stage in ('onboarding_submitted', 'ekyc_pending') and not merchant.device_ready:
        next_action = 'device'
    elif merchant.stage in ('onboarding_submitted', 'ekyc_pending'):
        next_action = 'ekyc'
    elif merchant.stage == 'active' and not merchant.device_ready:
        next_action = 'device'
    elif merchant.stage == 'active' and not twofa_ok:
        next_action = 'twofa'
    elif merchant.stage == 'active':
        next_action = 'ready'

    merchant_block = None
    if merchant:
        # Never embed full onboarding_payload here — drafts can include multi-MB base64
        # KYC images and would make /aeps/me/status/ hang the SPA (looks like "not entitled").
        raw_payload = merchant.onboarding_payload if isinstance(merchant.onboarding_payload, dict) else {}
        image_keys = {
            'merchantPanImage',
            'maskedAadharImage',
            'backgroundImageOfShop',
            'cancelledChequeImages',
            'tradeBusinessProof',
        }
        light_fields = {
            k: v
            for k, v in raw_payload.items()
            if k not in image_keys and not (isinstance(v, str) and len(v) > 500)
        }
        merchant_block = {
            'merchant_login_id': merchant.merchant_login_id,
            'stage': merchant.stage,
            'device_imei': merchant.device_imei,
            'scanner_serial': merchant.scanner_serial,
            'device_ready': merchant.device_ready,
            'masked_aadhaar': merchant.masked_aadhaar,
            'last_2fa_at': merchant.last_2fa_at.isoformat() if merchant.last_2fa_at else None,
            'twofa_ok_today': twofa_ok,
            'has_onboarding_draft': bool(raw_payload),
            'onboarding_draft_keys': sorted(raw_payload.keys()),
            # Lightweight text fields only (images belong on /aeps/onboarding/draft/).
            'onboarding_summary': light_fields,
        }

    return {
        'module_key': 'aeps',
        'is_admin': is_admin,
        'entitled': bool(ent and ent.enabled),
        'can_trade': can_trade,
        'pending_access_request': bool(pending_req),
        'merchant': merchant_block,
        'stage': stage,
        'next_action': next_action,
        'capture_profile': capture_profile_payload(),
    }


def capture_profile_payload() -> dict:
    """RD-service capture options the browser should use, from provider config."""
    from apps.aeps.models import AepsProviderConfig

    row = (
        AepsProviderConfig.objects.filter(is_active=True, is_deleted=False)
        .order_by('-updated_at')
        .first()
    )
    return {
        'ftype_aeps': (getattr(row, 'capture_ftype_aeps', '') or '2'),
        'ftype_ekyc': (getattr(row, 'capture_ftype_ekyc', '') or '2'),
    }
