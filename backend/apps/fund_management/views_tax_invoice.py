"""Admin tax-invoice APIs for Partner pay-in reports."""
from __future__ import annotations

from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.core.permissions import IsAdmin
from apps.fund_management.models import LoadMoney, PayinTaxInvoice
from apps.fund_management.payin_tax_invoice import (
    assign_invoice_number,
    build_draft_from_load_money,
    company_payload,
    extract_payin_references,
    get_or_create_invoice_settings,
    recompute_payload,
    serialize_saved,
    settings_public,
)


def _ok(data, message='OK', code=status.HTTP_200_OK):
    return Response({'success': True, 'data': data, 'message': message, 'errors': []}, status=code)


def _err(message, errors=None, code=status.HTTP_400_BAD_REQUEST):
    return Response(
        {'success': False, 'data': None, 'message': message, 'errors': errors or [message]},
        status=code,
    )


@api_view(['GET', 'PATCH'])
@permission_classes([IsAuthenticated, IsAdmin])
def invoice_settings_view(request):
    """GET/PATCH /api/admin/invoice-settings/ — company branding for tax invoices."""
    row = get_or_create_invoice_settings()
    if request.method == 'GET':
        return _ok({'settings': settings_public(row, request)})

    data = request.data
    text_fields = {
        'legalName': 'legal_name',
        'companyLine': 'company_line',
        'address': 'address',
        'phone': 'phone',
        'email': 'email',
        'gstNumber': 'gst_number',
        'declaration': 'declaration',
    }
    for camel, field in text_fields.items():
        if camel in data:
            setattr(row, field, str(data.get(camel) or '').strip())
        elif field in data:
            setattr(row, field, str(data.get(field) or '').strip())

    if 'gstRatePercent' in data or 'gst_rate_percent' in data:
        raw = data.get('gstRatePercent', data.get('gst_rate_percent'))
        try:
            rate = float(raw)
        except (TypeError, ValueError):
            return _err('gstRatePercent must be a number.')
        if rate < 0 or rate > 100:
            return _err('gstRatePercent must be between 0 and 100.')
        row.gst_rate_percent = rate

    if 'invoiceNextNumber' in data or 'invoice_next_number' in data:
        raw = data.get('invoiceNextNumber', data.get('invoice_next_number'))
        try:
            nxt = int(raw)
        except (TypeError, ValueError):
            return _err('invoiceNextNumber must be a positive integer.')
        if nxt < 1:
            return _err('invoiceNextNumber must be at least 1.')
        row.invoice_next_number = nxt

    remove_signature = str(data.get('removeSignature') or data.get('remove_signature') or '').lower() in (
        '1', 'true', 'yes',
    )
    remove_stamp = str(data.get('removeStamp') or data.get('remove_stamp') or '').lower() in (
        '1', 'true', 'yes',
    )
    if remove_signature and row.signature:
        row.signature.delete(save=False)
        row.signature = None
    if remove_stamp and row.stamp:
        row.stamp.delete(save=False)
        row.stamp = None

    signature_file = request.FILES.get('signature') or request.FILES.get('signatureFile')
    stamp_file = request.FILES.get('stamp') or request.FILES.get('stampFile')
    if signature_file is not None:
        if row.signature:
            row.signature.delete(save=False)
        row.signature = signature_file
    if stamp_file is not None:
        if row.stamp:
            row.stamp.delete(save=False)
        row.stamp = stamp_file

    row.save()
    return _ok({'settings': settings_public(row, request)}, message='Invoice settings saved')


def _load_money_for_admin(transaction_id: str):
    return LoadMoney.objects.filter(transaction_id=transaction_id, is_deleted=False).first()


def _existing_invoice(load_money):
    return PayinTaxInvoice.objects.filter(load_money=load_money, is_deleted=False).first()


def _persist_invoice(load_money, invoice_body, *, user, request=None, existing=None):
    settings = get_or_create_invoice_settings()
    existing = existing or _existing_invoice(load_money)
    existing_number = existing.invoice_number if existing else ''
    body = dict(invoice_body or {})
    body['company'] = company_payload(settings, request)
    body.update(extract_payin_references(load_money))
    if existing_number:
        body['invoiceNumber'] = existing_number
    computed = recompute_payload(body, settings.gst_rate_percent)
    number = assign_invoice_number(existing_number, when=load_money.created_at)
    computed['invoiceNumber'] = number
    computed['saved'] = True
    if existing is None:
        return PayinTaxInvoice.objects.create(
            load_money=load_money,
            invoice_number=number,
            payload=computed,
            created_by=user,
        )
    existing.payload = computed
    existing.invoice_number = number
    existing.save(update_fields=['payload', 'invoice_number', 'updated_at'])
    return existing


def ensure_invoice_for_completed(load_money, *, user, request=None):
    """Completed SUCCESS pay-ins get a PRA invoice number on first open."""
    existing = _existing_invoice(load_money)
    if existing is not None:
        return existing
    if (load_money.status or '').upper() != 'SUCCESS':
        return None
    draft = build_draft_from_load_money(load_money, request)
    return _persist_invoice(load_money, draft, user=user, request=request, existing=None)


@api_view(['GET', 'PUT'])
@permission_classes([IsAuthenticated, IsAdmin])
def payin_tax_invoice_view(request, transaction_id: str):
    """GET/PUT /api/reports/payin/<transaction_id>/tax-invoice/"""
    lm = _load_money_for_admin(transaction_id)
    if lm is None:
        return _err('Pay-in transaction not found.', code=status.HTTP_404_NOT_FOUND)

    if request.method == 'GET':
        existing = ensure_invoice_for_completed(lm, user=request.user, request=request)
        if existing is not None:
            return _ok({'invoice': serialize_saved(existing, request), 'transactionId': lm.transaction_id})
        draft = build_draft_from_load_money(lm, request)
        return _ok({'invoice': draft, 'transactionId': lm.transaction_id})

    body = request.data if isinstance(request.data, dict) else {}
    invoice_body = body.get('invoice') if isinstance(body.get('invoice'), dict) else body
    existing = _existing_invoice(lm)
    row = _persist_invoice(lm, invoice_body, user=request.user, request=request, existing=existing)

    return _ok(
        {'invoice': serialize_saved(row, request), 'transactionId': lm.transaction_id},
        message='Tax invoice saved',
    )
