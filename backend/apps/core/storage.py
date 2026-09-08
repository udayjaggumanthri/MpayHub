"""
Env-driven media storage backends.

When USE_S3=True, uploads land in the shared bucket under AWS_S3_MEDIA_PREFIX
(uat/ vs prod/). .url always returns same-origin MEDIA_URL paths so DB-relative
names and nginx /media/ keep working without hardcoding S3 hosts.
"""

from urllib.parse import urljoin

from django.conf import settings
from storages.backends.s3boto3 import S3Boto3Storage


class MediaStorage(S3Boto3Storage):
    """Private S3 media with same-origin /media/ URLs."""

    default_acl = None
    file_overwrite = False
    querystring_auth = False
    location = ''

    def __init__(self, *args, **kwargs):
        prefix = (getattr(settings, 'AWS_S3_MEDIA_PREFIX', None) or '').strip().strip('/')
        kwargs.setdefault('location', prefix)
        kwargs.setdefault('default_acl', None)
        kwargs.setdefault('querystring_auth', False)
        kwargs.setdefault('file_overwrite', False)
        bucket = getattr(settings, 'AWS_STORAGE_BUCKET_NAME', None)
        if bucket:
            kwargs.setdefault('bucket_name', bucket)
        region = getattr(settings, 'AWS_S3_REGION_NAME', None)
        if region:
            kwargs.setdefault('region_name', region)
        super().__init__(*args, **kwargs)

    def url(self, name, parameters=None, expire=None, http_method=None):
        """Return MEDIA_URL-relative path (ignore S3 public object URLs)."""
        media_url = settings.MEDIA_URL or '/media/'
        if not media_url.endswith('/'):
            media_url = f'{media_url}/'
        cleaned = (name or '').lstrip('/')
        return urljoin(media_url, cleaned)
