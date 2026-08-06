"""Excel export for wallet adjustment reports."""
from __future__ import annotations

import io

from django.http import HttpResponse
from openpyxl import Workbook

from apps.wallet_adjustments.services import serialize_adjustment


def build_adjustments_xlsx(rows, *, filename: str = 'wallet-adjustments.xlsx') -> HttpResponse:
    wb = Workbook()
    ws = wb.active
    ws.title = 'Adjustments'
    headers = [
        'Adjustment ID',
        'Date',
        'User ID',
        'Display code',
        'Phone',
        'User name',
        'Wallet',
        'Type',
        'Amount',
        'Balance before',
        'Balance after',
        'Reference',
        'Reason',
        'Remarks',
        'Adjusted by',
        'Status',
    ]
    ws.append(headers)
    for adj in rows:
        data = serialize_adjustment(adj)
        user = data.get('user') or {}
        adjusted_by = data.get('adjusted_by') or {}
        ws.append(
            [
                data.get('adjustment_id') or '',
                data.get('created_at') or '',
                user.get('user_id') or '',
                user.get('display_code') or '',
                user.get('phone') or '',
                user.get('name') or '',
                data.get('wallet_type') or '',
                data.get('adjustment_type') or '',
                data.get('amount') or '',
                data.get('balance_before') or '',
                data.get('balance_after') or '',
                data.get('reference_number') or '',
                data.get('reason_category_label') or data.get('reason_category') or '',
                (data.get('remarks') or '')[:1000],
                adjusted_by.get('name') or '',
                data.get('status') or '',
            ]
        )

    buffer = io.BytesIO()
    wb.save(buffer)
    buffer.seek(0)
    response = HttpResponse(
        buffer.getvalue(),
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    )
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response
