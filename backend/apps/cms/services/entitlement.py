"""Admin entitlement + agent profile workflows for Uber CMS."""
from __future__ import annotations

import secrets
import string

from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied, ValidationError

from apps.cms.models import CmsAgentProfile, CmsEntitlement, CmsWallet
from apps.core.financial_access import FINANCIAL_TX_BLOCKED_ROLES
from apps.core.roles import is_platform_operator
from apps.core.utils import encrypt_secret_payload


def _require_admin(actor) -> None:
    if not is_platform_operator(actor):
        raise PermissionDenied('Only Admin can manage CMS entitlements.')


def _gen_bc_login_id(user) -> str:
    phone = ''.join(c for c in str(getattr(user, 'phone', '') or '') if c.isdigit())
    if len(phone) >= 10:
        candidate = f'CMS{phone[-10:]}'[:60]
        if not CmsAgentProfile.objects.filter(bc_login_id=candidate).exists():
            return candidate
    base = f'CMS{getattr(user, "member_number", None) or user.pk}'
    while True:
        suffix = ''.join(secrets.choice(string.digits) for _ in range(4))
        candidate = f'{base}{suffix}'[:60]
        if not CmsAgentProfile.objects.filter(bc_login_id=candidate).exists():
            return candidate


def _gen_pin() -> str:
    return ''.join(secrets.choice(string.digits) for _ in range(4))


def _ensure_agent_and_wallet(user) -> CmsAgentProfile:
    agent = CmsAgentProfile.objects.filter(user=user, is_deleted=False).first()
    if not agent:
        pin = _gen_pin()
        phone = ''.join(c for c in str(getattr(user, 'phone', '') or '') if c.isdigit())[-10:]
        agent = CmsAgentProfile.objects.create(
            user=user,
            bc_login_id=_gen_bc_login_id(user),
            merchant_pin_encrypted=encrypt_secret_payload({'pin': pin}),
            mobile_number=phone,
            status='active',
            activated_at=timezone.now(),
        )
    elif agent.status != 'active':
        agent.status = 'active'
        agent.activated_at = agent.activated_at or timezone.now()
        agent.save(update_fields=['status', 'activated_at', 'updated_at'])

    CmsWallet.objects.get_or_create(user=user, defaults={'balance': 0, 'held_balance': 0})
    return agent


@transaction.atomic
def enable_entitlement(*, actor, user, source: str = 'manual') -> CmsEntitlement:
    _require_admin(actor)
    if getattr(user, 'role', None) in FINANCIAL_TX_BLOCKED_ROLES:
        raise ValidationError(
            {
                'code': 'CMS_ADMIN_BLOCKED',
                'message': 'Cannot enable CMS trading for Admin users.',
            }
        )

    ent, _ = CmsEntitlement.objects.get_or_create(
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

    _ensure_agent_and_wallet(user)
    return ent


@transaction.atomic
def disable_entitlement(*, actor, user, reason: str = '') -> CmsEntitlement:
    _require_admin(actor)
    try:
        ent = CmsEntitlement.objects.get(user=user, is_deleted=False)
    except CmsEntitlement.DoesNotExist as exc:
        raise ValidationError({'message': 'User is not entitled for CMS.'}) from exc
    ent.enabled = False
    ent.disabled_at = timezone.now()
    ent.disabled_reason = reason or ''
    ent.save(update_fields=['enabled', 'disabled_at', 'disabled_reason', 'updated_at'])
    agent = CmsAgentProfile.objects.filter(user=user, is_deleted=False).first()
    if agent and agent.status == 'active':
        agent.status = 'suspended'
        agent.save(update_fields=['status', 'updated_at'])
    return ent


@transaction.atomic
def reset_agent_pin(*, actor, agent_id: int) -> dict:
    _require_admin(actor)
    agent = CmsAgentProfile.objects.select_for_update().get(pk=agent_id, is_deleted=False)
    pin = _gen_pin()
    agent.merchant_pin_encrypted = encrypt_secret_payload({'pin': pin})
    agent.save(update_fields=['merchant_pin_encrypted', 'updated_at'])
    return {'agent_id': agent.pk, 'bc_login_id': agent.bc_login_id, 'new_pin': pin}


def is_entitled(user) -> bool:
    return CmsEntitlement.objects.filter(user=user, enabled=True, is_deleted=False).exists()
