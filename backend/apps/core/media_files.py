"""
Helpers for ImageField / FileField cleanup across local disk and S3.

Use these whenever a media file is removed or replaced so objects do not linger
in default_storage (FileSystemStorage or MediaStorage).
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


def discard_stored_file(field_file: Any) -> None:
    """
    Delete the underlying storage object for a FileField/ImageField value.

    Safe if the field is empty or the object is already gone.
    Does not save the model — caller clears the field and saves as needed.
    """
    if not field_file:
        return
    name = (getattr(field_file, 'name', None) or '').strip()
    if not name:
        return
    try:
        field_file.delete(save=False)
    except Exception:
        logger.exception('Failed to delete stored media file name=%s', name)


def clear_image_field(instance: Any, field_name: str, *, save: bool = False) -> None:
    """Delete storage object and null/blank the model field."""
    field_file = getattr(instance, field_name, None)
    discard_stored_file(field_file)
    field = instance._meta.get_field(field_name)
    empty = None if getattr(field, 'null', False) else ''
    setattr(instance, field_name, empty)
    if save:
        instance.save(update_fields=[field_name])


def delete_replaced_file(old_name: str | None, new_name: str | None) -> None:
    """
    After assigning a new upload, remove the previous storage key if it changed.
    """
    old = (old_name or '').strip()
    new = (new_name or '').strip()
    if not old or old == new:
        return
    from django.core.files.storage import default_storage

    try:
        if default_storage.exists(old):
            default_storage.delete(old)
    except Exception:
        logger.exception('Failed to delete replaced media file name=%s', old)
