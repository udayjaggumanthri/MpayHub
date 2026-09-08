"""Stream PayIn QR image files for authenticated API clients."""
from __future__ import annotations

import mimetypes

from django.http import FileResponse, Http404

from apps.core.media_cache import MEDIA_CACHE_CONTROL


def qr_image_file_response(image_field, *, download_name: str = 'qr.png'):
    if not image_field:
        raise Http404
    try:
        fh = image_field.open('rb')
        name = image_field.name.rsplit('/', 1)[-1] if image_field.name else download_name
        content_type = mimetypes.guess_type(name)[0] or 'image/png'
        response = FileResponse(fh, content_type=content_type)
        response['Cache-Control'] = MEDIA_CACHE_CONTROL
        return response
    except Exception as exc:
        raise Http404 from exc
