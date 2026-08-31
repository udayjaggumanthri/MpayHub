"""Excel export for QR pay-in operations queue."""
from __future__ import annotations

import io

from django.http import HttpResponse
from openpyxl import Workbook


def build_qr_operations_xlsx(qs, *, filename: str = 'qr_payin_operations.xlsx') -> HttpResponse:
    wb = Workbook()
    ws = wb.active
    ws.title = 'QR Operations'
    headers = [
        'Transaction ID',
        'Created at',
        'Status',
        'User email',
        'Role',
        'QR account',
        'Submitted amount',
        'Approved amount',
        'UTR',
        'Payment date',
        'Failure reason',
    ]
    ws.append(headers)
    for lm in qs:
        ws.append(
            [
                lm.transaction_id or '',
                lm.created_at.isoformat() if lm.created_at else '',
                lm.status or '',
                getattr(lm.user, 'email', '') if lm.user else '',
                getattr(lm.user, 'role', '') if lm.user else '',
                lm.pay_in_qr_account.display_name if lm.pay_in_qr_account else '',
                str(lm.submitted_amount or ''),
                str(lm.amount or ''),
                lm.utr or '',
                str(lm.payment_date or ''),
                (lm.failure_reason or '')[:500],
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
