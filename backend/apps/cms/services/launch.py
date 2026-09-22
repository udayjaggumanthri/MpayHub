"""Build encrypted Uber CMS launch URL for entitled agents."""
from __future__ import annotations

from datetime import timedelta
from decimal import Decimal, InvalidOperation

from django.utils import timezone
from rest_framework.exceptions import PermissionDenied, ValidationError

from apps.cms.models import CmsAgentProfile, CmsLaunchSession
from apps.cms.services import entitlement as entitlement_svc
from apps.cms.services.crypto import build_launch_url, encrypt_launch_payload
from apps.cms.services.ids import agent_pin_plain
from apps.cms.services.registry import get_active_cms_config
from apps.core.maintenance_mode import MODULE_CMS, assert_module_available


def prepare_launch(
    *,
    user,
    amount,
    latitude,
    longitude,
    client_ip: str | None = None,
    additional_params=None,
) -> dict:
    assert_module_available(MODULE_CMS)

    if not entitlement_svc.is_entitled(user):
        raise PermissionDenied(
            detail={
                'code': 'CMS_NOT_ENTITLED',
                'message': 'CMS is not enabled for your account. Contact Admin.',
            }
        )

    agent = CmsAgentProfile.objects.filter(user=user, is_deleted=False).first()
    if not agent or agent.status != 'active':
        raise ValidationError(
            {
                'code': 'CMS_AGENT_INACTIVE',
                'message': 'CMS agent profile is not active.',
            }
        )

    try:
        amt = Decimal(str(amount))
    except (InvalidOperation, TypeError) as exc:
        raise ValidationError({'message': 'Invalid amount'}) from exc
    if amt < 0:
        raise ValidationError({'message': 'Amount cannot be negative'})

    try:
        lat = float(latitude)
        lng = float(longitude)
    except (TypeError, ValueError) as exc:
        raise ValidationError({'message': 'Location (latitude/longitude) is required'}) from exc

    cfg = get_active_cms_config(require_secrets=True)
    if not cfg.cms_base_url:
        raise ValidationError(
            {
                'code': 'CMS_BASE_URL_MISSING',
                'message': 'CMS base URL is not configured.',
            }
        )
    if not cfg.super_merchant_id:
        raise ValidationError(
            {
                'code': 'CMS_SUPERMERCHANT_MISSING',
                'message': 'CMS superMerchantId is not configured.',
            }
        )

    pin = agent_pin_plain(agent)
    if not pin:
        raise ValidationError({'message': 'CMS agent PIN is missing. Ask Admin to reset PIN.'})

    mobile = (agent.mobile_number or '').strip()
    if len(mobile) < 10:
        phone = ''.join(c for c in str(getattr(user, 'phone', '') or '') if c.isdigit())
        mobile = phone[-10:] if len(phone) >= 10 else phone

    payload = {
        'additionalParams': additional_params,
        'latitude': lat,
        'loginType': cfg.login_type or '2',
        'longitude': lng,
        'supermerchantId': str(cfg.super_merchant_id),
        'merchantId': agent.bc_login_id,
        'merchantPin': pin,
        'mobileNumber': mobile,
        'amount': str(amt.quantize(Decimal('0.01'))),
        'superMerchantSkey': cfg.super_merchant_skey,
    }

    encrypted = encrypt_launch_payload(payload, super_merchant_skey=cfg.super_merchant_skey)
    url = build_launch_url(
        cms_base_url=cfg.cms_base_url,
        login_path=cfg.login_path,
        encrypted_data=encrypted,
        skey=cfg.super_merchant_skey,
    )

    expires_at = timezone.now() + timedelta(minutes=10)
    session = CmsLaunchSession.objects.create(
        user=user,
        agent=agent,
        amount=amt.quantize(Decimal('0.01')),
        latitude=lat,
        longitude=lng,
        status='created',
        expires_at=expires_at,
        client_ip=client_ip,
    )

    return {
        'url': url,
        'launch_id': session.pk,
        'expires_at': expires_at.isoformat(),
        'amount': str(amt.quantize(Decimal('0.01'))),
        'bc_login_id': agent.bc_login_id,
    }
