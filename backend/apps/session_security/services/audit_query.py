"""Query helpers for user activity audit logs (filters + Excel)."""
from __future__ import annotations

import io
from datetime import datetime, time
from typing import Any

from django.db.models import QuerySet
from django.http import HttpResponse
from django.utils import timezone
from django.utils.dateparse import parse_date, parse_datetime

from apps.session_security.constants import (
    ADMIN_EVENTS,
    AUTH_EVENTS,
    ACCOUNT_EVENTS,
    CATEGORY_ACCOUNT,
    CATEGORY_ADMIN,
    CATEGORY_ALL,
    CATEGORY_AUTH,
    CATEGORY_MONEY,
    MONEY_EVENTS,
    event_category,
)
from apps.session_security.models import UserLoginAuditLog


def _parse_day_bound(raw: str | None, *, end: bool) -> datetime | None:
    """
    Parse a filter bound.

    HTML ``<input type="date">`` sends ``YYYY-MM-DD``. Django's
    ``parse_datetime('YYYY-MM-DD')`` returns midnight — which must NOT be used
    as ``date_to`` (it would exclude the entire selected day). Date-only strings
    therefore become start/end of that calendar day in the active timezone.
    """
    if not raw:
        return None
    raw = str(raw).strip()
    if not raw:
        return None

    # Prefer date-only handling for YYYY-MM-DD (and similar date-only forms).
    d = parse_date(raw)
    if d is not None and 'T' not in raw and ' ' not in raw and len(raw) <= 10:
        tz = timezone.get_current_timezone()
        if end:
            return timezone.make_aware(
                datetime.combine(d, time(23, 59, 59, 999999)), tz
            )
        return timezone.make_aware(datetime.combine(d, time.min), tz)

    dt = parse_datetime(raw)
    if dt is not None:
        if timezone.is_naive(dt):
            dt = timezone.make_aware(dt, timezone.get_current_timezone())
        return dt
    return None


def filter_audit_queryset(
    qs: QuerySet | None = None,
    *,
    user_id=None,
    event_type: str = '',
    category: str = '',
    date_from: str | None = None,
    date_to: str | None = None,
) -> QuerySet:
    if qs is None:
        qs = UserLoginAuditLog.objects.select_related('user', 'session').all()
    if user_id not in (None, ''):
        qs = qs.filter(user_id=user_id)
    event_type = (event_type or '').strip()
    if event_type:
        qs = qs.filter(event_type=event_type)
    category = (category or CATEGORY_ALL).strip().lower()
    if category == CATEGORY_AUTH:
        qs = qs.filter(event_type__in=AUTH_EVENTS)
    elif category == CATEGORY_MONEY:
        qs = qs.filter(event_type__in=MONEY_EVENTS)
    elif category == CATEGORY_ADMIN:
        qs = qs.filter(event_type__in=ADMIN_EVENTS)
    elif category == CATEGORY_ACCOUNT:
        qs = qs.filter(event_type__in=ACCOUNT_EVENTS)
    start = _parse_day_bound(date_from, end=False)
    end = _parse_day_bound(date_to, end=True)
    if start:
        qs = qs.filter(created_at__gte=start)
    if end:
        qs = qs.filter(created_at__lte=end)
    return qs.order_by('-created_at')


def format_location(location: dict | None, *, ip_address: str | None = None) -> str:
    loc = location if isinstance(location, dict) else {}
    parts = [loc.get('city'), loc.get('region'), loc.get('country') or loc.get('country_name')]
    label = ', '.join(str(p) for p in parts if p)
    if label:
        return label
    source = (loc.get('source') or '').strip()
    if source in ('server_side', 'none') or not ip_address:
        return 'N/A (server-side)'
    if source == 'unavailable':
        return 'Unknown'
    return ''


def is_stub_location(location: dict | None) -> bool:
    """True for test/memory placeholder geo that should not be shown in production UI."""
    loc = location if isinstance(location, dict) else {}
    city = str(loc.get('city') or '')
    region = str(loc.get('region') or '')
    source = str(loc.get('source') or '')
    return (
        source == 'memory'
        or city == 'Test City'
        or region == 'Test Region'
        or city.startswith('Test ')
    )


def heal_location_for_display(location: dict | None, ip_address: str | None) -> dict:
    """
    Replace stub/memory geo with a live soft GeoIP lookup for display.
    Does not raise; returns original location when heal is not possible.
    """
    loc = dict(location or {}) if isinstance(location, dict) else {}
    if not is_stub_location(loc):
        return loc
    ip = (ip_address or loc.get('ip') or '').strip()
    if not ip:
        return loc
    try:
        from apps.session_security.services.geo import soft_lookup_location

        healed = soft_lookup_location(ip)
        if is_stub_location(healed):
            return loc
        if healed.get('city') or healed.get('country'):
            return healed
    except Exception:  # noqa: BLE001
        pass
    return loc


def format_browser_coords(browser_geo: dict | None) -> str:
    geo = browser_geo if isinstance(browser_geo, dict) else {}
    if geo.get('status') != 'granted':
        return ''
    lat = geo.get('latitude')
    lng = geo.get('longitude')
    if lat is None or lng is None:
        return ''
    try:
        return f'{float(lat):.5f}, {float(lng):.5f}'
    except (TypeError, ValueError):
        return ''


def precise_location_label(
    *,
    location: dict | None,
    metadata: dict | None,
    ip_address: str | None = None,
) -> str:
    """Prefer browser GPS coords when granted; else IP-derived city label."""
    meta = metadata if isinstance(metadata, dict) else {}
    browser = meta.get('browser_geo') if isinstance(meta.get('browser_geo'), dict) else {}
    coords = format_browser_coords(browser)
    if coords:
        return coords
    display_loc = heal_location_for_display(location, ip_address)
    return format_location(display_loc, ip_address=ip_address)


def device_summary(metadata: dict | None) -> str:
    meta = metadata if isinstance(metadata, dict) else {}
    device = meta.get('device') if isinstance(meta.get('device'), dict) else {}
    if not device:
        return ''
    browser = device.get('browser_name') or ''
    ver = device.get('browser_version') or ''
    browser_part = f'{browser} {ver}'.strip() if browser else ''
    os_part = device.get('os') or ''
    dtype = device.get('device_type') or ''
    parts = [p for p in (browser_part, os_part, dtype) if p]
    return ' · '.join(parts)


def _resolve_device_for_row(row: UserLoginAuditLog) -> dict:
    meta = row.metadata if isinstance(row.metadata, dict) else {}
    device = meta.get('device') if isinstance(meta.get('device'), dict) else {}
    if device.get('browser_name') or device.get('os'):
        return device

    from apps.session_security.services.device_parse import (
        device_from_session_info,
        device_from_user_agent,
    )

    session = getattr(row, 'session', None)
    if session is not None:
        from_session = device_from_session_info(getattr(session, 'device_info', None))
        if from_session:
            return from_session

    ua = row.user_agent or ''
    if ua:
        return device_from_user_agent(ua)
    return {}


def serialize_audit_row(row: UserLoginAuditLog, *, user_brief_fn=None) -> dict[str, Any]:
    user_payload = None
    if row.user_id and user_brief_fn:
        user_payload = user_brief_fn(row.user)
    elif row.user_id and row.user:
        user_payload = {
            'id': row.user.id,
            'display_code': getattr(row.user, 'display_code', None)
            or getattr(row.user, 'user_id', None),
            'phone': row.user.phone,
        }
    raw_loc = row.location or {}
    display_loc = heal_location_for_display(raw_loc, row.ip_address)
    meta = row.metadata or {}
    browser_geo = meta.get('browser_geo') if isinstance(meta.get('browser_geo'), dict) else {}
    device = _resolve_device_for_row(row)
    resolution = meta.get('location_resolution') or ''
    if not resolution:
        if browser_geo.get('status') == 'granted':
            resolution = 'browser'
        elif display_loc.get('city') or display_loc.get('country'):
            resolution = 'ip_fallback'
        else:
            resolution = ''
    # Never advertise stub memory source in API responses
    location_source = display_loc.get('source') or ''
    if location_source == 'memory':
        location_source = display_loc.get('source') if not is_stub_location(display_loc) else ''

    return {
        'id': row.id,
        'event_type': row.event_type,
        'category': event_category(row.event_type),
        'user_id': row.user_id,
        'user': user_payload,
        'phone_attempted': row.phone_attempted,
        'ip_address': row.ip_address,
        'location': display_loc,
        'location_label': format_location(display_loc, ip_address=row.ip_address),
        'precise_location_label': precise_location_label(
            location=display_loc, metadata=meta, ip_address=row.ip_address
        ),
        'location_source': location_source if location_source != 'memory' else '',
        'location_resolution': resolution,
        'browser_geo': browser_geo,
        'device': device,
        'device_summary': device_summary({'device': device}),
        'network_capture': meta.get('network_capture') or '',
        'user_agent': row.user_agent,
        'session_id': row.session_id,
        'message': row.message,
        'metadata': meta,
        'created_at': row.created_at.isoformat() if row.created_at else None,
    }


def paginate_queryset(qs: QuerySet, *, page: int = 1, page_size: int = 25):
    page = max(1, page)
    page_size = min(100, max(1, page_size))
    total = qs.count()
    start = (page - 1) * page_size
    rows = list(qs[start : start + page_size])
    return rows, {
        'page': page,
        'page_size': page_size,
        'total': total,
        'total_pages': (total + page_size - 1) // page_size if page_size else 1,
    }


def build_audit_xlsx(rows: list[UserLoginAuditLog], *, filename: str = 'activity.xlsx') -> HttpResponse:
    from openpyxl import Workbook

    wb = Workbook()
    ws = wb.active
    ws.title = 'Activity'
    headers = [
        'When',
        'Event',
        'Category',
        'User ID',
        'Display code',
        'Phone',
        'IP',
        'Location',
        'Precise location',
        'Device',
        'Location resolution',
        'Message',
        'Metadata',
    ]
    ws.append(headers)
    for row in rows:
        user = row.user
        display = ''
        phone = row.phone_attempted or ''
        if user:
            display = getattr(user, 'display_code', None) or getattr(user, 'user_id', None) or ''
            phone = phone or user.phone
        meta = row.metadata or {}
        meta_summary = ', '.join(f'{k}={v}' for k, v in list(meta.items())[:8])
        ws.append(
            [
                row.created_at.isoformat() if row.created_at else '',
                row.event_type,
                event_category(row.event_type),
                row.user_id or '',
                display,
                phone,
                row.ip_address or '',
                format_location(
                    heal_location_for_display(row.location, row.ip_address),
                    ip_address=row.ip_address,
                ),
                precise_location_label(
                    location=heal_location_for_display(row.location, row.ip_address),
                    metadata=meta,
                    ip_address=row.ip_address,
                ),
                device_summary({'device': _resolve_device_for_row(row)}) or device_summary(meta),
                meta.get('location_resolution') or '',
                (row.message or '')[:500],
                meta_summary[:1000],
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


def export_limit_default() -> int:
    return 5000
