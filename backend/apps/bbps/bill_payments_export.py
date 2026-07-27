"""CSV export for BBPS bill payments list."""
from __future__ import annotations

import csv
from typing import Iterable

from django.http import StreamingHttpResponse

from apps.bbps.bill_payment_balances import bill_payment_balance_by_id
from apps.bbps.models import BillPayment


def bill_payment_csv_rows(payments: Iterable[BillPayment]) -> list[list]:
    payment_list = list(payments)
    balance_by_id = bill_payment_balance_by_id(payment_list)
    rows = []
    for p in payment_list:
        user = getattr(p, 'user', None)
        balances = balance_by_id.get(p.id, {'opening_balance': '', 'closing_balance': ''})
        rows.append(
            [
                p.created_at.isoformat() if p.created_at else '',
                p.service_id or '',
                p.request_id or '',
                str(p.amount),
                str(p.charge),
                str(p.total_deducted),
                p.bill_type or '',
                p.biller or '',
                p.biller_id or '',
                balances['opening_balance'],
                balances['closing_balance'],
                p.status or '',
                getattr(user, 'display_code', None)
                or getattr(user, 'user_id', None)
                or getattr(user, 'member_id', None)
                or '',
                getattr(user, 'phone', '') or '',
                getattr(user, 'role', '') or '',
            ]
        )
    return rows


BILL_PAYMENTS_CSV_HEADERS = [
    'created_at',
    'service_id',
    'request_id',
    'bill_amount',
    'charge',
    'total_deducted',
    'category',
    'biller',
    'biller_id',
    'opening_balance',
    'closing_balance',
    'status',
    'agent_user_code',
    'agent_mobile',
    'agent_role',
]


def stream_bill_payments_csv(filename_base: str, payments: Iterable[BillPayment]) -> StreamingHttpResponse:
    class Echo:
        def write(self, value):
            return value

    writer = csv.writer(Echo())

    def row_iter():
        yield writer.writerow(BILL_PAYMENTS_CSV_HEADERS)
        for row in bill_payment_csv_rows(payments):
            yield writer.writerow(row)

    response = StreamingHttpResponse(row_iter(), content_type='text/csv; charset=utf-8')
    response['Content-Disposition'] = f'attachment; filename="{filename_base}.csv"'
    return response
