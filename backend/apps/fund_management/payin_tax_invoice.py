"""Build and recompute LMS-style tax invoices for Partner pay-in rows."""
from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP
from typing import Any

from django.db import transaction as db_transaction
from django.utils import timezone

from apps.admin_panel.models import InvoiceSettings

TWOPLACES = Decimal('0.01')
_BELOW_TWENTY = [
    '', 'One', 'Two', 'Three', 'Four', 'Five', 'Six', 'Seven', 'Eight', 'Nine', 'Ten',
    'Eleven', 'Twelve', 'Thirteen', 'Fourteen', 'Fifteen', 'Sixteen', 'Seventeen', 'Eighteen', 'Nineteen',
]
_TENS = ['', '', 'Twenty', 'Thirty', 'Forty', 'Fifty', 'Sixty', 'Seventy', 'Eighty', 'Ninety']


def _money(value) -> Decimal:
    return Decimal(str(value or 0)).quantize(TWOPLACES, rounding=ROUND_HALF_UP)


def _two_digits(value: int) -> str:
    if value < 20:
        return _BELOW_TWENTY[value]
    ten, one = divmod(value, 10)
    return _TENS[ten] if one == 0 else f'{_TENS[ten]} {_BELOW_TWENTY[one]}'


def _indian_group(value: int) -> str:
    if value == 0:
        return ''
    hundred, rest = divmod(value, 100)
    parts = []
    if hundred:
        parts.append(f'{_BELOW_TWENTY[hundred]} Hundred')
    if rest:
        parts.append(_two_digits(rest))
    return ' '.join(parts)


def format_invoice_date(value=None) -> str:
    when = value or timezone.localdate()
    if hasattr(when, 'astimezone'):
        when = timezone.localtime(when).date()
    return f'{when.day} {when.strftime("%B %Y")}'


def amount_in_words(amount) -> str:
    total = _money(amount)
    rupees = int(total)
    paise = int((total - Decimal(rupees)) * 100)
    if rupees == 0 and paise == 0:
        return 'Zero Rupees Only'
    crore, rest = divmod(rupees, 10000000)
    lakh, rest = divmod(rest, 100000)
    thousand, rest = divmod(rest, 1000)
    parts = []
    if crore:
        parts.append(f'{_indian_group(crore)} Crore')
    if lakh:
        parts.append(f'{_indian_group(lakh)} Lakh')
    if thousand:
        parts.append(f'{_indian_group(thousand)} Thousand')
    if rest:
        parts.append(_indian_group(rest))
    words = ' '.join(part for part in parts if part).strip() or 'Zero'
    if paise:
        return f'{words} Rupees and {_two_digits(paise)} Paise Only'
    return f'{words} Rupees Only'


def tax_breakdown(total, gst_rate_percent):
    paid = _money(total)
    rate = Decimal(str(gst_rate_percent or 0))
    if rate <= 0:
        return {
            'taxable': paid,
            'cgst': Decimal('0.00'),
            'sgst': Decimal('0.00'),
            'round_off': Decimal('0.00'),
            'total': paid,
            'cgst_rate': Decimal('0'),
            'sgst_rate': Decimal('0'),
        }
    taxable = (paid / (Decimal('1') + (rate / Decimal('100')))).quantize(TWOPLACES, rounding=ROUND_HALF_UP)
    gst = (paid - taxable).quantize(TWOPLACES)
    cgst = (gst / Decimal('2')).quantize(TWOPLACES, rounding=ROUND_HALF_UP)
    sgst = (gst - cgst).quantize(TWOPLACES)
    half_rate = (rate / Decimal('2')).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
    return {
        'taxable': taxable,
        'cgst': cgst,
        'sgst': sgst,
        'round_off': Decimal('0.00'),
        'total': paid,
        'cgst_rate': half_rate,
        'sgst_rate': half_rate,
    }


def get_or_create_invoice_settings() -> InvoiceSettings:
    row, _ = InvoiceSettings.objects.get_or_create(key='global')
    return row


def _media_url(field, request=None) -> str:
    if not field:
        return ''
    try:
        url = field.url
    except ValueError:
        return ''
    if request is not None:
        return request.build_absolute_uri(url)
    return url


def company_payload(settings: InvoiceSettings, request=None) -> dict:
    return {
        'legalName': settings.legal_name or '',
        'companyLine': settings.company_line or '',
        'fullName': settings.full_name,
        'address': settings.address or '',
        'phone': settings.phone or '',
        'email': settings.email or '',
        'gstNumber': settings.gst_number or '',
        'declaration': settings.declaration or '',
        'signatureUrl': _media_url(settings.signature, request),
        'stampUrl': _media_url(settings.stamp, request),
        'gstRatePercent': str(settings.gst_rate_percent or 18),
    }


def settings_public(settings: InvoiceSettings, request=None) -> dict:
    data = company_payload(settings, request)
    data['invoiceNextNumber'] = int(settings.invoice_next_number or 1)
    data['updatedAt'] = settings.updated_at.isoformat() if settings.updated_at else None
    return data


INVOICE_PREFIX = 'PRA'


def _line_list_amount(row: dict) -> Decimal:
    """Inclusive list price for the row (before GST split / coupons)."""
    if row.get('listAmount') not in (None, ''):
        return _money(row.get('listAmount'))
    qty = max(int(row.get('quantity') or 1), 1)
    unit = _money(row.get('price') or 0)
    if unit <= 0 and row.get('amount') is not None:
        return _money(row.get('amount'))
    return (unit * Decimal(qty)).quantize(TWOPLACES, rounding=ROUND_HALF_UP)


def _line_shares(lines: list[dict], taxable: Decimal) -> list[dict]:
    weights = [_line_list_amount(row) for row in lines]
    gross = sum(weights, Decimal('0.00'))
    out = []
    allocated = Decimal('0.00')
    for index, row in enumerate(lines):
        qty = max(int(row.get('quantity') or 1), 1)
        title = str(row.get('title') or '').strip() or f'Item {index + 1}'
        list_amount = weights[index]
        if index == len(lines) - 1:
            amount = (taxable - allocated).quantize(TWOPLACES)
        elif gross > 0:
            amount = (taxable * list_amount / gross).quantize(TWOPLACES, rounding=ROUND_HALF_UP)
            allocated += amount
        else:
            amount = Decimal('0.00')
        unit = (amount / Decimal(qty)).quantize(TWOPLACES, rounding=ROUND_HALF_UP) if qty else amount
        out.append({
            'title': title,
            'quantity': qty,
            'price': str(unit),
            'amount': str(amount),
            'listAmount': str(list_amount),
        })
    return out


def _normalize_coupons(raw) -> list[dict]:
    coupons = []
    for index, row in enumerate(raw or []):
        if not isinstance(row, dict):
            continue
        name = str(row.get('name') or row.get('title') or '').strip()
        amount = _money(row.get('amount') or 0)
        if not name and amount <= 0:
            continue
        coupons.append({
            'name': name or f'Coupon {index + 1}',
            'amount': str(amount),
        })
    return coupons


def extract_payin_references(load_money) -> dict:
    meta = load_money.payment_meta if isinstance(load_money.payment_meta, dict) else {}
    rrn = (
        str(meta.get('rrn') or meta.get('RRN') or meta.get('bankRrn') or meta.get('bank_rrn') or '').strip()
        or str(load_money.utr or '').strip()
        or str(load_money.gateway_transaction_id or '').strip()
    )
    return {
        'transactionId': load_money.transaction_id or '',
        'rrn': rrn,
        'utr': str(load_money.utr or '').strip(),
        'gatewayTransactionId': str(load_money.gateway_transaction_id or '').strip(),
        'providerOrderId': str(load_money.provider_order_id or '').strip(),
        'transactionAmount': str(_money(load_money.amount)),
    }


def recompute_payload(payload: dict, gst_rate_percent=None) -> dict:
    """Normalize edited invoice fields and recompute tax from lines minus coupons."""
    data = dict(payload or {})
    customer = dict(data.get('customer') or {})
    lines_in = list(data.get('lines') or [])
    if not lines_in:
        default_total = data.get('transactionAmount') or data.get('total') or '0'
        lines_in = [{'title': data.get('courseTitle') or 'Pay In', 'quantity': 1, 'price': default_total}]

    coupons = _normalize_coupons(data.get('coupons'))
    lines_gross = sum((_line_list_amount(row) for row in lines_in), Decimal('0.00'))
    coupon_total = sum((_money(row.get('amount')) for row in coupons), Decimal('0.00'))
    total = (lines_gross - coupon_total).quantize(TWOPLACES)
    if total < 0:
        total = Decimal('0.00')

    rate = gst_rate_percent
    if rate is None:
        company = data.get('company') or {}
        rate = company.get('gstRatePercent')
    breakdown = tax_breakdown(total, rate)
    lines = _line_shares(lines_in, breakdown['taxable'])
    qty = sum(int(row['quantity']) for row in lines) or len(lines) or 1
    # Summary "Course :" heading stays independent of purchased line-item names.
    course_title = str(data.get('courseTitle') or '').strip()

    company = dict(data.get('company') or {})
    transaction_amount = _money(data.get('transactionAmount') or total)
    return {
        'company': company,
        'invoiceNumber': str(data.get('invoiceNumber') or '').strip(),
        'date': str(data.get('date') or format_invoice_date()),
        'customer': {
            'name': str(customer.get('name') or '').strip(),
            'email': str(customer.get('email') or '').strip(),
            'phone': str(customer.get('phone') or '').strip(),
            'address': str(customer.get('address') or '').strip(),
        },
        'courseTitle': course_title,
        'paymentMethod': str(data.get('paymentMethod') or 'Online').strip() or 'Online',
        'lines': lines,
        'coupons': coupons,
        'linesGross': str(lines_gross),
        'couponTotal': str(coupon_total),
        'quantity': qty,
        'taxable': str(breakdown['taxable']),
        'cgstRate': str(breakdown['cgst_rate']),
        'cgst': str(breakdown['cgst']),
        'sgstRate': str(breakdown['sgst_rate']),
        'sgst': str(breakdown['sgst']),
        'roundOff': str(breakdown['round_off']),
        'total': str(breakdown['total']),
        'amountInWords': amount_in_words(breakdown['total']),
        'transactionId': str(data.get('transactionId') or '').strip(),
        'rrn': str(data.get('rrn') or '').strip(),
        'utr': str(data.get('utr') or '').strip(),
        'gatewayTransactionId': str(data.get('gatewayTransactionId') or '').strip(),
        'providerOrderId': str(data.get('providerOrderId') or '').strip(),
        'transactionAmount': str(transaction_amount),
        'amountMatchesTransaction': breakdown['total'] == transaction_amount,
        'saved': bool(data.get('saved')),
    }


def build_draft_from_load_money(load_money, request=None) -> dict:
    settings = get_or_create_invoice_settings()
    company = company_payload(settings, request)
    total = _money(load_money.amount)
    refs = extract_payin_references(load_money)
    title = (load_money.gateway or '').strip() or 'Pay In'
    if load_money.collection_rail == 'qr':
        title = 'Pay In (QR)'
    method = (load_money.payment_method or '').strip() or 'Online'
    if method and method.lower() not in ('online',):
        method = method.replace('_', ' ').title()
    else:
        method = 'Online'

    draft = {
        'company': company,
        'invoiceNumber': '',
        'date': format_invoice_date(load_money.created_at) if load_money.created_at else format_invoice_date(),
        'customer': {
            'name': load_money.customer_name or '',
            'email': load_money.customer_email or '',
            'phone': load_money.customer_phone or '',
            'address': '',
        },
        'courseTitle': title,
        'paymentMethod': method,
        'lines': [{'title': title, 'quantity': 1, 'price': str(total), 'amount': str(total)}],
        'coupons': [],
        'total': str(total),
        **refs,
        'saved': False,
    }
    return recompute_payload(draft, settings.gst_rate_percent)


def _invoice_day_key(when=None) -> str:
    stamp = when or timezone.localtime()
    if hasattr(stamp, 'astimezone'):
        stamp = timezone.localtime(stamp)
    if hasattr(stamp, 'date'):
        stamp = stamp.date()
    return stamp.strftime('%Y%m%d')


def next_pra_invoice_number(*, when=None, exists_fn) -> str:
    """PRA + YYYYMMDD + 4-digit daily sequence, e.g. PRA202610200001."""
    day_key = _invoice_day_key(when)
    prefix = f'{INVOICE_PREFIX}{day_key}'
    with db_transaction.atomic():
        seq = 1
        while exists_fn(f'{prefix}{seq:04d}'):
            seq += 1
            if seq > 9999:
                raise RuntimeError('Daily invoice sequence exhausted.')
        return f'{prefix}{seq:04d}'


def assign_invoice_number(existing_number: str = '', when=None) -> str:
    if existing_number:
        return existing_number
    from apps.fund_management.models import PayinTaxInvoice

    return next_pra_invoice_number(
        when=when,
        exists_fn=lambda value: PayinTaxInvoice.objects.filter(invoice_number=value).exists(),
    )


def serialize_saved(row, request=None) -> dict:
    payload = dict(row.payload or {})
    payload['invoiceNumber'] = row.invoice_number
    payload['saved'] = True
    if row.load_money_id:
        refs = extract_payin_references(row.load_money)
        for key, value in refs.items():
            if value or key in ('transactionId', 'transactionAmount'):
                payload[key] = value or payload.get(key) or ''
    # Refresh live company asset URLs from settings if payload company lacks them
    settings = get_or_create_invoice_settings()
    company = company_payload(settings, request)
    saved_company = dict(payload.get('company') or {})
    for key in ('signatureUrl', 'stampUrl', 'legalName', 'companyLine', 'fullName', 'address', 'phone', 'email', 'gstNumber', 'declaration', 'gstRatePercent'):
        if key in ('signatureUrl', 'stampUrl'):
            saved_company[key] = company.get(key) or saved_company.get(key) or ''
        elif not saved_company.get(key):
            saved_company[key] = company.get(key) or ''
    payload['company'] = saved_company
    return recompute_payload(payload, saved_company.get('gstRatePercent') or settings.gst_rate_percent)
