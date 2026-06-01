"""Attach passbook opening/closing balances to BBPS bill payment list payloads."""
from __future__ import annotations

from apps.bbps.models import BillPayment
from apps.transactions.report_passbook_balances import balance_fields_for_key, bbps_balance_map


def bill_payment_balance_by_id(payments: list[BillPayment]) -> dict[int, dict[str, str]]:
    balance_map = bbps_balance_map(payments)
    out: dict[int, dict[str, str]] = {}
    for payment in payments:
        out[payment.id] = balance_fields_for_key(
            balance_map, str(payment.service_id or ''), int(payment.user_id)
        )
    return out


def enrich_serialized_bill_payments(
    payments: list[BillPayment],
    rows: list[dict],
) -> list[dict]:
    by_id = bill_payment_balance_by_id(payments)
    enriched: list[dict] = []
    for row in rows:
        item = dict(row)
        fields = by_id.get(item.get('id'), {'opening_balance': '', 'closing_balance': ''})
        item['opening_balance'] = fields['opening_balance']
        item['closing_balance'] = fields['closing_balance']
        enriched.append(item)
    return enriched
