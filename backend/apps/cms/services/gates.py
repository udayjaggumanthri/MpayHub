"""CMS journey status for the partner portal."""
from __future__ import annotations

from apps.cms.models import CmsAgentProfile, CmsEntitlement
from apps.cms.services import wallet as wallet_svc
from apps.cms.services.registry import get_active_cms_config
from apps.core.roles import is_platform_operator


def me_status_payload(user) -> dict:
    entitled = CmsEntitlement.objects.filter(user=user, enabled=True, is_deleted=False).exists()
    agent = CmsAgentProfile.objects.filter(user=user, is_deleted=False).first()
    provider_ok = False
    try:
        get_active_cms_config(require_secrets=True)
        provider_ok = True
    except Exception:
        provider_ok = False

    if is_platform_operator(user):
        next_action = 'admin_ops'
    elif not entitled:
        next_action = 'request_access'
    elif not agent or agent.status != 'active':
        next_action = 'await_agent'
    elif not provider_ok:
        next_action = 'await_provider'
    else:
        next_action = 'ready'

    snap = wallet_svc.wallet_snapshot(user) if entitled else {
        'balance': '0.00',
        'held_balance': '0.00',
        'available': '0.00',
    }

    return {
        'entitled': entitled,
        'next_action': next_action,
        'provider_configured': provider_ok,
        'agent': (
            {
                'bc_login_id': agent.bc_login_id,
                'status': agent.status,
                'mobile_number': agent.mobile_number,
            }
            if agent
            else None
        ),
        'wallet': snap,
    }
