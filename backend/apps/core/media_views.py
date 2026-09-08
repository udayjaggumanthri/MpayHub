"""Serve MEDIA via default_storage (local disk or S3) — works with USE_S3 on/off."""

from __future__ import annotations

import mimetypes
import posixpath

from django.core.files.storage import default_storage
from django.http import FileResponse, Http404, HttpResponseNotAllowed

from apps.core.media_cache import MEDIA_CACHE_CONTROL


def media_serve_view(request, path: str):
    """
    GET/HEAD /media/<path> — stream from default_storage.

    nginx should proxy /media/ here (not alias local disk) so S3 cutover is
    transparent. Local rollback (USE_S3=False) keeps the same URL shape.
    """
    if request.method not in ('GET', 'HEAD'):
        return HttpResponseNotAllowed(['GET', 'HEAD'])

    normalized = posixpath.normpath(path or '').lstrip('/')
    if normalized in ('', '.') or normalized.startswith('..') or '/../' in f'/{normalized}/':
        raise Http404('Media not found')

    # Single storage round-trip (avoid exists() + open()).
    try:
        fh = default_storage.open(normalized, 'rb')
    except (FileNotFoundError, OSError, ValueError):
        raise Http404('Media not found') from None

    content_type, _ = mimetypes.guess_type(normalized)
    response = FileResponse(fh, content_type=content_type or 'application/octet-stream')
    response['Cache-Control'] = MEDIA_CACHE_CONTROL
    return response
