from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.exceptions import PermissionDenied

from apps.core.financial_access import (
    ACCESS_CODE_USER_DISABLED,
    ACCESS_CODE_USER_PAYMENTS_LOCKED,
    ACCESS_CODE_USER_RESTRICTED,
    assert_can_pay_in,
    assert_can_pay_out,
    user_may_login,
    user_may_pay_in,
    user_may_pay_out,
)

User = get_user_model()


def _retailer(**kwargs):
    defaults = dict(
        phone='9111111101',
        email='access-retailer@test.com',
        password='testpass123',
        role='Retailer',
        user_id='ACCRT1',
    )
    defaults.update(kwargs)
    phone = defaults.pop('phone')
    email = defaults.pop('email')
    password = defaults.pop('password')
    return User.objects.create_user(phone=phone, email=email, password=password, **defaults)


class UserAccessMatrixTests(TestCase):
    def test_active_retailer_full_access(self):
        user = _retailer()
        self.assertTrue(user_may_login(user))
        self.assertTrue(user_may_pay_in(user))
        self.assertTrue(user_may_pay_out(user))
        assert_can_pay_in(user)
        assert_can_pay_out(user)

    def test_restricted_blocks_pay_in_and_pay_out(self):
        user = _retailer(is_restricted=True)
        self.assertTrue(user_may_login(user))
        self.assertFalse(user_may_pay_in(user))
        self.assertFalse(user_may_pay_out(user))
        with self.assertRaises(PermissionDenied) as ctx:
            assert_can_pay_in(user)
        self.assertEqual(ctx.exception.detail['code'], ACCESS_CODE_USER_RESTRICTED)
        with self.assertRaises(PermissionDenied) as ctx:
            assert_can_pay_out(user)
        self.assertEqual(ctx.exception.detail['code'], ACCESS_CODE_USER_RESTRICTED)

    def test_payments_locked_allows_pay_in_not_pay_out(self):
        user = _retailer(payments_locked=True)
        self.assertTrue(user_may_pay_in(user))
        self.assertFalse(user_may_pay_out(user))
        assert_can_pay_in(user)
        with self.assertRaises(PermissionDenied) as ctx:
            assert_can_pay_out(user)
        self.assertEqual(ctx.exception.detail['code'], ACCESS_CODE_USER_PAYMENTS_LOCKED)

    def test_disabled_without_pay_in_flag_cannot_login(self):
        user = _retailer(is_active=False)
        self.assertFalse(user_may_login(user))
        self.assertFalse(user_may_pay_in(user))
        self.assertFalse(user_may_pay_out(user))

    def test_disabled_with_pay_in_flag_may_login_and_pay_in_only(self):
        user = _retailer(is_active=False, pay_in_allowed_when_disabled=True)
        self.assertTrue(user_may_login(user))
        self.assertTrue(user_may_pay_in(user))
        self.assertFalse(user_may_pay_out(user))
        assert_can_pay_in(user)
        with self.assertRaises(PermissionDenied) as ctx:
            assert_can_pay_out(user)
        self.assertEqual(ctx.exception.detail['code'], ACCESS_CODE_USER_DISABLED)

    def test_admin_role_blocked_from_financial_apis(self):
        admin = User.objects.create_user(
            phone='9222222201',
            email='access-admin@test.com',
            password='testpass123',
            role='Admin',
            user_id='ACCADM',
        )
        self.assertFalse(user_may_pay_in(admin))
        self.assertFalse(user_may_pay_out(admin))
