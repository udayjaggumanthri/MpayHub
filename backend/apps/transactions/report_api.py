"""Enterprise report payloads: summaries, joins, agent flags."""
from __future__ import annotations

import csv
import hashlib
from decimal import ROUND_HALF_UP, Decimal
from typing import Any, Iterable

from django.core.cache import cache
from django.db.models import Count, Max, Min, QuerySet, Sum

from apps.authentication.models import User
from apps.fund_management.models import LoadMoney, Payout
from apps.fund_management.payin_rail_labels import (
    payin_collection_method_label,
    payin_gateway_provider_name,
    payin_is_qr_rail,
    payin_rail_type_label,
)
from apps.fund_management.payin_receipt_context import build_payin_receipt_context
from apps.fund_management.serializers import payin_payment_mode_display
from apps.bbps.models import BillPayment
from apps.transactions.agent_snapshot import (
    agent_row_from_user,
    card_last4_from_payment_meta,
    utr_or_bank_reference_from_payment_meta,
)
from apps.transactions.models import CommissionLedger, PassbookEntry, Transaction
from apps.transactions.report_passbook_balances import (
    balance_fields_for_key,
    bbps_balance_map,
    payin_balance_map_for_load_money,
    payin_balance_map_for_transactions,
    payout_balance_map,
)
from apps.transactions.reporting_scope import direct_subordinate_id_set
from apps.transactions.service_name_map import service_display_name


def money_str(v: Decimal | None) -> str:
    if v is None:
        return ''
    return str(Decimal(str(v)).quantize(Decimal('0.0001'), rounding=ROUND_HALF_UP))


def txn_status_financial_summary(qs: QuerySet) -> dict[str, Any]:
    """Totals by status for summary cards (amount + count)."""
    return operational_status_financial_summary(qs, amount_field='amount')


def operational_status_financial_summary(qs: QuerySet, *, amount_field: str = 'amount') -> dict[str, Any]:
    """Totals by status for operational models (LoadMoney, Payout, BillPayment)."""
    rows = (
        qs.values('status')
        .annotate(total=Sum(amount_field), n=Count('id'))
        .order_by()
    )
    out = {
        'SUCCESS': {'amount': Decimal('0'), 'count': 0},
        'PENDING': {'amount': Decimal('0'), 'count': 0},
        'FAILED': {'amount': Decimal('0'), 'count': 0},
    }
    for row in rows:
        st = (row['status'] or 'PENDING').upper()
        if st == 'FAILURE':
            st = 'FAILED'
        if st not in out:
            out[st] = {'amount': Decimal('0'), 'count': 0}
        out[st]['amount'] = row['total'] or Decimal('0')
        out[st]['count'] = row['n'] or 0
    return {
        'by_status': {
            k: {'amount': money_str(v['amount']), 'count': v['count']} for k, v in out.items()
        },
        'total_count': sum(v['count'] for v in out.values()),
    }


REPORT_SUMMARY_CACHE_TIMEOUT = 30


def report_summary_cache_key(request, kind: str, scope: str) -> str:
    parts = []
    for key in sorted(request.query_params.keys()):
        if key in ('page', 'page_size', 'include_summary'):
            continue
        for val in request.query_params.getlist(key):
            parts.append(f'{key}={val}')
    digest = hashlib.sha256('&'.join(parts).encode('utf-8')).hexdigest()[:20]
    uid = getattr(request.user, 'pk', 'anon')
    return f'report:summary:{kind}:{scope}:{uid}:{digest}'


def cached_report_financial_summary(
    qs: QuerySet,
    request,
    kind: str,
    scope: str,
    *,
    amount_field: str = 'amount',
) -> dict[str, Any]:
    """30s cache of full-range pay-in/payout summary so the list page is not recosted."""
    key = report_summary_cache_key(request, kind, scope)
    cached = cache.get(key)
    if cached is not None:
        return cached
    summary = operational_status_financial_summary(qs, amount_field=amount_field)
    cache.set(key, summary, timeout=REPORT_SUMMARY_CACHE_TIMEOUT)
    return summary


def _agent_for_transaction(t: Transaction) -> User | None:
    return t.agent_user or t.user


def _batch_commission_breakdown(viewer, service_ids: list[str]) -> dict[str, list[dict[str, Any]]]:
    if not service_ids:
        return {}
    grouped: dict[str, list[dict[str, Any]]] = {}
    for row in CommissionLedger.objects.filter(
        reference_service_id__in=service_ids,
        user=viewer,
    ).values('reference_service_id', 'amount', 'role_at_time', 'meta'):
        sid = str(row.get('reference_service_id') or '')
        bucket = grouped.setdefault(sid, [])
        if len(bucket) < 50:
            bucket.append(row)
    return grouped


def _direct_subordinate_for_users(viewer, users: list[User | None]) -> dict[int, bool | None]:
    role = getattr(viewer, 'role', '') or ''
    if role != 'Super Distributor':
        return {}
    direct_ids = direct_subordinate_id_set(viewer)
    out: dict[int, bool | None] = {}
    for user in users:
        if user is None:
            continue
        out[int(user.pk)] = int(user.pk) in direct_ids
    return out


def payin_rows_for_transactions(
    request,
    transactions: list[Transaction],
) -> list[dict[str, Any]]:
    viewer = request.user
    ids = [tx.service_id for tx in transactions]
    lm_map = {
        lm.transaction_id: lm
        for lm in LoadMoney.objects.filter(transaction_id__in=ids).select_related(
            'user', 'package', 'package__payment_gateway', 'payment_gateway'
        )
    }
    balance_map = payin_balance_map_for_transactions(transactions)
    direct_flags = _direct_subordinate_for_users(viewer, [t.user for t in transactions])
    out = []
    for t in transactions:
        lm = lm_map.get(t.service_id)
        actor = _agent_for_transaction(t)
        gateway_meta: dict = {}
        payment_gateway_name = ''
        package_code = ''
        package_display_name = ''
        customer_name = ''
        customer_email = ''
        customer_phone = ''
        customer_user_code = str(
            getattr(t.user, 'display_code', None)
            or getattr(t.user, 'user_id', None)
            or getattr(t.user, 'member_id', None)
            or ''
        )
        provider_order_id = ''
        provider_payment_id = ''
        gateway_transaction_id = ''
        fee_breakdown_snapshot: dict | None = None
        mode = ''
        balances = balance_fields_for_key(
            balance_map, str(t.service_id or ''), int(getattr(t, 'user_id', 0) or 0)
        )
        opening_balance = balances['opening_balance']
        closing_balance = balances['closing_balance']
        if lm:
            gateway_meta = lm.payment_meta if isinstance(lm.payment_meta, dict) else {}
            mode = (lm.payment_method or '').replace('_', ' ') or '—'
            customer_name = (lm.customer_name or '').strip()
            customer_email = (lm.customer_email or '').strip()
            customer_phone = (lm.customer_phone or '').strip()
            provider_order_id = (lm.provider_order_id or '').strip()
            provider_payment_id = (lm.provider_payment_id or '').strip()
            gateway_transaction_id = (lm.gateway_transaction_id or '').strip()
            if isinstance(lm.fee_breakdown_snapshot, dict):
                fee_breakdown_snapshot = lm.fee_breakdown_snapshot
            pkg = lm.package
            if pkg:
                package_code = str(getattr(pkg, 'code', '') or '').strip()
                package_display_name = str(getattr(pkg, 'display_name', '') or '').strip()
            selected_pg = getattr(lm, 'payment_gateway', None)
            if selected_pg is not None and getattr(selected_pg, 'name', None):
                payment_gateway_name = str(selected_pg.name).strip()
            if not payment_gateway_name and pkg:
                pg = getattr(pkg, 'payment_gateway', None)
                if pg is not None and getattr(pg, 'name', None):
                    payment_gateway_name = str(pg.name).strip()
            if not payment_gateway_name and (lm.gateway or '').strip():
                payment_gateway_name = str(lm.gateway).replace('_', ' ').strip().title()

        if not customer_email:
            customer_email = (gateway_meta.get('rzp_email') or '').strip()
        if not customer_phone:
            raw_c = (gateway_meta.get('rzp_contact') or '').strip()
            digits = ''.join(c for c in raw_c if c.isdigit())
            if len(digits) >= 10:
                customer_phone = digits[-10:]
        if not customer_name and t.user_id:
            try:
                u = t.user
                prof = getattr(u, 'profile', None)
                if prof is not None:
                    customer_name = (getattr(prof, 'full_name', None) or '').strip()
                if not customer_name:
                    customer_name = (u.get_full_name() or '').strip()
            except Exception:
                pass
        if not customer_email and t.user_id:
            customer_email = (getattr(t.user, 'email', None) or '').strip()

        # Customer id for tables: prefer explicit customer phone, else wallet user code.
        customer_id = customer_phone or customer_user_code

        meta_utr = utr_or_bank_reference_from_payment_meta(gateway_meta)
        bank_ref_for_utr = meta_utr
        if not bank_ref_for_utr and gateway_transaction_id:
            ref = (t.reference or '').strip()
            if gateway_transaction_id != ref and not gateway_transaction_id.startswith('pay_'):
                bank_ref_for_utr = gateway_transaction_id

        card_last4 = (t.card_last4 or '').strip() or card_last4_from_payment_meta(gateway_meta)

        # Commission / fee-split snapshot: Admin-only (avoid leaking upline splits via API).
        if getattr(viewer, 'role', None) != 'Admin':
            fee_breakdown_snapshot = None

        row_user = t.user
        out.append(
            {
                'id': t.id,
                'created_at': t.created_at.isoformat() if t.created_at else None,
                'service_id': t.service_id,
                'service_name': service_display_name(t.service_id),
                'customer_id': customer_id,
                'customer_user_code': customer_user_code,
                'customer_name': customer_name,
                'customer_email': customer_email,
                'customer_phone': customer_phone,
                'mode': mode,
                'principal': money_str(t.amount),
                'service_charge': money_str(t.charge),
                'net_credit': money_str(t.net_amount if t.net_amount is not None else t.amount),
                'status': t.status,
                'reference': t.reference,
                'provider_order_id': provider_order_id,
                'provider_payment_id': provider_payment_id,
                'gateway_transaction_id': gateway_transaction_id,
                'bank_txn_id': (t.bank_txn_id or '').strip()
                or provider_payment_id
                or (t.reference or '').strip()
                or gateway_transaction_id,
                'card_last4': card_last4,
                'gateway_utr': bank_ref_for_utr,
                'gateway_payment_meta': gateway_meta,
                'package_id': lm.package_id if lm and lm.package_id else None,
                'package_code': package_code,
                'package_display_name': package_display_name,
                'payment_gateway_name': payment_gateway_name,
                'opening_balance': opening_balance,
                'closing_balance': closing_balance,
                'fee_breakdown_snapshot': fee_breakdown_snapshot,
                'agent_details': agent_row_from_user(actor),
                'direct_subordinate': direct_flags.get(int(row_user.pk)) if row_user else None,
            }
        )
    return out


def payout_rows_for_transactions(request, transactions: list[Transaction]) -> list[dict[str, Any]]:
    viewer = request.user
    ids = [tx.service_id for tx in transactions]
    po_map = {
        p.transaction_id: p
        for p in Payout.objects.filter(transaction_id__in=ids).select_related('bank_account', 'user')
    }
    balance_map = payout_balance_map(transactions)
    commission_by_sid = _batch_commission_breakdown(viewer, ids)
    direct_flags = _direct_subordinate_for_users(viewer, [t.user for t in transactions])
    out = []
    for t in transactions:
        p = po_map.get(t.service_id)
        bank_name = ''
        acct_masked = ''
        if p and p.bank_account:
            bank_name = getattr(p.bank_account, 'bank_name', '') or '—'
            acct = p.bank_account.account_number or ''
            acct_masked = f"****{acct[-4:]}" if len(acct) >= 4 else '****'
        actor = _agent_for_transaction(t)
        row_user = t.user
        breakdown = commission_by_sid.get(str(t.service_id or ''), [])
        balances = balance_fields_for_key(
            balance_map, str(t.service_id or ''), int(getattr(t, 'user_id', 0) or 0)
        )
        out.append(
            {
                'id': t.id,
                'created_at': t.created_at.isoformat() if t.created_at else None,
                'transaction_id': t.service_id,
                'payout_id': p.transaction_id if p else t.service_id,
                'service_name': service_display_name(t.service_id),
                'bank_name': bank_name,
                'account_number_masked': acct_masked,
                'transfer_amount': money_str(t.amount),
                'payout_charge': money_str(t.charge),
                'platform_fee': money_str(t.platform_fee or Decimal('0')),
                'net_debit': money_str(t.net_amount if t.net_amount is not None else t.amount),
                'status': t.status,
                'reference': t.reference,
                'opening_balance': balances['opening_balance'],
                'closing_balance': balances['closing_balance'],
                'commission_breakdown': [
                    {
                        'amount': money_str(Decimal(str(x.get('amount') or '0'))),
                        'role_at_time': x.get('role_at_time'),
                        'slice': (x.get('meta') or {}).get('slice'),
                    }
                    for x in breakdown
                ],
                'agent_details': agent_row_from_user(actor),
                'direct_subordinate': direct_flags.get(int(row_user.pk)) if row_user else None,
            }
        )
    return out


def bbps_rows_for_transactions(
    request,
    transactions: list[Transaction],
    *,
    serial_offset: int = 0,
) -> list[dict[str, Any]]:
    viewer = request.user
    ids = [tx.service_id for tx in transactions]
    bp_map = {b.service_id: b for b in BillPayment.objects.filter(service_id__in=ids)}
    balance_map = bbps_balance_map(transactions)
    direct_flags = _direct_subordinate_for_users(viewer, [t.user for t in transactions])
    out = []
    for idx, t in enumerate(transactions, start=1):
        bp = bp_map.get(t.service_id)
        actor = _agent_for_transaction(t)
        row_user = t.user
        st = (t.status or 'PENDING').upper()
        token = 'PENDING'
        if st == 'SUCCESS':
            token = 'SUCCESS'
        elif st == 'FAILED':
            token = 'FAILED'
        balances = balance_fields_for_key(
            balance_map, str(t.service_id or ''), int(getattr(t, 'user_id', 0) or 0)
        )
        out.append(
            {
                'serial': serial_offset + idx,
                'id': t.id,
                'created_at': t.created_at.isoformat() if t.created_at else None,
                'transaction_id': t.service_id,
                'request_id': t.request_id or (bp.request_id if bp else '') or '',
                'category': t.bill_type or (bp.bill_type if bp else '') or '',
                'biller': t.biller or (bp.biller if bp else '') or '',
                'bill_amount': money_str(t.amount),
                'platform_fee': money_str(t.charge),
                'status': t.status,
                'status_token': token,
                'service_name': service_display_name(t.service_id),
                'opening_balance': balances['opening_balance'],
                'closing_balance': balances['closing_balance'],
                'agent_details': agent_row_from_user(actor),
                'direct_subordinate': direct_flags.get(int(row_user.pk)) if row_user else None,
            }
        )
    return out


def payin_rows_from_load_money(
    request,
    items: list[LoadMoney],
    *,
    include_heavy_fields: bool = False,
) -> list[dict[str, Any]]:
    """Platform pay-in report rows from LoadMoney (matches dashboard counts)."""
    viewer = request.user
    balance_map = payin_balance_map_for_load_money(items)
    out = []
    for lm in items:
        actor = lm.user
        gateway_meta = lm.payment_meta if isinstance(lm.payment_meta, dict) else {}
        mode = payin_payment_mode_display(lm)
        customer_name = (lm.customer_name or '').strip()
        customer_email = (lm.customer_email or '').strip()
        customer_phone = (lm.customer_phone or '').strip()
        provider_order_id = (lm.provider_order_id or '').strip()
        provider_payment_id = (lm.provider_payment_id or '').strip()
        gateway_transaction_id = (lm.gateway_transaction_id or '').strip()
        fee_breakdown_snapshot = (
            lm.fee_breakdown_snapshot if isinstance(lm.fee_breakdown_snapshot, dict) else None
        )
        package_code = ''
        package_display_name = ''
        payment_gateway_name = ''
        pkg = lm.package
        if pkg:
            package_code = str(getattr(pkg, 'code', '') or '').strip()
            package_display_name = str(getattr(pkg, 'display_name', '') or '').strip()
        if payin_is_qr_rail(lm):
            payment_gateway_name = payin_collection_method_label(lm)
        else:
            payment_gateway_name = payin_gateway_provider_name(lm)
        rail_type_label = payin_rail_type_label(lm)

        balances = balance_fields_for_key(balance_map, str(lm.transaction_id or ''), int(lm.user_id))
        opening_balance = balances['opening_balance']
        closing_balance = balances['closing_balance']

        customer_user_code = str(
            getattr(lm.user, 'display_code', None)
            or getattr(lm.user, 'user_id', None)
            or getattr(lm.user, 'member_id', None)
            or ''
        )
        if not customer_email:
            customer_email = (gateway_meta.get('rzp_email') or '').strip()
        if not customer_phone:
            raw_c = (gateway_meta.get('rzp_contact') or '').strip()
            digits = ''.join(c for c in raw_c if c.isdigit())
            if len(digits) >= 10:
                customer_phone = digits[-10:]
        customer_id = customer_phone or customer_user_code

        meta_utr = utr_or_bank_reference_from_payment_meta(gateway_meta)
        bank_ref_for_utr = meta_utr
        if not bank_ref_for_utr and gateway_transaction_id:
            if not gateway_transaction_id.startswith('pay_'):
                bank_ref_for_utr = gateway_transaction_id

        card_last4 = card_last4_from_payment_meta(gateway_meta)
        if getattr(viewer, 'role', None) != 'Admin':
            fee_breakdown_snapshot = None

        qr_account_name = ''
        qr_acct = getattr(lm, 'pay_in_qr_account', None)
        if qr_acct is not None:
            qr_account_name = str(getattr(qr_acct, 'display_name', '') or '').strip()
        collection_rail = (getattr(lm, 'collection_rail', None) or 'gateway').strip().lower()
        utr_val = (getattr(lm, 'utr', None) or '').strip()
        submitted_amount = getattr(lm, 'submitted_amount', None)
        reject_reason = (getattr(lm, 'reject_reason', None) or lm.failure_reason or '').strip()
        receipt_details = build_payin_receipt_context(lm, request=request) if include_heavy_fields else {}

        tid = lm.transaction_id
        out.append(
            {
                'id': lm.id,
                'created_at': lm.created_at.isoformat() if lm.created_at else None,
                'service_id': tid,
                'service_name': service_display_name(tid),
                'customer_id': customer_id,
                'customer_user_code': customer_user_code,
                'customer_name': customer_name,
                'customer_email': customer_email,
                'customer_phone': customer_phone,
                'mode': mode,
                'principal': money_str(lm.amount),
                'service_charge': money_str(lm.charge),
                'net_credit': money_str(lm.net_credit),
                'status': lm.status,
                'collection_rail': collection_rail,
                'rail_type_label': rail_type_label,
                'utr': utr_val,
                'qr_account_name': qr_account_name,
                'submitted_amount': money_str(submitted_amount) if submitted_amount is not None else '',
                'reject_reason': reject_reason,
                'receipt_details': receipt_details if include_heavy_fields else None,
                'proof_receipt_url': (receipt_details.get('proof_receipt_url') or '') if include_heavy_fields else '',
                'reference': gateway_transaction_id or provider_payment_id or '',
                'provider_order_id': provider_order_id,
                'provider_payment_id': provider_payment_id,
                'gateway_transaction_id': gateway_transaction_id,
                'bank_txn_id': provider_payment_id or gateway_transaction_id or '',
                'card_last4': card_last4,
                'gateway_utr': bank_ref_for_utr,
                'gateway_payment_meta': gateway_meta if include_heavy_fields else {},
                'package_id': lm.package_id if lm.package_id else None,
                'package_code': package_code,
                'package_display_name': package_display_name,
                'payment_gateway_name': payment_gateway_name,
                'opening_balance': opening_balance,
                'closing_balance': closing_balance,
                'fee_breakdown_snapshot': fee_breakdown_snapshot,
                'agent_details': agent_row_from_user(actor),
                'direct_subordinate': None,
            }
        )
    return out


def payout_rows_from_payout(request, items: list[Payout]) -> list[dict[str, Any]]:
    viewer = request.user
    balance_map = payout_balance_map(items)
    commission_by_sid = _batch_commission_breakdown(viewer, [str(p.transaction_id or '') for p in items])
    out = []
    for p in items:
        bank_name = ''
        acct_masked = ''
        if p.bank_account:
            bank_name = getattr(p.bank_account, 'bank_name', '') or '—'
            acct = p.bank_account.account_number or ''
            acct_masked = f"****{acct[-4:]}" if len(acct) >= 4 else '****'
        actor = p.user
        breakdown = commission_by_sid.get(str(p.transaction_id or ''), [])
        balances = balance_fields_for_key(balance_map, str(p.transaction_id or ''), int(p.user_id))
        out.append(
            {
                'id': p.id,
                'created_at': p.created_at.isoformat() if p.created_at else None,
                'transaction_id': p.transaction_id,
                'payout_id': p.transaction_id,
                'service_name': service_display_name(p.transaction_id),
                'bank_name': bank_name,
                'account_number_masked': acct_masked,
                'transfer_amount': money_str(p.amount),
                'payout_charge': money_str(p.charge),
                'platform_fee': money_str(p.platform_fee or Decimal('0')),
                'net_debit': money_str(p.total_deducted),
                'status': p.status,
                'reference': p.gateway_transaction_id or '',
                'opening_balance': balances['opening_balance'],
                'closing_balance': balances['closing_balance'],
                'commission_breakdown': [
                    {
                        'amount': money_str(Decimal(str(x.get('amount') or '0'))),
                        'role_at_time': x.get('role_at_time'),
                        'slice': (x.get('meta') or {}).get('slice'),
                    }
                    for x in breakdown
                ],
                'agent_details': agent_row_from_user(actor),
                'direct_subordinate': None,
            }
        )
    return out


def bbps_rows_from_bill_payment(
    request,
    items: list[BillPayment],
    *,
    serial_offset: int = 0,
) -> list[dict[str, Any]]:
    viewer = request.user
    balance_map = bbps_balance_map(items)
    out = []
    for idx, bp in enumerate(items, start=1):
        actor = bp.user
        st = (bp.status or 'PENDING').upper()
        token = 'PENDING'
        if st == 'SUCCESS':
            token = 'SUCCESS'
        elif st == 'FAILED':
            token = 'FAILED'
        balances = balance_fields_for_key(balance_map, str(bp.service_id or ''), int(bp.user_id))
        out.append(
            {
                'serial': serial_offset + idx,
                'id': bp.id,
                'created_at': bp.created_at.isoformat() if bp.created_at else None,
                'transaction_id': bp.service_id,
                'request_id': bp.request_id or '',
                'category': bp.bill_type or '',
                'biller': bp.biller or '',
                'bill_amount': money_str(bp.amount),
                'platform_fee': money_str(bp.charge),
                'status': bp.status,
                'status_token': token,
                'service_name': service_display_name(bp.service_id),
                'opening_balance': balances['opening_balance'],
                'closing_balance': balances['closing_balance'],
                'agent_details': agent_row_from_user(actor),
                'direct_subordinate': None,
            }
        )
    return out


def passbook_period_header(entries_qs: QuerySet) -> dict[str, Any]:
    """Summary across the full filtered passbook range (not just current page)."""
    agg = entries_qs.aggregate(
        total_credits=Sum('credit_amount'),
        total_debits=Sum('debit_amount'),
        first_at=Min('created_at'),
        last_at=Max('created_at'),
    )
    credits = agg.get('total_credits') or Decimal('0')
    debits = agg.get('total_debits') or Decimal('0')
    first_at = agg.get('first_at')
    last_at = agg.get('last_at')
    ob = Decimal('0')
    cb = ob
    if first_at is not None:
        rows = list(
            entries_qs.filter(created_at__in={first_at, last_at}).only(
                'created_at', 'opening_balance', 'closing_balance'
            )
        )
        by_ts = {}
        for row in rows:
            by_ts.setdefault(row.created_at, row)
        first = by_ts.get(first_at)
        last = by_ts.get(last_at) or first
        ob = first.opening_balance if first else Decimal('0')
        cb = last.closing_balance if last else ob
    return {
        'opening_balance': money_str(ob),
        'total_credits': money_str(credits),
        'total_debits': money_str(debits),
        'closing_balance': money_str(cb),
    }


def passbook_rows(request, entries: list[PassbookEntry]) -> list[dict[str, Any]]:
    viewer = request.user
    direct_flags = _direct_subordinate_for_users(viewer, [e.user for e in entries])
    rows = []
    for e in entries:
        init = e.initiator_user
        agent_u = init or e.user
        rows.append(
            {
                'id': e.id,
                'created_at': e.created_at.isoformat() if e.created_at else None,
                'service_type': e.service,
                'service_id': e.service_id,
                'service_name': service_display_name(e.service_id),
                'description': e.description,
                'debit': money_str(e.debit_amount),
                'credit': money_str(e.credit_amount),
                'opening_balance': money_str(e.opening_balance),
                'current_balance': money_str(e.closing_balance),
                'closing_balance': money_str(e.closing_balance),
                'wallet_type': e.wallet_type,
                'service_charge': money_str(e.service_charge),
                'principal_amount': money_str(e.principal_amount) if e.principal_amount is not None else '',
                'agent_details': agent_row_from_user(agent_u),
                'owner_user_code': (
                    getattr(e.user, 'display_code', None)
                    or getattr(e.user, 'user_id', None)
                    or getattr(e.user, 'member_id', None)
                    or ''
                ),
                'direct_subordinate': direct_flags.get(int(e.user_id)) if e.user_id else None,
            }
        )
    return rows


def stream_csv(filename_base: str, headers: list[str], rows: Iterable[list[Any]]):
    from django.http import StreamingHttpResponse

    class Echo:
        def write(self, value):
            return value

    writer = csv.writer(Echo())

    def row_iter():
        yield writer.writerow(headers)
        for r in rows:
            yield writer.writerow(r)

    response = StreamingHttpResponse(row_iter(), content_type='text/csv; charset=utf-8')
    response['Content-Disposition'] = f'attachment; filename="{filename_base}.csv"'
    return response
