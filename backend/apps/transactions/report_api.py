"""Enterprise report payloads: summaries, joins, agent flags."""
from __future__ import annotations

import csv
from decimal import ROUND_HALF_UP, Decimal
from typing import Any, Iterable

from django.db.models import Count, QuerySet, Sum

from apps.authentication.models import User
from apps.fund_management.models import LoadMoney, Payout
from apps.bbps.models import BillPayment
from apps.transactions.agent_snapshot import (
    agent_row_from_user,
    card_last4_from_payment_meta,
    utr_or_bank_reference_from_payment_meta,
)
from apps.transactions.models import CommissionLedger, PassbookEntry, Transaction
from apps.transactions.reporting_scope import is_direct_subordinate
from apps.transactions.service_name_map import service_display_name


def money_str(v: Decimal | None) -> str:
    if v is None:
        return ''
    return str(Decimal(str(v)).quantize(Decimal('0.0001'), rounding=ROUND_HALF_UP))


def txn_status_financial_summary(qs: QuerySet) -> dict[str, Any]:
    """Totals by status for summary cards (amount + count)."""
    rows = (
        qs.values('status')
        .annotate(total=Sum('amount'), n=Count('id'))
        .order_by()
    )
    out = {
        'SUCCESS': {'amount': Decimal('0'), 'count': 0},
        'PENDING': {'amount': Decimal('0'), 'count': 0},
        'FAILED': {'amount': Decimal('0'), 'count': 0},
    }
    for row in rows:
        st = (row['status'] or 'PENDING').upper()
        if st not in out:
            out[st] = {'amount': Decimal('0'), 'count': 0}
        out[st]['amount'] = row['total'] or Decimal('0')
        out[st]['count'] = row['n'] or 0
    return {
        'by_status': {
            k: {'amount': money_str(v['amount']), 'count': v['count']} for k, v in out.items()
        },
        'total_count': qs.count(),
    }


def _agent_for_transaction(t: Transaction) -> User | None:
    return t.agent_user or t.user


def payin_rows_for_transactions(
    request,
    transactions: list[Transaction],
) -> list[dict[str, Any]]:
    viewer = request.user
    ids = [tx.service_id for tx in transactions]
    lm_map = {
        lm.transaction_id: lm
        for lm in LoadMoney.objects.filter(transaction_id__in=ids).select_related(
            'user', 'package', 'package__payment_gateway'
        )
    }
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
        customer_user_code = str(getattr(t.user, 'user_id', None) or '')
        provider_order_id = ''
        provider_payment_id = ''
        gateway_transaction_id = ''
        fee_breakdown_snapshot: dict | None = None
        mode = ''
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
                'fee_breakdown_snapshot': fee_breakdown_snapshot,
                'agent_details': agent_row_from_user(actor),
                'direct_subordinate': is_direct_subordinate(viewer, row_user)
                if getattr(viewer, 'role', '') == 'Super Distributor'
                else None,
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
        breakdown: list[dict[str, Any]] = []
        if p:
            breakdown = list(
                CommissionLedger.objects.filter(
                    reference_service_id=p.transaction_id,
                    user=viewer,
                ).values('amount', 'role_at_time', 'meta')[:50]
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
                'commission_breakdown': [
                    {
                        'amount': money_str(Decimal(str(x.get('amount') or '0'))),
                        'role_at_time': x.get('role_at_time'),
                        'slice': (x.get('meta') or {}).get('slice'),
                    }
                    for x in breakdown
                ],
                'agent_details': agent_row_from_user(actor),
                'direct_subordinate': is_direct_subordinate(viewer, row_user)
                if getattr(viewer, 'role', '') == 'Super Distributor'
                else None,
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
                'agent_details': agent_row_from_user(actor),
                'direct_subordinate': is_direct_subordinate(viewer, row_user)
                if getattr(viewer, 'role', '') == 'Super Distributor'
                else None,
            }
        )
    return out


def passbook_period_header(entries_qs: QuerySet) -> dict[str, Any]:
    """Summary across the full filtered passbook range (not just current page)."""
    agg = entries_qs.aggregate(
        total_credits=Sum('credit_amount'),
        total_debits=Sum('debit_amount'),
    )
    first = entries_qs.order_by('created_at').first()
    last = entries_qs.order_by('-created_at').first()
    credits = agg.get('total_credits') or Decimal('0')
    debits = agg.get('total_debits') or Decimal('0')
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
                'current_balance': money_str(e.closing_balance),
                'wallet_type': e.wallet_type,
                'service_charge': money_str(e.service_charge),
                'principal_amount': money_str(e.principal_amount) if e.principal_amount is not None else '',
                'agent_details': agent_row_from_user(agent_u),
                'owner_user_code': getattr(e.user, 'user_id', '') or '',
                'direct_subordinate': is_direct_subordinate(viewer, e.user)
                if getattr(viewer, 'role', '') == 'Super Distributor'
                else None,
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
