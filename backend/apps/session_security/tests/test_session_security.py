"""
Session security unit/integration tests.
"""
from datetime import timedelta
from unittest.mock import patch

import pytest
from django.test import RequestFactory
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.authentication.models import User, UserSession
from apps.session_security.constants import SESSION_CLAIM
from apps.session_security.exceptions import GeoCaptureFailed, SessionIdleTimeout, SessionReplaced
from apps.session_security.models import SessionSecuritySettings, UserLoginAuditLog
from apps.session_security.services.facade import get_facade
from apps.session_security.services.geo import MemoryGeoProvider, get_geo_provider
from apps.session_security.services.ip import ClientIpResolver
from apps.session_security.services.sessions import get_session_lifecycle
from apps.session_security.services.settings import invalidate_settings_cache, update_settings


@pytest.fixture
def api():
    return APIClient()


@pytest.fixture
def user(db):
    return User.objects.create_user(
        phone='9876543210',
        email='session.user@example.com',
        password='TestPass123!',
        role='Retailer',
        first_name='Session',
        last_name='User',
        user_id='RTEST1',
    )


@pytest.fixture
def admin_user(db):
    return User.objects.create_user(
        phone='9999999999',
        email='session.admin@example.com',
        password='AdminPass123!',
        role='Admin',
        first_name='Admin',
        last_name='User',
        user_id='ATEST1',
        is_staff=True,
        is_superuser=True,
    )


@pytest.fixture(autouse=True)
def _session_security_defaults(db, settings):
    settings.GEOIP_PROVIDER = 'memory'
    invalidate_settings_cache()
    SessionSecuritySettings.objects.update_or_create(
        pk=1,
        defaults={
            'ip_location_enforcement_enabled': True,
            'audit_logging_enabled': True,
            'single_session_enforcement_enabled': True,
            'idle_timeout_minutes': 5,
        },
    )
    invalidate_settings_cache()


class TestIpAndGeo:
    def test_prefers_x_real_ip(self):
        factory = RequestFactory()
        request = factory.get(
            '/',
            HTTP_X_REAL_IP='203.0.113.99',
            HTTP_X_FORWARDED_FOR='8.8.8.8, 203.0.113.99',
        )
        assert ClientIpResolver().resolve(request) == '203.0.113.99'

    def test_xff_rightmost_public_not_spoofed_left(self):
        factory = RequestFactory()
        # Client-spoofed left hop must not win; nginx-appended rightmost public wins
        request = factory.get('/', HTTP_X_FORWARDED_FOR='8.8.8.8, 203.0.113.10')
        assert ClientIpResolver().resolve(request) == '203.0.113.10'

    def test_xff_skips_private_tail(self):
        factory = RequestFactory()
        request = factory.get('/', HTTP_X_FORWARDED_FOR='203.0.113.10, 10.0.0.1')
        assert ClientIpResolver().resolve(request) == '203.0.113.10'

    def test_memory_geo_private_and_public(self):
        provider = MemoryGeoProvider()
        private = provider.lookup('127.0.0.1')
        assert private['source'] == 'private_network'
        public = provider.lookup('8.8.8.8')
        assert public['country'] == 'IN'
        assert get_geo_provider().__class__ is MemoryGeoProvider

    def test_coalesce_never_mixes_session_geo_with_other_ip(self, settings):
        from apps.session_security.services.geo import coalesce_audit_network

        settings.GEOIP_PROVIDER = 'memory'
        session_loc = {
            'city': 'Prakasam',
            'region': 'Andhra Pradesh',
            'country': 'IN',
            'ip': '160.238.73.134',
            'source': 'ip-api',
        }
        ip, loc = coalesce_audit_network(
            ip_address='150.238.73.134',
            location=None,
            fallback_ip='160.238.73.134',
            fallback_location=session_loc,
        )
        assert ip == '150.238.73.134'
        assert loc.get('ip') == '150.238.73.134'
        assert loc.get('city') != 'Prakasam'


@pytest.mark.django_db
class TestLoginSessionFlow:
    def test_login_creates_session_and_audit(self, api, user):
        res = api.post(
            '/api/auth/login/',
            {'phone': '9876543210', 'password': 'TestPass123!'},
            format='json',
            REMOTE_ADDR='127.0.0.1',
        )
        assert res.status_code == 200
        assert res.data['success'] is True
        tokens = res.data['data']['tokens']
        assert tokens['access'] and tokens['refresh']
        access = AccessToken(tokens['access'])
        sid = access[SESSION_CLAIM]
        session = UserSession.objects.get(jti=sid)
        assert session.is_active
        assert session.ip_address == '127.0.0.1'
        assert UserLoginAuditLog.objects.filter(
            user=user, event_type='login_success'
        ).exists()

    def test_geo_failure_blocks_login(self, api, user):
        with patch(
            'apps.session_security.services.facade.get_geo_provider'
        ) as mock_geo:
            mock_geo.return_value.lookup.side_effect = GeoCaptureFailed('no geo')
            res = api.post(
                '/api/auth/login/',
                {'phone': '9876543210', 'password': 'TestPass123!'},
                format='json',
                REMOTE_ADDR='203.0.113.50',
            )
        assert res.status_code == 403
        assert res.data['error']['code'] == 'GEO_CAPTURE_FAILED'
        assert not UserSession.objects.filter(user=user, is_active=True).exists()

    def test_single_session_replaces_previous(self, api, user):
        first = api.post(
            '/api/auth/login/',
            {'phone': '9876543210', 'password': 'TestPass123!'},
            format='json',
            REMOTE_ADDR='127.0.0.1',
        )
        first_access = first.data['data']['tokens']['access']
        second = api.post(
            '/api/auth/login/',
            {'phone': '9876543210', 'password': 'TestPass123!'},
            format='json',
            REMOTE_ADDR='127.0.0.1',
        )
        assert second.status_code == 200
        assert UserSession.objects.filter(user=user, is_active=True).count() == 1

        api.credentials(HTTP_AUTHORIZATION=f'Bearer {first_access}')
        me = api.get('/api/auth/me/')
        assert me.status_code == 401

    def test_concurrent_exception_keeps_both(self, api, user):
        user.allow_concurrent_sessions = True
        user.save(update_fields=['allow_concurrent_sessions'])
        api.post(
            '/api/auth/login/',
            {'phone': '9876543210', 'password': 'TestPass123!'},
            format='json',
            REMOTE_ADDR='127.0.0.1',
        )
        api.post(
            '/api/auth/login/',
            {'phone': '9876543210', 'password': 'TestPass123!'},
            format='json',
            REMOTE_ADDR='127.0.0.1',
        )
        assert UserSession.objects.filter(user=user, is_active=True).count() == 2

    def test_idle_timeout_rejects_session(self, api, user):
        res = api.post(
            '/api/auth/login/',
            {'phone': '9876543210', 'password': 'TestPass123!'},
            format='json',
            REMOTE_ADDR='127.0.0.1',
        )
        access = res.data['data']['tokens']['access']
        sid = AccessToken(access)[SESSION_CLAIM]
        session = UserSession.objects.get(jti=sid)
        session.last_activity_at = timezone.now() - timedelta(minutes=30)
        session.save(update_fields=['last_activity_at'])

        api.credentials(HTTP_AUTHORIZATION=f'Bearer {access}')
        me = api.get('/api/auth/me/')
        assert me.status_code == 401
        session.refresh_from_db()
        assert session.is_active is False
        assert session.termination_reason == 'idle'

    def test_logout_deactivates_session(self, api, user):
        res = api.post(
            '/api/auth/login/',
            {'phone': '9876543210', 'password': 'TestPass123!'},
            format='json',
            REMOTE_ADDR='127.0.0.1',
        )
        access = res.data['data']['tokens']['access']
        sid = AccessToken(access)[SESSION_CLAIM]
        api.credentials(HTTP_AUTHORIZATION=f'Bearer {access}')
        out = api.post('/api/auth/logout/')
        assert out.status_code == 200
        session = UserSession.objects.get(jti=sid)
        assert session.is_active is False
        assert session.termination_reason == 'logout'


@pytest.mark.django_db
class TestAdminSettingsApi:
    def test_admin_can_patch_settings(self, api, admin_user):
        api.force_authenticate(user=admin_user)
        # Need a real session for JWT path — force_authenticate bypasses JWT
        res = api.patch(
            '/api/admin/session-security/settings/',
            {'idle_timeout_minutes': 3, 'single_session_enforcement_enabled': False},
            format='json',
        )
        assert res.status_code == 200
        assert res.data['data']['settings']['idle_timeout_minutes'] == 3
        assert res.data['data']['settings']['single_session_enforcement_enabled'] is False

    def test_exception_toggle(self, api, admin_user, user):
        api.force_authenticate(user=admin_user)
        res = api.post(
            '/api/admin/session-security/concurrent-exceptions/',
            {'user_id': user.id, 'allow_concurrent_sessions': True},
            format='json',
        )
        assert res.status_code == 200
        user.refresh_from_db()
        assert user.allow_concurrent_sessions is True

    def test_audit_export_xlsx(self, api, admin_user, user):
        UserLoginAuditLog.objects.create(
            user=user,
            event_type='login_success',
            ip_address='203.0.113.10',
            location={'city': 'Hyderabad', 'region': 'Telangana', 'country': 'IN'},
            message='ok',
        )
        api.force_authenticate(user=admin_user)
        res = api.get('/api/admin/session-security/audit-logs/export/', {'user_id': user.id})
        assert res.status_code == 200
        assert (
            res['Content-Type']
            == 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
        assert res.content[:2] == b'PK'

    def test_my_activity(self, api, user):
        UserLoginAuditLog.objects.create(
            user=user,
            event_type='wallet_transfer',
            message='Transfer',
        )
        api.force_authenticate(user=user)
        res = api.get('/api/auth/my-activity/', {'category': 'money'})
        assert res.status_code == 200
        assert res.data['success'] is True
        assert any(r['event_type'] == 'wallet_transfer' for r in res.data['data']['results'])

    def test_non_admin_cannot_list_all_audit_logs(self, api, user):
        api.force_authenticate(user=user)
        res = api.get('/api/admin/session-security/audit-logs/')
        assert res.status_code in (403, 401)

    def test_account_category_filter(self, api, user):
        UserLoginAuditLog.objects.create(
            user=user,
            event_type='contact_created',
            message='Contact created: Demo',
        )
        api.force_authenticate(user=user)
        res = api.get('/api/auth/my-activity/', {'category': 'account'})
        assert res.status_code == 200
        assert any(r['event_type'] == 'contact_created' for r in res.data['data']['results'])

    def test_date_to_includes_full_local_day(self, api, user):
        """Regression: YYYY-MM-DD date_to must be end-of-day, not midnight."""
        from django.utils import timezone as dj_tz
        from datetime import timedelta

        # Event "today" afternoon IST
        now = dj_tz.localtime(dj_tz.now())
        row = UserLoginAuditLog.objects.create(
            user=user,
            event_type='login_success',
            message='today login',
            ip_address='8.8.8.8',
        )
        # Force created_at to mid-afternoon today if needed
        UserLoginAuditLog.objects.filter(pk=row.pk).update(created_at=now)
        ymd = now.strftime('%Y-%m-%d')
        api.force_authenticate(user=user)
        res = api.get(
            '/api/auth/my-activity/',
            {'date_from': ymd, 'date_to': ymd},
        )
        assert res.status_code == 200
        ids = [r['id'] for r in res.data['data']['results']]
        assert row.id in ids


@pytest.mark.django_db
class TestCachedHttpGeo:
    def test_cache_hit_skips_http(self, settings):
        from django.core.cache import cache
        from apps.session_security.services.geo import CachedGeoProvider, HttpIpApiGeoProvider

        settings.GEOIP_PROVIDER = 'http'
        cache.clear()
        calls = {'n': 0}

        class Counting(HttpIpApiGeoProvider):
            def lookup(self, ip):
                calls['n'] += 1
                return {
                    'country': 'IN',
                    'country_name': 'India',
                    'region': 'Telangana',
                    'city': 'Hyderabad',
                    'latitude': 17.3,
                    'longitude': 78.4,
                    'source': 'ip-api',
                    'ip': ip,
                }

        provider = CachedGeoProvider(Counting(), ttl_seconds=60)
        a = provider.lookup('8.8.8.8')
        b = provider.lookup('8.8.8.8')
        assert a['city'] == 'Hyderabad'
        assert b['city'] == 'Hyderabad'
        assert calls['n'] == 1

    def test_passbook_emits_activity(self, user, db):
        from decimal import Decimal
        from apps.transactions.models import PassbookEntry
        from apps.session_security.constants import EVENT_PAYOUT_SUCCESS

        PassbookEntry.objects.create(
            user=user,
            wallet_type='main',
            service='PAYOUT',
            service_id='POTEST1',
            description='PAYOUT NEFT test',
            debit_amount=Decimal('100.00'),
            credit_amount=Decimal('0'),
            opening_balance=Decimal('500.00'),
            closing_balance=Decimal('400.00'),
        )
        row = UserLoginAuditLog.objects.filter(
            user=user, event_type=EVENT_PAYOUT_SUCCESS
        ).first()
        assert row is not None
        assert (row.metadata or {}).get('network_capture') == 'unavailable'
        assert (row.location or {}).get('source') == 'server_side'

    def test_passbook_uses_request_network_context(self, user, db, settings):
        from decimal import Decimal
        from apps.transactions.models import PassbookEntry
        from apps.session_security.constants import EVENT_PAYOUT_SUCCESS
        from apps.session_security.services.request_context import (
            clear_request_network,
            set_request_network,
        )

        settings.GEOIP_PROVIDER = 'memory'
        set_request_network(ip_address='8.8.8.8', user_agent='pytest-agent')
        try:
            PassbookEntry.objects.create(
                user=user,
                wallet_type='main',
                service='PAYOUT',
                service_id='POTEST2',
                description='PAYOUT NEFT with request',
                debit_amount=Decimal('50.00'),
                credit_amount=Decimal('0'),
                opening_balance=Decimal('400.00'),
                closing_balance=Decimal('350.00'),
            )
        finally:
            clear_request_network()

        row = UserLoginAuditLog.objects.filter(
            user=user, event_type=EVENT_PAYOUT_SUCCESS, ip_address='8.8.8.8'
        ).first()
        assert row is not None
        assert row.user_agent == 'pytest-agent'
        assert (row.metadata or {}).get('network_capture') == 'request'
        assert (row.location or {}).get('ip') == '8.8.8.8'
        assert (row.location or {}).get('city') == 'Test City'


class TestClientContext:
    def test_normalize_granted_and_denied(self):
        from apps.session_security.services.client_context import (
            build_login_audit_metadata,
            normalize_browser_geo,
            normalize_client_context,
        )

        granted = normalize_browser_geo(
            {'status': 'granted', 'latitude': 17.385, 'longitude': 78.4867, 'accuracy': 20}
        )
        assert granted['status'] == 'granted'
        assert granted['latitude'] == 17.385

        denied = normalize_browser_geo({'status': 'denied', 'latitude': 1, 'longitude': 2})
        assert denied['status'] == 'denied'
        assert denied['latitude'] is None

        bad = normalize_browser_geo(
            {'status': 'granted', 'latitude': 999, 'longitude': 78}
        )
        assert bad['status'] == 'unavailable'

        ctx = normalize_client_context(
            {
                'browser_geo': granted,
                'device': {
                    'browser_name': 'Chrome',
                    'browser_version': '126',
                    'os': 'Windows',
                    'device_type': 'desktop',
                    'screen': '1920x1080',
                    'timezone': 'Asia/Kolkata',
                    'language': 'en-US',
                    'user_agent': 'Mozilla/5.0',
                },
                'captured_at': '2026-07-23T16:00:00.000Z',
            }
        )
        meta = build_login_audit_metadata(
            client_context=ctx,
            ip_location={'city': 'Hyderabad', 'country': 'IN', 'source': 'ip-api'},
        )
        assert meta['location_resolution'] == 'browser'
        assert meta['device']['browser_name'] == 'Chrome'

        meta_deny = build_login_audit_metadata(
            client_context={
                'browser_geo': {'status': 'denied'},
                'device': {'browser_name': 'Chrome', 'device_type': 'desktop'},
            },
            ip_location={'city': 'Hyderabad', 'country': 'IN', 'source': 'memory'},
        )
        assert meta_deny['location_resolution'] == 'ip_fallback'


class TestAuditDisplayHeal:
    def test_stub_location_healed_in_serialize(self, db, user, settings):
        settings.GEOIP_PROVIDER = 'http'
        from apps.session_security.services.audit_query import serialize_audit_row
        from apps.session_security.services.geo import CachedGeoProvider

        # Force cached real lookup without network by seeding cache via stub provider swap
        class FakeInner:
            def lookup(self, ip):
                return {
                    'country': 'IN',
                    'country_name': 'India',
                    'region': 'Telangana',
                    'city': 'Hyderabad',
                    'latitude': 17.3,
                    'longitude': 78.4,
                    'source': 'ip-api',
                    'ip': ip,
                }

        from unittest.mock import patch

        row = UserLoginAuditLog.objects.create(
            user=user,
            event_type='idle_timeout',
            ip_address='8.8.8.8',
            location={
                'city': 'Test City',
                'region': 'Test Region',
                'country': 'IN',
                'source': 'memory',
                'ip': '8.8.8.8',
            },
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/126.0.0.0 Safari/537.36',
            message='idle',
        )
        with patch(
            'apps.session_security.services.geo.get_geo_provider',
            return_value=CachedGeoProvider(FakeInner(), ttl_seconds=60),
        ):
            payload = serialize_audit_row(row)
        assert payload['location_label'] == 'Hyderabad, Telangana, IN'
        assert 'Test City' not in payload['location_label']
        assert 'Chrome' in (payload.get('device_summary') or '')
        assert payload.get('location_source') != 'memory'


@pytest.mark.django_db
class TestLoginClientContext:
    def test_login_stores_browser_geo_and_device(self, api, user):
        res = api.post(
            '/api/auth/login/',
            {
                'phone': '9876543210',
                'password': 'TestPass123!',
                'client_context': {
                    'browser_geo': {
                        'status': 'granted',
                        'latitude': 17.385044,
                        'longitude': 78.486671,
                        'accuracy': 15,
                    },
                    'device': {
                        'browser_name': 'Chrome',
                        'browser_version': '126',
                        'os': 'Windows',
                        'device_type': 'desktop',
                        'screen': '1920x1080',
                        'timezone': 'Asia/Kolkata',
                        'language': 'en-IN',
                        'user_agent': 'Mozilla/5.0 (Windows NT 10.0) Chrome/126',
                    },
                    'captured_at': '2026-07-23T16:00:00.000Z',
                },
            },
            format='json',
            REMOTE_ADDR='127.0.0.1',
        )
        assert res.status_code == 200
        row = UserLoginAuditLog.objects.filter(user=user, event_type='login_success').latest(
            'created_at'
        )
        meta = row.metadata or {}
        assert meta.get('location_resolution') == 'browser'
        assert meta.get('browser_geo', {}).get('latitude') == 17.385044
        assert meta.get('device', {}).get('browser_name') == 'Chrome'
        assert meta.get('device', {}).get('os') == 'Windows'

        from apps.session_security.services.audit_query import serialize_audit_row

        payload = serialize_audit_row(row)
        assert '17.385' in (payload.get('precise_location_label') or '')
        assert 'Chrome' in (payload.get('device_summary') or '')

    def test_login_denied_geo_uses_ip_fallback(self, api, user):
        res = api.post(
            '/api/auth/login/',
            {
                'phone': '9876543210',
                'password': 'TestPass123!',
                'client_context': {
                    'browser_geo': {'status': 'denied'},
                    'device': {
                        'browser_name': 'Firefox',
                        'os': 'Linux',
                        'device_type': 'desktop',
                    },
                },
            },
            format='json',
            REMOTE_ADDR='127.0.0.1',
        )
        assert res.status_code == 200
        row = UserLoginAuditLog.objects.filter(user=user, event_type='login_success').latest(
            'created_at'
        )
        meta = row.metadata or {}
        assert meta.get('location_resolution') == 'ip_fallback'
        assert meta.get('browser_geo', {}).get('status') == 'denied'
        assert row.location  # IP geo still present
