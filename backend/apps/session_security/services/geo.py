"""Pluggable GeoIP providers (IP-derived location)."""
from __future__ import annotations

import ipaddress
import logging
from abc import ABC, abstractmethod
from typing import Any

import requests
from django.conf import settings
from django.core.cache import cache

from apps.session_security.exceptions import GeoCaptureFailed

logger = logging.getLogger(__name__)

GEO_CACHE_KEY_PREFIX = 'geoip:v1:'


def _private_location(ip: str) -> dict[str, Any]:
    return {
        'country': 'LOCAL',
        'country_name': 'Private Network',
        'region': '',
        'city': 'Private Network',
        'latitude': None,
        'longitude': None,
        'source': 'private_network',
        'ip': ip,
    }


def _is_private_ip(ip: str) -> bool:
    try:
        addr = ipaddress.ip_address(ip)
        return bool(addr.is_private or addr.is_loopback or addr.is_link_local or addr.is_reserved)
    except ValueError:
        return False


class GeoIpProvider(ABC):
    @abstractmethod
    def lookup(self, ip: str) -> dict[str, Any]:
        """Return location dict or raise GeoCaptureFailed."""


class MemoryGeoProvider(GeoIpProvider):
    """Deterministic provider for tests / environments without external GeoIP."""

    def lookup(self, ip: str) -> dict[str, Any]:
        if not ip:
            raise GeoCaptureFailed('IP address is required for geolocation.')
        if _is_private_ip(ip):
            return _private_location(ip)
        return {
            'country': 'IN',
            'country_name': 'India',
            'region': 'Test Region',
            'city': 'Test City',
            'latitude': 28.6139,
            'longitude': 77.2090,
            'source': 'memory',
            'ip': ip,
        }


class HttpIpApiGeoProvider(GeoIpProvider):
    """
    Free HTTP GeoIP via ip-api.com (non-SSL free tier).

    Only called for public IPs; wrap with CachedGeoProvider in production.
    """

    ENDPOINT = 'http://ip-api.com/json/{ip}'
    FIELDS = 'status,message,country,countryCode,regionName,city,lat,lon,query'

    def __init__(self, timeout: float | None = None):
        self.timeout = float(
            timeout
            if timeout is not None
            else getattr(settings, 'GEOIP_HTTP_TIMEOUT_SECONDS', 1.5)
        )

    def lookup(self, ip: str) -> dict[str, Any]:
        if not ip:
            raise GeoCaptureFailed('IP address is required for geolocation.')
        if _is_private_ip(ip):
            return _private_location(ip)

        url = self.ENDPOINT.format(ip=ip)
        try:
            resp = requests.get(
                url,
                params={'fields': self.FIELDS},
                timeout=self.timeout,
            )
            resp.raise_for_status()
            data = resp.json()
        except requests.Timeout as exc:
            raise GeoCaptureFailed('Geolocation lookup timed out.') from exc
        except requests.RequestException as exc:
            logger.warning('ip-api request failed for %s: %s', ip, exc)
            raise GeoCaptureFailed('Geolocation lookup failed.') from exc
        except ValueError as exc:
            raise GeoCaptureFailed('Invalid geolocation response.') from exc

        if not isinstance(data, dict) or data.get('status') != 'success':
            msg = ''
            if isinstance(data, dict):
                msg = str(data.get('message') or '')
            raise GeoCaptureFailed(
                f'No geolocation data for IP {ip}' + (f': {msg}' if msg else '.')
            )

        country = (data.get('countryCode') or '').strip()
        city = (data.get('city') or '').strip()
        region = (data.get('regionName') or '').strip()
        if not country and not city:
            raise GeoCaptureFailed(f'Incomplete geolocation data for IP {ip}.')

        lat = data.get('lat')
        lon = data.get('lon')
        try:
            latitude = float(lat) if lat is not None else None
        except (TypeError, ValueError):
            latitude = None
        try:
            longitude = float(lon) if lon is not None else None
        except (TypeError, ValueError):
            longitude = None

        return {
            'country': country or 'XX',
            'country_name': (data.get('country') or '').strip(),
            'region': region,
            'city': city or 'Unknown',
            'latitude': latitude,
            'longitude': longitude,
            'source': 'ip-api',
            'ip': ip,
        }


class CachedGeoProvider(GeoIpProvider):
    """Cache-first wrapper; private IPs never hit the inner provider network path."""

    def __init__(self, inner: GeoIpProvider, ttl_seconds: int | None = None):
        self.inner = inner
        self.ttl = int(
            ttl_seconds
            if ttl_seconds is not None
            else getattr(settings, 'GEOIP_CACHE_TTL_SECONDS', 604800)
        )

    def lookup(self, ip: str) -> dict[str, Any]:
        if not ip:
            raise GeoCaptureFailed('IP address is required for geolocation.')
        if _is_private_ip(ip):
            return _private_location(ip)

        key = f'{GEO_CACHE_KEY_PREFIX}{ip}'
        cached = cache.get(key)
        if isinstance(cached, dict) and cached.get('country'):
            return cached

        location = self.inner.lookup(ip)
        try:
            cache.set(key, location, self.ttl)
        except Exception:  # noqa: BLE001
            logger.debug('Failed to cache geo lookup for %s', ip, exc_info=True)
        return location


class MaxMindGeoProvider(GeoIpProvider):
    """MaxMind GeoLite2-City lookup from a local MMDB file."""

    def __init__(self, db_path: str | None = None):
        self.db_path = db_path or getattr(settings, 'GEOIP_DB_PATH', '') or ''

    def lookup(self, ip: str) -> dict[str, Any]:
        if not ip:
            raise GeoCaptureFailed('IP address is required for geolocation.')
        if _is_private_ip(ip):
            return _private_location(ip)

        if not self.db_path:
            raise GeoCaptureFailed(
                'GeoIP database path is not configured (GEOIP_DB_PATH).'
            )

        try:
            import geoip2.database
            import geoip2.errors
        except ImportError as exc:
            raise GeoCaptureFailed(
                'geoip2 package is not installed; cannot resolve location.'
            ) from exc

        try:
            with geoip2.database.Reader(self.db_path) as reader:
                resp = reader.city(ip)
        except FileNotFoundError as exc:
            raise GeoCaptureFailed(
                f'GeoIP database not found at {self.db_path}.'
            ) from exc
        except geoip2.errors.AddressNotFoundError as exc:
            raise GeoCaptureFailed(f'No geolocation data for IP {ip}.') from exc
        except OSError as exc:
            raise GeoCaptureFailed(f'Unable to read GeoIP database: {exc}') from exc
        except Exception as exc:  # noqa: BLE001 — fail closed
            logger.warning('GeoIP lookup failed for %s: %s', ip, exc)
            raise GeoCaptureFailed('Geolocation lookup failed.') from exc

        country = (resp.country.iso_code or '').strip()
        city = (resp.city.name or '').strip() if resp.city else ''
        region = ''
        if resp.subdivisions:
            region = (resp.subdivisions.most_specific.name or '').strip()

        if not country and not city:
            raise GeoCaptureFailed(f'Incomplete geolocation data for IP {ip}.')

        return {
            'country': country or 'XX',
            'country_name': (resp.country.name or '') if resp.country else '',
            'region': region,
            'city': city or 'Unknown',
            'latitude': float(resp.location.latitude)
            if resp.location and resp.location.latitude is not None
            else None,
            'longitude': float(resp.location.longitude)
            if resp.location and resp.location.longitude is not None
            else None,
            'source': 'maxmind',
            'ip': ip,
        }


def get_geo_provider() -> GeoIpProvider:
    name = (getattr(settings, 'GEOIP_PROVIDER', 'http') or 'http').strip().lower()
    if name in ('memory', 'stub', 'test'):
        return MemoryGeoProvider()
    if name in ('maxmind', 'geolite2', 'geoip2'):
        return CachedGeoProvider(MaxMindGeoProvider())
    if name in ('http', 'ipapi', 'ip-api'):
        return CachedGeoProvider(HttpIpApiGeoProvider())
    logger.warning('Unknown GEOIP_PROVIDER=%s; using cached HTTP provider', name)
    return CachedGeoProvider(HttpIpApiGeoProvider())


def soft_lookup_location(ip: str | None) -> dict[str, Any]:
    """
    Resolve location for an IP without raising.

    Golden rule for audit rows: location must describe *this* IP.
    """
    if not ip:
        return {
            'country': '',
            'country_name': '',
            'region': '',
            'city': '',
            'latitude': None,
            'longitude': None,
            'source': 'none',
            'ip': '',
        }
    try:
        return get_geo_provider().lookup(ip)
    except GeoCaptureFailed:
        return {
            'country': 'XX',
            'country_name': 'Unknown',
            'region': '',
            'city': 'Unknown',
            'latitude': None,
            'longitude': None,
            'source': 'unavailable',
            'ip': ip,
        }
    except Exception:  # noqa: BLE001
        logger.exception('soft_lookup_location failed for %s', ip)
        return {
            'country': 'XX',
            'country_name': 'Unknown',
            'region': '',
            'city': 'Unknown',
            'latitude': None,
            'longitude': None,
            'source': 'unavailable',
            'ip': ip,
        }


def location_matches_ip(location: dict | None, ip: str | None) -> bool:
    """True when location dict was produced for the given IP (or both empty)."""
    loc = location if isinstance(location, dict) else {}
    loc_ip = (loc.get('ip') or '').strip()
    ip = (ip or '').strip()
    if not ip and not loc_ip:
        return True
    if not ip or not loc_ip:
        # Legacy rows may lack location.ip — treat as unmatched so we re-resolve
        return False
    return loc_ip == ip


def coalesce_audit_network(
    *,
    ip_address: str | None = None,
    location: dict | None = None,
    fallback_ip: str | None = None,
    fallback_location: dict | None = None,
) -> tuple[str | None, dict]:
    """
    Pick IP + location for an audit row, never mixing geo from a different IP.
    """
    effective_ip = (ip_address or fallback_ip or '').strip() or None
    loc = location if isinstance(location, dict) else None
    fb_loc = fallback_location if isinstance(fallback_location, dict) else None

    if loc and location_matches_ip(loc, effective_ip):
        return effective_ip, loc
    if (
        fb_loc
        and effective_ip
        and (location_matches_ip(fb_loc, effective_ip) or not fb_loc.get('ip'))
        and (fallback_ip or '') == (effective_ip or '')
    ):
        # Same IP as session / prior capture — reuse stored geo
        if not fb_loc.get('ip') and effective_ip:
            fb_loc = {**fb_loc, 'ip': effective_ip}
        return effective_ip, fb_loc

    return effective_ip, soft_lookup_location(effective_ip)
