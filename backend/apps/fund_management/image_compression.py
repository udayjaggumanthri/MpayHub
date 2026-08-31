"""Image compression helpers for pay-in receipt uploads."""
from __future__ import annotations

import io
from typing import BinaryIO

from django.core.files.base import ContentFile
from PIL import Image, ImageOps

DEFAULT_MAX_BYTES = 100 * 1024
DEFAULT_MAX_EDGE = 1600
MIN_JPEG_QUALITY = 45


def _open_image(uploaded_file) -> Image.Image:
    if hasattr(uploaded_file, 'seek'):
        uploaded_file.seek(0)
    img = Image.open(uploaded_file)
    img = ImageOps.exif_transpose(img)
    if img.mode not in ('RGB', 'L'):
        img = img.convert('RGB')
    elif img.mode == 'L':
        img = img.convert('RGB')
    return img


def _resize_image(img: Image.Image, max_edge: int) -> Image.Image:
    w, h = img.size
    longest = max(w, h)
    if longest <= max_edge:
        return img
    scale = max_edge / float(longest)
    new_size = (max(1, int(w * scale)), max(1, int(h * scale)))
    return img.resize(new_size, Image.Resampling.LANCZOS)


def _encode_jpeg(img: Image.Image, quality: int) -> bytes:
    buf = io.BytesIO()
    img.save(buf, format='JPEG', quality=quality, optimize=True)
    return buf.getvalue()


def compress_image_bytes(
    raw: bytes,
    *,
    max_bytes: int = DEFAULT_MAX_BYTES,
    max_edge: int = DEFAULT_MAX_EDGE,
    filename: str = 'receipt.jpg',
) -> ContentFile:
    if len(raw) <= max_bytes:
        return ContentFile(raw, name=filename)

    img = _open_image(io.BytesIO(raw))
    img = _resize_image(img, max_edge)

    quality = 82
    data = _encode_jpeg(img, quality)
    while len(data) > max_bytes and quality > MIN_JPEG_QUALITY:
        quality -= 8
        data = _encode_jpeg(img, quality)

    if len(data) > max_bytes:
        w, h = img.size
        img = img.resize((max(1, int(w * 0.75)), max(1, int(h * 0.75))), Image.Resampling.LANCZOS)
        quality = 72
        data = _encode_jpeg(img, quality)
        while len(data) > max_bytes and quality > MIN_JPEG_QUALITY:
            quality -= 8
            data = _encode_jpeg(img, quality)

    base = filename.rsplit('.', 1)[0] if '.' in filename else filename
    return ContentFile(data, name=f'{base}.jpg')


def compress_image_upload(
    uploaded_file,
    *,
    max_bytes: int = DEFAULT_MAX_BYTES,
    max_edge: int = DEFAULT_MAX_EDGE,
) -> ContentFile:
    """Return a ContentFile JPEG at or under max_bytes."""
    name = getattr(uploaded_file, 'name', None) or 'receipt.jpg'
    size = getattr(uploaded_file, 'size', None)
    if size is not None and size <= max_bytes:
        if hasattr(uploaded_file, 'seek'):
            uploaded_file.seek(0)
        raw = uploaded_file.read()
        return ContentFile(raw, name=name)

    if hasattr(uploaded_file, 'seek'):
        uploaded_file.seek(0)
    raw = uploaded_file.read()
    if len(raw) <= max_bytes:
        return ContentFile(raw, name=name)
    return compress_image_bytes(raw, max_bytes=max_bytes, max_edge=max_edge, filename=name)
