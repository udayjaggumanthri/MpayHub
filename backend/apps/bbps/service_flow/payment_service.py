from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from django.conf import settings
from django.db import transaction as db_transaction
from django.utils import timezone

from apps.bbps.models import (
    BillPayment,
    BbpsApiAuditLog,
    BbpsBillerMaster,
    BbpsFetchSession,
    BbpsPaymentAttempt,
    BbpsStatusPollLog,
)
from apps.bbps.service_flow.compliance import (
    compute_ccf1_if_required,
    enforce_cash_pan_rule,
    enforce_biller_mode_channel_constraints,
    enforce_fetch_pay_linkage,
    enforce_plan_mdm_requirement,
    validate_channel_device_fields,
)
from apps.bbps.service_flow.commission_service import resolve_commission_for_payment
from apps.core.exceptions import InsufficientBalance, TransactionFailed
from apps.integrations.bbps_client import BBPSClient, extract_biller_response_dict
from apps.transactions.agent_snapshot import passbook_initiator_db_fields, transaction_agent_db_fields
from apps.transactions.models import PassbookEntry, Transaction
from apps.wallets.models import Wallet


def _to_paise(amount) -> int:
    return int((Decimal(str(amount)) * Decimal('100')).to_integral_value())


def _json_safe(value):
    """Recursively convert values so PostgreSQL JSONField / psycopg2 can persist them."""
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(v) for v in value]
    return value


@db_transaction.atomic
def process_bill_payment_flow(*, user, bill_data: dict) -> dict:
    amount = Decimal(str(bill_data['amount']))
    biller_id = str(bill_data.get('biller_id') or '').strip()
    if not biller_id:
        raise TransactionFailed('biller_id is required for BillAvenue payment flow.')
    biller = BbpsBillerMaster.objects.filter(biller_id=biller_id, is_deleted=False).first()
    if not biller:
        raise TransactionFailed(f'Biller {biller_id} not found in MDM cache. Run sync first.')
    if str(biller.biller_status or '').upper() not in ('ACTIVE', 'ENABLED', 'FLUCTUATING'):
        raise TransactionFailed(f'Biller {biller_id} is not active for payment.')
    if 'biller_adhoc' not in bill_data:
        bill_data['biller_adhoc'] = bool(getattr(biller, 'biller_adhoc', False))
    agent_device_info = bill_data.get('agent_device_info') or {}
    payment_channel = str(bill_data.get('init_channel') or '').strip().upper()
    validate_channel_device_fields(init_channel=payment_channel, agent_device_info=agent_device_info)
    enforce_biller_mode_channel_constraints(
        biller=biller,
        payment_mode=str(bill_data.get('payment_mode') or ''),
        payment_channel=payment_channel,
        amount=amount,
    )
    enforce_plan_mdm_requirement(
        biller=biller,
        plan_id=str(bill_data.get('plan_id') or ''),
    )
    fetch_session = enforce_fetch_pay_linkage(
        user=user,
        biller=biller,
        input_params=(bill_data.get('input_params') or []),
        request_id=str(bill_data.get('request_id') or ''),
    )
    # Bill Pay (inner + outer transport) must use the same requestId as the successful bill fetch (Postman UAT).
    if fetch_session and str(getattr(fetch_session, 'request_id', '') or '').strip():
        fetch_rid = str(fetch_session.request_id).strip()
        bill_data['request_id'] = fetch_rid
    # Keep bill-pay request aligned with bill-fetch snapshot.
    if fetch_session and isinstance(getattr(fetch_session, 'input_params', None), dict):
        inp = fetch_session.input_params or {}
        if not isinstance(bill_data.get('agent_device_info'), dict) or not bill_data.get('agent_device_info'):
            bill_data['agent_device_info'] = inp.get('agentDeviceInfo') or {}
        if not isinstance(bill_data.get('customer_info'), dict) or not bill_data.get('customer_info'):
            bill_data['customer_info'] = inp.get('customerInfo') or {}
    if fetch_session and isinstance(getattr(fetch_session, 'biller_response', None), dict):
        raw_fetch = fetch_session.biller_response or {}
        br = extract_biller_response_dict(raw_fetch)
        if br:
            bill_data['biller_response'] = br
    payer_display = (getattr(user, 'get_full_name', lambda: '')() or '').strip() or str(
        getattr(user, 'phone', '') or ''
    ).strip()
    if payer_display:
        bill_data['remitter_name'] = str(bill_data.get('remitter_name') or '').strip() or payer_display
    payer_email = str(getattr(user, 'email', '') or '').strip()
    if payer_email:
        bill_data.setdefault('payer_email', payer_email)
    charge_info = resolve_commission_for_payment(amount=amount, bill_data=bill_data)
    enforce_cash_pan_rule(
        amount_paise=_to_paise(amount),
        payment_mode=str(bill_data.get('payment_mode') or ''),
        customer_info=(bill_data.get('customer_info') or {}),
    )
    computed_charge = Decimal(str(charge_info.get('computed_charge') or charge_info.get('charge') or 0))
    if getattr(settings, 'BBPS_COMMISSION_FINANCIAL_IMPACT_ENABLED', False):
        applied_charge = Decimal(str(charge_info.get('charge') or 0))
    else:
        applied_charge = Decimal(str(getattr(settings, 'BBPS_SERVICE_CHARGE', 0)))
    charge_info['charge'] = applied_charge
    charge_info['total_deducted'] = amount + applied_charge
    charge_info['shadow_mode'] = not bool(getattr(settings, 'BBPS_COMMISSION_FINANCIAL_IMPACT_ENABLED', False))
    total = charge_info['total_deducted']

    bbps_wallet = Wallet.get_wallet(user, 'bbps')
    if bbps_wallet.balance < total:
        raise InsufficientBalance(
            f'Insufficient BBPS wallet balance. Available: Rs {bbps_wallet.balance}, Required: Rs {total}'
        )

    service_id = bill_data.get('service_id') or ''
    BbpsApiAuditLog.objects.create(
        endpoint_name='commission_resolution',
        request_id=str(bill_data.get('request_id') or ''),
        service_id=service_id,
        status_code='000',
        latency_ms=0,
        success=True,
        request_meta={
            'biller_id': bill_data.get('biller_id') or '',
            'provider_id': bill_data.get('provider_id') or None,
            'bill_type': bill_data.get('bill_type') or '',
        },
        response_meta={
            'commission_rule_code': charge_info.get('commission_rule_code') or '',
            'computed_charge': str(computed_charge),
            'applied_charge': str(charge_info.get('charge') or 0),
            'total_deducted': str(charge_info.get('total_deducted') or 0),
            'shadow_mode': charge_info.get('shadow_mode'),
        },
        error_message='',
    )
    idem = f"{user.pk}|{bill_data.get('biller_id','')}|{bill_data.get('bill_type','')}|{_to_paise(amount)}|{bill_data.get('payment_mode','')}|{service_id}"
    attempt, created = BbpsPaymentAttempt.objects.get_or_create(
        idempotency_key=idem,
        defaults={
            'user': user,
            'service_id': service_id,
            'biller_id': bill_data.get('biller_id', ''),
            'amount_paise': _to_paise(amount),
            'payment_mode': bill_data.get('payment_mode', ''),
            'payment_channel': bill_data.get('init_channel', ''),
            'commission_rule_code': charge_info.get('commission_rule_code') or '',
            'commission_rule_snapshot': _json_safe(charge_info.get('commission_rule_snapshot') or {}),
            'commission_amount': charge_info['charge'],
            'status': 'PAY_INITIATED',
            'fetch_session': fetch_session,
        },
    )
    if not created and attempt.status in ('SUCCESS', 'AWAITED', 'PAY_INITIATED'):
        return {'attempt': attempt, 'bill_payment': attempt.bill_payment, 'idempotent': True}

    bill_payment = BillPayment.objects.create(
        user=user,
        biller=bill_data.get('biller', ''),
        biller_id=bill_data.get('biller_id', ''),
        bill_type=bill_data.get('bill_type', ''),
        amount=amount,
        charge=charge_info['charge'],
        total_deducted=total,
        commission_rule_code=charge_info.get('commission_rule_code') or '',
        commission_rule_snapshot=_json_safe(charge_info.get('commission_rule_snapshot') or {}),
        commission_amount=charge_info['charge'],
        status='PENDING',
        service_id=service_id,
        request_id=bill_data.get('request_id') or None,
    )

    attempt.bill_payment = bill_payment
    attempt.request_id = bill_payment.request_id or ''
    safe_bill = {k: v for k, v in bill_data.items() if str(k).lower() != 'mpin'}
    attempt.request_payload = _json_safe(dict(safe_bill))
    attempt.status = 'PAY_INITIATED'
    attempt.fetch_session = fetch_session
    attempt.commission_rule_code = charge_info.get('commission_rule_code') or ''
    attempt.commission_rule_snapshot = _json_safe(charge_info.get('commission_rule_snapshot') or {})
    attempt.commission_amount = charge_info['charge']
    attempt.save(
        update_fields=[
            'bill_payment',
            'request_id',
            'request_payload',
            'status',
            'fetch_session',
            'commission_rule_code',
            'commission_rule_snapshot',
            'commission_amount',
            'updated_at',
        ]
    )

    client = BBPSClient()
    ccf1 = compute_ccf1_if_required(biller=biller, amount_paise=_to_paise(amount))
    if ccf1:
        bill_data.setdefault('bill_payment_payload', {})
        payload = bill_data['bill_payment_payload']
        amount_info = payload.get('amountInfo') if isinstance(payload, dict) else None
        if not isinstance(amount_info, dict):
            amount_info = {}
        if 'CCF1' not in amount_info:
            amount_info['CCF1'] = str(ccf1.ccf1_paise)
        payload['amountInfo'] = amount_info
        bill_data['bill_payment_payload'] = payload
    try:
        payment_result = client.process_payment(bill_payment.service_id, bill_payment.request_id, amount, bill_data)
    finally:
        if fetch_session:
            BbpsFetchSession.objects.filter(pk=fetch_session.pk, status='FETCHED').update(status='CONSUMED')
    status = payment_result.get('status')

    if status == 'SUCCESS':
        bill_payment.status = 'SUCCESS'
        bill_payment.save(update_fields=['status'])

        opening_balance = bbps_wallet.balance
        bbps_wallet.debit(total, reference=bill_payment.service_id)
        closing_balance = bbps_wallet.balance

        Transaction.objects.create(
            user=user,
            transaction_type='bbps',
            amount=amount,
            charge=charge_info['charge'],
            status='SUCCESS',
            service_id=bill_payment.service_id,
            request_id=bill_payment.request_id,
            bill_type=bill_data.get('bill_type', ''),
            biller=bill_data.get('biller', ''),
            service_family='bbps',
            **transaction_agent_db_fields(user),
        )

        PassbookEntry.objects.create(
            user=user,
            wallet_type='bbps',
            service='BBPS',
            service_id=bill_payment.service_id,
            description=(
                f"PAID FOR {bill_data.get('bill_type', 'BILL PAYMENT')}, BILLER: {bill_data.get('biller', 'N/A')}, "
                f"AMOUNT: {amount}, CHARGE: {charge_info['charge']}"
            ),
            debit_amount=total,
            credit_amount=Decimal('0.00'),
            opening_balance=opening_balance,
            closing_balance=closing_balance,
            service_charge=charge_info['charge'],
            principal_amount=amount,
            **passbook_initiator_db_fields(user),
        )

        attempt.status = 'SUCCESS'
        attempt.txn_ref_id = payment_result.get('txn_ref_id') or ''
        attempt.approval_ref_number = payment_result.get('approval_ref_number') or ''
        attempt.response_payload = _json_safe(payment_result.get('response_payload') or {})
        attempt.settled_at = timezone.now()
        attempt.save(update_fields=['status', 'txn_ref_id', 'approval_ref_number', 'response_payload', 'settled_at', 'updated_at'])
        return {'attempt': attempt, 'bill_payment': bill_payment, 'idempotent': False}

    if status == 'AWAITED':
        attempt.status = 'AWAITED'
        attempt.txn_ref_id = payment_result.get('txn_ref_id') or ''
        attempt.approval_ref_number = payment_result.get('approval_ref_number') or ''
        attempt.response_payload = _json_safe(payment_result.get('response_payload') or {})
        attempt.save(update_fields=['status', 'txn_ref_id', 'approval_ref_number', 'response_payload', 'updated_at'])
        bill_payment.status = 'PENDING'
        bill_payment.save(update_fields=['status'])
        BbpsStatusPollLog.objects.create(
            attempt=attempt,
            track_type='REQUEST_ID',
            track_value=bill_payment.request_id or bill_payment.service_id,
            response_code='AWAITED',
            txn_status='AWAITED',
            response_payload=_json_safe(payment_result.get('response_payload') or {}),
        )
        return {'attempt': attempt, 'bill_payment': bill_payment, 'idempotent': False}

    attempt.status = 'FAILED'
    attempt.last_error_message = payment_result.get('message') or 'Payment failed'
    attempt.response_payload = _json_safe(payment_result.get('response_payload') or {})
    attempt.save(update_fields=['status', 'last_error_message', 'response_payload', 'updated_at'])
    bill_payment.status = 'FAILED'
    bill_payment.failure_reason = payment_result.get('message') or 'Payment failed'
    bill_payment.save(update_fields=['status', 'failure_reason'])
    msg = bill_payment.failure_reason or 'Payment failed'
    if fetch_session:
        msg = f'{msg} Fetch the bill again before retrying payment.'
    raise TransactionFailed(msg)
