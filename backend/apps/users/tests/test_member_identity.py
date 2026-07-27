"""Tests for immutable member identity + mutable display_code."""
from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.users.identity import (
    allocate_member_number,
    format_display_code,
    format_member_id,
    public_display_code,
)
from apps.users.models import UserHierarchy, UserRoleHistory
from apps.users.services import admin_change_user_role, create_user
from apps.wallets.models import Wallet

User = get_user_model()


class IdentityFormatTests(TestCase):
    def test_format_member_and_display(self):
        self.assertEqual(format_member_id(4), 'MPH000004')
        self.assertEqual(format_display_code('Distributor', 4), 'D000004')
        self.assertEqual(format_display_code('Master Distributor', 4), 'MD000004')
        self.assertEqual(format_display_code('Admin', 1), 'A000001')
        self.assertEqual(format_display_code('Super Distributor', 2), 'SD000002')
        self.assertEqual(format_display_code('Retailer', 5), 'R000005')


class CreateUserIdentityTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            phone='9000000001',
            email='id_admin@test.com',
            password='pass123',
            role='Admin',
            user_id='LEGACYADMIN1',
            member_number=1,
            member_id='MPH000001',
            display_code='A000001',
        )
        from apps.authentication.models import MemberNumberSequence

        MemberNumberSequence.objects.update_or_create(
            key='global', defaults={'next_value': 2}
        )

    def test_mixed_roles_share_global_serial(self):
        sd, _ = create_user(
            {
                'phone': '9000000002',
                'email': 'sd@test.com',
                'role': 'Super Distributor',
                'first_name': 'S',
                'last_name': 'D',
            },
            self.admin,
        )
        md, _ = create_user(
            {
                'phone': '9000000003',
                'email': 'md@test.com',
                'role': 'Master Distributor',
                'first_name': 'M',
                'last_name': 'D',
            },
            self.admin,
        )
        dt, _ = create_user(
            {
                'phone': '9000000004',
                'email': 'dt@test.com',
                'role': 'Distributor',
                'first_name': 'D',
                'last_name': 'T',
            },
            self.admin,
        )
        r, _ = create_user(
            {
                'phone': '9000000005',
                'email': 'r@test.com',
                'role': 'Retailer',
                'first_name': 'R',
                'last_name': 'T',
            },
            self.admin,
        )

        self.assertEqual(sd.member_number, 2)
        self.assertEqual(sd.display_code, 'SD000002')
        self.assertEqual(sd.member_id, 'MPH000002')
        self.assertEqual(sd.user_id, 'MPH000002')

        self.assertEqual(md.member_number, 3)
        self.assertEqual(md.display_code, 'MD000003')
        self.assertEqual(dt.member_number, 4)
        self.assertEqual(dt.display_code, 'D000004')
        self.assertEqual(r.member_number, 5)
        self.assertEqual(r.display_code, 'R000005')

    def test_promote_distributor_updates_only_display_code(self):
        dt, _ = create_user(
            {
                'phone': '9000000010',
                'email': 'prom@test.com',
                'role': 'Distributor',
                'first_name': 'Promo',
                'last_name': 'User',
            },
            self.admin,
        )
        dt.member_number = 4
        dt.member_id = 'MPH000004'
        dt.display_code = 'D000004'
        dt.user_id = 'DT4LEGACY'
        dt.save(
            update_fields=['member_number', 'member_id', 'display_code', 'user_id', 'updated_at']
        )
        wallets_before = list(
            Wallet.objects.filter(user=dt).values_list('wallet_type', 'balance')
        )
        legacy = dt.user_id
        member_id = dt.member_id
        member_number = dt.member_number
        pk = dt.pk

        updated = admin_change_user_role(
            actor=self.admin, target=dt, new_role='Master Distributor'
        )
        updated.refresh_from_db()

        self.assertEqual(updated.role, 'Master Distributor')
        self.assertEqual(updated.display_code, 'MD000004')
        self.assertEqual(updated.member_number, member_number)
        self.assertEqual(updated.member_id, member_id)
        self.assertEqual(updated.user_id, legacy)
        self.assertEqual(updated.pk, pk)
        self.assertEqual(
            list(Wallet.objects.filter(user=updated).values_list('wallet_type', 'balance')),
            wallets_before,
        )
        hist = UserRoleHistory.objects.filter(user=updated).latest('created_at')
        self.assertEqual(hist.old_role, 'Distributor')
        self.assertEqual(hist.new_role, 'Master Distributor')
        self.assertEqual(hist.old_display_code, 'D000004')
        self.assertEqual(hist.new_display_code, 'MD000004')
        self.assertEqual(hist.legacy_user_id, legacy)

    def test_delete_does_not_reuse_member_number(self):
        u, _ = create_user(
            {
                'phone': '9000000020',
                'email': 'del@test.com',
                'role': 'Retailer',
                'first_name': 'Del',
                'last_name': 'Me',
            },
            self.admin,
        )
        deleted_number = u.member_number
        UserHierarchy.objects.filter(child_user=u).delete()
        u.delete()
        nxt = allocate_member_number()
        self.assertGreater(nxt, deleted_number)

    def test_public_display_code_fallback(self):
        u = User(
            phone='x',
            email='x@t.com',
            role='Retailer',
            user_id='R99',
            display_code='',
            member_id='',
        )
        u.pk = 99
        self.assertEqual(public_display_code(u), 'R99')


class MemberIdentityBackfillTests(TestCase):
    def test_backfill_preserves_legacy_user_id(self):
        import importlib.util
        from pathlib import Path

        mig_path = (
            Path(__file__).resolve().parents[2]
            / 'authentication'
            / 'migrations'
            / '0009_backfill_member_identity.py'
        )
        spec = importlib.util.spec_from_file_location('backfill_member_identity_mig', mig_path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        backfill_member_identity = mod.backfill_member_identity

        User.objects.all().delete()
        u1 = User.objects.create_user(
            phone='9110000001',
            email='bf1@test.com',
            password='pass',
            role='Admin',
            user_id='ADMIN9',
        )
        u2 = User.objects.create_user(
            phone='9110000002',
            email='bf2@test.com',
            password='pass',
            role='Distributor',
            user_id='DT9',
        )
        User.objects.all().update(member_number=None, member_id=None, display_code=None)
        pwd1 = User.objects.get(pk=u1.pk).password

        class FakeApps:
            @staticmethod
            def get_model(app, model):
                from django.apps import apps

                return apps.get_model(app, model)

        backfill_member_identity(FakeApps, None)
        u1.refresh_from_db()
        u2.refresh_from_db()
        self.assertEqual(u1.user_id, 'ADMIN9')
        self.assertEqual(u2.user_id, 'DT9')
        self.assertEqual(u1.member_number, 1)
        self.assertEqual(u1.display_code, 'A000001')
        self.assertEqual(u2.member_number, 2)
        self.assertEqual(u2.display_code, 'D000002')
        self.assertEqual(u1.password, pwd1)


class SearchIdentityTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            phone='9220000001',
            email='search_admin@test.com',
            password='pass123',
            role='Admin',
            user_id='LEGACYSDX',
            member_number=40,
            member_id='MPH000040',
            display_code='A000040',
            is_staff=True,
            is_superuser=True,
        )
        self.target = User.objects.create_user(
            phone='9220000002',
            email='search_target@test.com',
            password='pass123',
            role='Distributor',
            user_id='DT55',
            member_number=55,
            member_id='MPH000055',
            display_code='D000055',
        )
        UserHierarchy.objects.create(parent_user=self.admin, child_user=self.target)

    def test_list_search_matches_all_codes(self):
        from rest_framework.test import APIClient

        client = APIClient()
        client.force_authenticate(user=self.admin)
        for term in ('D000055', 'MPH000055', 'DT55'):
            res = client.get('/api/users/', {'search': term})
            self.assertEqual(res.status_code, 200, term)
            users = res.data.get('data', {}).get('users') or []
            ids = {u['id'] for u in users}
            self.assertIn(self.target.pk, ids, term)
