"""Admin entitlement + access-request workflows."""
from __future__ import annotations

import secrets
import string

from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied, ValidationError

from apps.aeps.models import AepsAccessRequest, AepsEntitlement, AepsMerchantProfile
from apps.core.financial_access import FINANCIAL_TX_BLOCKED_ROLES
from apps.core.utils import encrypt_secret_payload


def _require_admin(actor) -> None:
    if getattr(actor, 'role', None) != 'Admin':
        raise PermissionDenied('Only Admin can manage AEPS entitlements.')


def _gen_merchant_login_id(user) -> str:
    base = f"MPH{getattr(user, 'member_number', None) or user.pk}"
    suffix = ''.join(secrets.choice(string.digits) for _ in range(3))
    candidate = f'{base}{suffix}'[:60]
    while AepsMerchantProfile.objects.filter(merchant_login_id=candidate).exists():
        suffix = ''.join(secrets.choice(string.digits) for _ in range(3))
        candidate = f'{base}{suffix}'[:60]
    return candidate


def _gen_pin() -> str:
    return ''.join(secrets.choice(string.digits) for _ in range(4))


@transaction.atomic
def enable_entitlement(*, actor, user, source: str = 'manual') -> AepsEntitlement:
    _require_admin(actor)
    if getattr(user, 'role', None) in FINANCIAL_TX_BLOCKED_ROLES:
        raise ValidationError({'code': 'AEPS_ADMIN_BLOCKED', 'message': 'Cannot enable AEPS trading for Admin users.'})

    ent, _ = AepsEntitlement.objects.get_or_create(
        user=user,
        defaults={
            'enabled': True,
            'source': source,
            'assigned_by': actor,
            'assigned_at': timezone.now(),
        },
    )
    if not ent.enabled or ent.is_deleted:
        ent.enabled = True
        ent.is_deleted = False
        ent.deleted_at = None
        ent.source = source
        ent.assigned_by = actor
        ent.assigned_at = timezone.now()
        ent.disabled_at = None
        ent.disabled_reason = ''
        ent.save()

    if not AepsMerchantProfile.objects.filter(user=user, is_deleted=False).exists():
        pin = _gen_pin()
        AepsMerchantProfile.objects.create(
            user=user,
            merchant_login_id=_gen_merchant_login_id(user),
            merchant_pin_encrypted=encrypt_secret_payload({'pin': pin}),
            stage='not_started',
        )
    return ent


@transaction.atomic
def disable_entitlement(*, actor, user, reason: str = '') -> AepsEntitlement:
    _require_admin(actor)
    try:
        ent = AepsEntitlement.objects.get(user=user, is_deleted=False)
    except AepsEntitlement.DoesNotExist as exc:
        raise ValidationError({'message': 'User is not entitled for AEPS.'}) from exc
    ent.enabled = False
    ent.disabled_at = timezone.now()
    ent.disabled_reason = reason or ''
    ent.save(update_fields=['enabled', 'disabled_at', 'disabled_reason', 'updated_at'])
    merchant = AepsMerchantProfile.objects.filter(user=user, is_deleted=False).first()
    if merchant and merchant.stage == 'active':
        merchant.stage = 'suspended'
        merchant.save(update_fields=['stage', 'updated_at'])
    return ent


def create_access_request(*, user, reason: str = '') -> AepsAccessRequest:
    if getattr(user, 'role', None) in FINANCIAL_TX_BLOCKED_ROLES:
        raise ValidationError(
            {
                'code': 'AEPS_ADMIN_BLOCKED',
                'message': 'Admin accounts manage AEPS only and cannot request trading access. Enable AEPS for an operator user instead.',
            }
        )
    if AepsEntitlement.objects.filter(user=user, enabled=True, is_deleted=False).exists():
        raise ValidationError({'code': 'ALREADY_ENTITLED', 'message': 'AEPS is already enabled for your account.'})
    if AepsAccessRequest.objects.filter(user=user, status='pending', is_deleted=False).exists():
        raise ValidationError({'code': 'REQUEST_PENDING', 'message': 'You already have a pending AEPS access request.'})
    return AepsAccessRequest.objects.create(user=user, reason=reason or '', status='pending')


@transaction.atomic
def decide_access_request(*, actor, request_id: int, decision: str, notes: str = '') -> AepsAccessRequest:
    _require_admin(actor)
    decision = (decision or '').lower().strip()
    if decision not in ('approved', 'rejected'):
        raise ValidationError({'message': 'decision must be approved or rejected.'})
    req = AepsAccessRequest.objects.select_for_update().get(pk=request_id, is_deleted=False)
    if req.status != 'pending':
        raise ValidationError({'message': 'Request is not pending.'})
    req.status = decision
    req.reviewed_by = actor
    req.reviewed_at = timezone.now()
    req.review_notes = notes or ''
    req.save()
    if decision == 'approved':
        enable_entitlement(actor=actor, user=req.user, source='access_request')
    return req
