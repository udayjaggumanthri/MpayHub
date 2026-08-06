"""
BillAvenue Deposit Enquiry — fetch prepaid deposit ledger for agent(s).

Stores every run as BbpsDepositEnquirySnapshot for ops reporting.
"""
from __future__ import annotations

import logging
from decimal import Decimal, InvalidOperation
from typing import Any

from django.utils import timezone

from apps.bbps.catalog.env import active_bbps_environment
from apps.bbps.models import BbpsDepositEnquirySnapshot
from apps.fund_management.money_utils import money_q
from apps.integrations.bbps_client import BBPSClient
from apps.integrations.billavenue.errors import BillAvenueClientError
from apps.integrations.billavenue.parsers import extract_response_code
from apps.integrations.billavenue.registry import (
    get_active_billavenue_config,
    normalize_billavenue_mode,
)
from apps.integrations.billavenue.request_id import generate_billavenue_request_id
from apps.integrations.models import BillAvenueAgentProfile

logger = logging.getLogger(__name__)


def _new_request_id() -> str:
    """BillAvenue E009 requires the standard 35-char requestId (not a custom DEP… prefix)."""
    return generate_billavenue_request_id()


def _normalize_request_id(raw: str) -> str:
    """Accept a caller id only if it already matches BillAvenue's 35-char shape; else generate."""
    rid = str(raw or '').strip()
    if len(rid) == 35 and rid.isalnum() and rid.isupper():
        return rid
    # Allow mixed-case alphanumeric of exact length (envelope generator uses upper+digits).
    if len(rid) == 35 and rid.isalnum():
        return rid.upper()
    return _new_request_id()


def default_agent_ids_for_active_env() -> list[str]:
    """Agent IDs from enabled profiles on the active BillAvenue config."""
    cfg = get_active_billavenue_config()
    if not cfg:
        return []
    qs = BillAvenueAgentProfile.objects.filter(
        config=cfg, enabled=True, is_deleted=False
    ).order_by('name')
    out: list[str] = []
    for row in qs:
        aid = str(row.agent_id or '').strip()
        if aid and aid not in out:
            out.append(aid)
    return out


def list_agent_options() -> list[dict[str, Any]]:
    cfg = get_active_billavenue_config()
    if not cfg:
        return []
    rows = []
    for p in BillAvenueAgentProfile.objects.filter(config=cfg, is_deleted=False).order_by('name'):
        rows.append(
            {
                'id': p.pk,
                'name': p.name,
                'agent_id': p.agent_id,
                'init_channel': p.init_channel,
                'enabled': bool(p.enabled),
            }
        )
    return rows


def _as_list(value) -> list:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, dict):
        # Single transaction object shaped as dict
        return [value]
    return []


def extract_deposit_transactions(resp: dict) -> list[dict[str, Any]]:
    """Normalize BillAvenue deposit enquiry transaction rows."""
    if not isinstance(resp, dict):
        return []
    raw = (
        resp.get('transaction')
        or resp.get('transactions')
        or resp.get('txnList')
        or resp.get('depositList')
        or []
    )
    if isinstance(raw, dict):
        # Sometimes wrapped: { transaction: { transaction: [...] } } or single row
        nested = raw.get('transaction') or raw.get('transactions') or raw.get('txnList')
        raw = nested if nested is not None else [raw]
    rows = []
    for item in _as_list(raw):
        if not isinstance(item, dict):
            continue
        rows.append(
            {
                'agent_id': str(item.get('agentId') or item.get('agent_id') or '').strip(),
                'transaction_id': str(
                    item.get('transactionId') or item.get('transaction_id') or item.get('txnRefId') or ''
                ).strip(),
                'request_id': str(item.get('requestId') or item.get('request_id') or '').strip(),
                'amount': str(item.get('amount') if item.get('amount') is not None else ''),
                'trans_type': str(item.get('transType') or item.get('txnType') or item.get('type') or '').strip().upper(),
                'source': str(item.get('source') or '').strip(),
                'datetime': str(item.get('datetime') or item.get('txnDate') or item.get('dateTime') or '').strip(),
            }
        )
    return rows


def serialize_snapshot(shot: BbpsDepositEnquirySnapshot, *, include_payload: bool = False) -> dict[str, Any]:
    resp = shot.response_payload if isinstance(shot.response_payload, dict) else {}
    transactions = extract_deposit_transactions(resp) if include_payload or shot.transaction_count else []
    if not include_payload and shot.transaction_count and not transactions:
        transactions = extract_deposit_transactions(resp)
    data = {
        'id': shot.pk,
        'request_id': shot.request_id or '',
        'environment': shot.environment or '',
        'from_date': shot.from_date or '',
        'to_date': shot.to_date or '',
        'trans_type': shot.trans_type or '',
        'agents': list(shot.agents or []),
        'current_balance': str(money_q(shot.current_balance)),
        'currency': shot.currency or 'INR',
        'response_code': shot.response_code or '',
        'transaction_count': int(shot.transaction_count or 0),
        'status': shot.status or '',
        'error_message': shot.error_message or '',
        'performed_by_id': shot.performed_by_id,
        'created_at': shot.created_at.isoformat() if shot.created_at else None,
        'transactions': transactions if include_payload else [],
    }
    if include_payload:
        data['response_payload'] = resp
        data['transactions'] = extract_deposit_transactions(resp)
    return data


def enquire_deposits(
    *,
    from_date: str,
    to_date: str,
    trans_type: str = '',
    agents: list[str] | None = None,
    request_id: str = '',
    transaction_id: str = '',
    admin_user=None,
) -> dict:
    env = normalize_billavenue_mode(active_bbps_environment())
    from_date = str(from_date or '').strip()
    to_date = str(to_date or '').strip()
    if not from_date or not to_date:
        raise ValueError('from_date and to_date are required (YYYY-MM-DD).')

    agent_list = [str(a).strip() for a in (agents or []) if str(a).strip()]
    if not agent_list:
        agent_list = default_agent_ids_for_active_env()
    if not agent_list:
        raise ValueError(
            'No agent IDs provided and no enabled BillAvenue agent profile is configured. '
            'Add an agent profile under BillAvenue Settings, or pass agents explicitly.'
        )

    rid = _normalize_request_id(request_id)
    txn_type = str(trans_type or '').strip().upper()
    if txn_type and txn_type not in ('CR', 'DR'):
        raise ValueError('trans_type must be CR, DR, or blank (all).')

    payload = {
        'fromDate': from_date,
        'toDate': to_date,
        'transType': txn_type,
        'agents': agent_list,
        'requestId': rid,
        'transactionId': str(transaction_id or '').strip(),
    }

    try:
        client = BBPSClient()
        resp = client.enquire_deposits(payload)
        if not isinstance(resp, dict):
            resp = {'raw': resp}
        code = str(extract_response_code(resp) or resp.get('responseCode') or '').strip()
        transactions = extract_deposit_transactions(resp)
        try:
            bal = money_q(Decimal(str(resp.get('currentBalance') or '0')))
        except (InvalidOperation, TypeError, ValueError):
            bal = money_q(Decimal('0'))
        currency = str(resp.get('currency') or 'INR').strip() or 'INR'
        ok = code in ('', '000', '0')
        shot = BbpsDepositEnquirySnapshot.objects.create(
            request_id=rid,
            environment=env,
            from_date=from_date,
            to_date=to_date,
            trans_type=txn_type,
            agents=agent_list,
            current_balance=bal,
            currency=currency,
            response_code=code or ('000' if ok else ''),
            response_payload=resp,
            transaction_count=len(transactions),
            status='SUCCESS' if ok else 'FAILED',
            error_message='' if ok else f'Provider responseCode={code}',
            performed_by=admin_user if getattr(admin_user, 'pk', None) else None,
        )
        return {
            'snapshot': serialize_snapshot(shot, include_payload=True),
            'snapshot_id': shot.pk,
            'response': resp,
            'transactions': transactions,
            'current_balance': str(bal),
            'currency': currency,
            'agents': agent_list,
            'request_id': rid,
            'environment': env,
        }
    except BillAvenueClientError as exc:
        logger.warning('deposit enquiry failed: %s', exc)
        shot = BbpsDepositEnquirySnapshot.objects.create(
            request_id=rid,
            environment=env,
            from_date=from_date,
            to_date=to_date,
            trans_type=txn_type,
            agents=agent_list,
            current_balance=Decimal('0'),
            currency='INR',
            response_code='',
            response_payload={'error': str(exc)},
            transaction_count=0,
            status='FAILED',
            error_message=str(exc)[:2000],
            performed_by=admin_user if getattr(admin_user, 'pk', None) else None,
        )
        raise BillAvenueClientError(str(exc)) from exc
    except ValueError:
        raise
    except Exception as exc:
        logger.exception('deposit enquiry unexpected error')
        BbpsDepositEnquirySnapshot.objects.create(
            request_id=rid,
            environment=env,
            from_date=from_date,
            to_date=to_date,
            trans_type=txn_type,
            agents=agent_list,
            current_balance=Decimal('0'),
            currency='INR',
            response_code='',
            response_payload={'error': str(exc)},
            transaction_count=0,
            status='FAILED',
            error_message=str(exc)[:2000],
            performed_by=admin_user if getattr(admin_user, 'pk', None) else None,
        )
        raise


def list_deposit_enquiries(
    *,
    environment: str | None = None,
    page: int = 1,
    page_size: int = 25,
    date_from: str = '',
    date_to: str = '',
    status: str = '',
) -> dict[str, Any]:
    qs = BbpsDepositEnquirySnapshot.objects.filter(is_deleted=False).order_by('-created_at')
    if environment:
        qs = qs.filter(environment=normalize_billavenue_mode(environment))
    if date_from:
        qs = qs.filter(created_at__date__gte=date_from)
    if date_to:
        qs = qs.filter(created_at__date__lte=date_to)
    if status:
        qs = qs.filter(status=status.strip().upper())
    page = max(1, int(page or 1))
    page_size = min(100, max(1, int(page_size or 25)))
    total = qs.count()
    start = (page - 1) * page_size
    rows = [serialize_snapshot(s, include_payload=False) for s in qs[start : start + page_size]]
    # Include transaction preview counts only — full rows on detail
    return {
        'results': rows,
        'pagination': {
            'page': page,
            'page_size': page_size,
            'total': total,
            'total_pages': (total + page_size - 1) // page_size if page_size else 1,
        },
        'agent_options': list_agent_options(),
        'default_agents': default_agent_ids_for_active_env(),
        'environment': normalize_billavenue_mode(active_bbps_environment()),
    }


def get_deposit_enquiry(snapshot_id: int) -> dict[str, Any]:
    shot = BbpsDepositEnquirySnapshot.objects.filter(pk=snapshot_id, is_deleted=False).first()
    if not shot:
        raise LookupError('Deposit enquiry snapshot not found.')
    return serialize_snapshot(shot, include_payload=True)
