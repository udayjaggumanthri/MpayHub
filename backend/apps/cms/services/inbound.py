"""Inbound Fingpay Uber CMS wallet-check / wallet-debit / txn-result handlers."""
from __future__ import annotations

import json
import logging
import time
from decimal import Decimal, InvalidOperation

from apps.cms.models import CmsAgentProfile, CmsApiAuditLog, CmsTransaction
from apps.cms.services import wallet as wallet_svc
from apps.cms.services.crypto import scrub_cms, verify_inbound_hash
from apps.cms.services.registry import get_active_cms_config
from apps.core.exceptions import InsufficientBalance

logger = logging.getLogger(__name__)


def _extract_hash(headers: dict) -> str:
    return str(
        headers.get('hash')
        or headers.get('Hash')
        or headers.get('HTTP_HASH')
        or ''
    ).strip()


def _ip_allowed(client_ip: str | None, allowed: list) -> bool:
    if not allowed:
        return True
    if not client_ip:
        return False
    return str(client_ip) in {str(x) for x in allowed}


def _audit(
    *,
    endpoint: str,
    raw_body: str,
    response: dict,
    success: bool,
    client_ip: str | None,
    latency_ms: int | None = None,
    error: str = '',
    mid: str = '',
    fpid: str = '',
    debug: bool = False,
    headers: dict | None = None,
):
    try:
        body = json.loads(raw_body) if raw_body else {}
    except json.JSONDecodeError:
        body = {'_raw': (raw_body or '')[:500]}
    CmsApiAuditLog.objects.create(
        endpoint=endpoint,
        method='POST',
        merchant_transaction_id=mid[:64],
        fp_transaction_id=fpid[:128],
        http_status=200,
        latency_ms=latency_ms,
        success=success,
        error_message=(error or '')[:500],
        client_ip=client_ip,
        request_summary=scrub_cms(body if isinstance(body, dict) else {}),
        response_summary=scrub_cms(response if isinstance(response, dict) else {}),
        debug_enabled=debug,
        request_headers=scrub_cms(headers or {}) if debug else {},
        request_body=scrub_cms(body) if debug else {},
        response_body=scrub_cms(response) if debug else {},
    )


def handle_wallet_check(*, raw_body: str, headers: dict, client_ip: str | None = None) -> dict:
    t0 = time.monotonic()
    cfg = get_active_cms_config(require_secrets=True)
    if not _ip_allowed(client_ip, cfg.allowed_inbound_ips):
        resp = {'status': False, 'errorMessage': 'IP not allowed', 'bcBalances': []}
        _audit(
            endpoint='wallet-check',
            raw_body=raw_body,
            response=resp,
            success=False,
            client_ip=client_ip,
            error='IP not allowed',
            debug=cfg.debug_mode,
            headers=headers,
            latency_ms=int((time.monotonic() - t0) * 1000),
        )
        return resp

    provided = _extract_hash(headers)
    if not verify_inbound_hash(raw_body, cfg.secret_key, provided, template=cfg.hash_template):
        resp = {'status': False, 'errorMessage': 'Invalid hash', 'bcBalances': []}
        _audit(
            endpoint='wallet-check',
            raw_body=raw_body,
            response=resp,
            success=False,
            client_ip=client_ip,
            error='Invalid hash',
            debug=cfg.debug_mode,
            headers=headers,
            latency_ms=int((time.monotonic() - t0) * 1000),
        )
        return resp

    try:
        payload = json.loads(raw_body) if raw_body else {}
    except json.JSONDecodeError:
        payload = {}

    ids = payload.get('bcLoginIds') if isinstance(payload, dict) else []
    if not isinstance(ids, list):
        ids = []

    balances = []
    for bc_id in ids:
        login = str(bc_id or '').strip()
        if not login:
            continue
        agent = CmsAgentProfile.objects.filter(
            bc_login_id=login,
            status='active',
            is_deleted=False,
        ).select_related('user').first()
        if not agent:
            continue
        avail = wallet_svc.available_balance(agent.user)
        balances.append({'bcLoginId': login, 'balance': float(avail)})

    resp = {'status': True, 'errorMessage': 'Success', 'bcBalances': balances}
    _audit(
        endpoint='wallet-check',
        raw_body=raw_body,
        response=resp,
        success=True,
        client_ip=client_ip,
        debug=cfg.debug_mode,
        headers=headers,
        latency_ms=int((time.monotonic() - t0) * 1000),
    )
    return resp


def handle_wallet_debit(*, raw_body: str, headers: dict, client_ip: str | None = None) -> dict:
    t0 = time.monotonic()
    cfg = get_active_cms_config(require_secrets=True)
    if not _ip_allowed(client_ip, cfg.allowed_inbound_ips):
        resp = {'merchantTransactionId': '', 'status': False, 'errorMessage': 'IP not allowed'}
        _audit(
            endpoint='wallet-debit',
            raw_body=raw_body,
            response=resp,
            success=False,
            client_ip=client_ip,
            error='IP not allowed',
            debug=cfg.debug_mode,
            headers=headers,
            latency_ms=int((time.monotonic() - t0) * 1000),
        )
        return resp

    provided = _extract_hash(headers)
    if not verify_inbound_hash(raw_body, cfg.secret_key, provided, template=cfg.hash_template):
        resp = {'merchantTransactionId': '', 'status': False, 'errorMessage': 'Invalid hash'}
        _audit(
            endpoint='wallet-debit',
            raw_body=raw_body,
            response=resp,
            success=False,
            client_ip=client_ip,
            error='Invalid hash',
            debug=cfg.debug_mode,
            headers=headers,
            latency_ms=int((time.monotonic() - t0) * 1000),
        )
        return resp

    try:
        payload = json.loads(raw_body) if raw_body else {}
    except json.JSONDecodeError:
        payload = {}

    if not isinstance(payload, dict):
        payload = {}

    status_flag = str(payload.get('transactionStatus') or '').upper().strip()
    fpid = str(payload.get('fpTransactionId') or '').strip()
    bc_login = str(payload.get('bcLoginId') or '').strip()
    mid_in = str(payload.get('merchantTransactionId') or '').strip()
    error_message = str(payload.get('errorMessage') or '')
    remarks = str(payload.get('remarks') or '')
    txn_type = str(payload.get('typeOfTransaction') or 'CDC')

    try:
        amount = Decimal(str(payload.get('amount') or '0'))
    except (InvalidOperation, TypeError):
        amount = Decimal('0')

    if not fpid:
        resp = {'merchantTransactionId': '', 'status': False, 'errorMessage': 'fpTransactionId required'}
        _audit(
            endpoint='wallet-debit',
            raw_body=raw_body,
            response=resp,
            success=False,
            client_ip=client_ip,
            error='missing fpTransactionId',
            debug=cfg.debug_mode,
            headers=headers,
            latency_ms=int((time.monotonic() - t0) * 1000),
        )
        return resp

    # --- Initiate ---
    if status_flag == 'I':
        agent = CmsAgentProfile.objects.filter(
            bc_login_id=bc_login,
            status='active',
            is_deleted=False,
        ).select_related('user').first()
        if not agent:
            resp = {
                'merchantTransactionId': '',
                'status': False,
                'errorMessage': 'Unknown or inactive BC login',
            }
            _audit(
                endpoint='wallet-debit',
                raw_body=raw_body,
                response=resp,
                success=False,
                client_ip=client_ip,
                fpid=fpid,
                error='unknown bc',
                debug=cfg.debug_mode,
                headers=headers,
                latency_ms=int((time.monotonic() - t0) * 1000),
            )
            return resp

        existing = CmsTransaction.objects.filter(fp_transaction_id=fpid, is_deleted=False).first()
        if existing:
            resp = {
                'merchantTransactionId': existing.merchant_transaction_id,
                'status': True,
                'errorMessage': 'already initiated',
            }
            _audit(
                endpoint='wallet-debit',
                raw_body=raw_body,
                response=resp,
                success=True,
                client_ip=client_ip,
                mid=existing.merchant_transaction_id,
                fpid=fpid,
                debug=cfg.debug_mode,
                headers=headers,
                latency_ms=int((time.monotonic() - t0) * 1000),
            )
            return resp

        try:
            txn = wallet_svc.place_hold(
                user=agent.user,
                amount=amount,
                fp_transaction_id=fpid,
                bc_login_id=bc_login,
                meta=scrub_cms(
                    {
                        **payload,
                        'typeOfTransaction': txn_type,
                        'remarks': remarks,
                    }
                ),
            )
            if txn.type_of_transaction != txn_type:
                txn.type_of_transaction = txn_type[:16]
                txn.save(update_fields=['type_of_transaction', 'updated_at'])
            resp = {
                'merchantTransactionId': txn.merchant_transaction_id,
                'status': True,
                'errorMessage': error_message or 'Transaction initiated',
            }
            _audit(
                endpoint='wallet-debit',
                raw_body=raw_body,
                response=resp,
                success=True,
                client_ip=client_ip,
                mid=txn.merchant_transaction_id,
                fpid=fpid,
                debug=cfg.debug_mode,
                headers=headers,
                latency_ms=int((time.monotonic() - t0) * 1000),
            )
            return resp
        except InsufficientBalance as exc:
            resp = {
                'merchantTransactionId': '',
                'status': False,
                'errorMessage': 'Insufficient BC balance',
            }
            _audit(
                endpoint='wallet-debit',
                raw_body=raw_body,
                response=resp,
                success=False,
                client_ip=client_ip,
                fpid=fpid,
                error=str(exc),
                debug=cfg.debug_mode,
                headers=headers,
                latency_ms=int((time.monotonic() - t0) * 1000),
            )
            return resp

    # --- Success / Failure ---
    if status_flag in ('S', 'F'):
        txn = CmsTransaction.objects.filter(fp_transaction_id=fpid, is_deleted=False).first()
        if not txn and mid_in:
            txn = CmsTransaction.objects.filter(
                merchant_transaction_id=mid_in, is_deleted=False
            ).first()
        if not txn:
            resp = {
                'merchantTransactionId': mid_in,
                'status': False,
                'errorMessage': 'Transaction not found',
            }
            _audit(
                endpoint='wallet-debit',
                raw_body=raw_body,
                response=resp,
                success=False,
                client_ip=client_ip,
                mid=mid_in,
                fpid=fpid,
                error='txn not found',
                debug=cfg.debug_mode,
                headers=headers,
                latency_ms=int((time.monotonic() - t0) * 1000),
            )
            return resp

        if status_flag == 'S':
            if txn.status != 'success':
                wallet_svc.settle_hold(txn=txn)
            resp = {
                'merchantTransactionId': txn.merchant_transaction_id,
                'status': True,
                'errorMessage': 'received',
            }
        else:
            if txn.status == 'initiated':
                wallet_svc.release_hold(
                    txn=txn,
                    status='failed',
                    error_message=error_message or 'Transaction failed',
                )
            resp = {
                'merchantTransactionId': txn.merchant_transaction_id,
                'status': True,
                'errorMessage': 'received',
            }
        _audit(
            endpoint='wallet-debit',
            raw_body=raw_body,
            response=resp,
            success=True,
            client_ip=client_ip,
            mid=txn.merchant_transaction_id,
            fpid=fpid,
            debug=cfg.debug_mode,
            headers=headers,
            latency_ms=int((time.monotonic() - t0) * 1000),
        )
        return resp

    resp = {
        'merchantTransactionId': mid_in,
        'status': False,
        'errorMessage': f'Unknown transactionStatus {status_flag}',
    }
    _audit(
        endpoint='wallet-debit',
        raw_body=raw_body,
        response=resp,
        success=False,
        client_ip=client_ip,
        mid=mid_in,
        fpid=fpid,
        error='unknown status',
        debug=cfg.debug_mode,
        headers=headers,
        latency_ms=int((time.monotonic() - t0) * 1000),
    )
    return resp


def handle_txn_result(*, payload: dict, client_ip: str | None = None) -> dict:
    """Optional aggregator callback with final CMS transaction details."""
    payload = payload or {}
    fpid = str(
        payload.get('fingpayTransactionId')
        or payload.get('fpTransactionId')
        or ''
    ).strip()
    mid = str(
        payload.get('merchantTxnId')
        or payload.get('merchantTransactionId')
        or ''
    ).strip()
    txn = None
    if fpid:
        txn = CmsTransaction.objects.filter(fp_transaction_id=fpid, is_deleted=False).first()
    if not txn and mid:
        txn = CmsTransaction.objects.filter(merchant_transaction_id=mid, is_deleted=False).first()
    if not txn:
        return {'ok': False, 'message': 'txn not found'}

    meta = dict(txn.provider_meta or {})
    meta['txn_result'] = scrub_cms(payload)
    txn.provider_meta = meta
    txn.agent_login_id = str(payload.get('agentLoginId') or txn.agent_login_id or '')[:64]
    drop = payload.get('dropAmount')
    if drop is not None:
        try:
            txn.drop_amount = Decimal(str(drop))
        except (InvalidOperation, TypeError):
            pass
    status_code = str(payload.get('statusCode') or '').lower()
    if status_code == 'success' and txn.status == 'initiated':
        wallet_svc.settle_hold(txn=txn)
    elif status_code in ('failed', 'failure') and txn.status == 'initiated':
        wallet_svc.release_hold(
            txn=txn,
            status='failed',
            error_message=str(payload.get('errorMessage') or 'Callback failed'),
        )
    else:
        txn.save(update_fields=['provider_meta', 'agent_login_id', 'drop_amount', 'updated_at'])

    _audit(
        endpoint='txn-result',
        raw_body=json.dumps(payload, default=str),
        response={'ok': True, 'merchant_transaction_id': txn.merchant_transaction_id, 'status': txn.status},
        success=True,
        client_ip=client_ip,
        mid=txn.merchant_transaction_id,
        fpid=txn.fp_transaction_id,
        debug=False,
        headers={},
    )
    return {'ok': True, 'merchant_transaction_id': txn.merchant_transaction_id, 'status': txn.status}
