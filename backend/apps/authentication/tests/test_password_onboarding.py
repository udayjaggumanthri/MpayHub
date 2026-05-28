from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.authentication.password_onboarding import (
    clear_must_change_password,
    generate_temporary_password,
    issue_temporary_password,
)

User = get_user_model()


class PasswordOnboardingTests(TestCase):
    def test_generate_temporary_password_meets_policy(self):
        for _ in range(20):
            pwd = generate_temporary_password()
            self.assertGreaterEqual(len(pwd), 8)
            self.assertTrue(any(c.isalpha() for c in pwd))
            self.assertTrue(any(c.isdigit() for c in pwd))

    def test_unique_passwords_differ(self):
        passwords = {generate_temporary_password() for _ in range(10)}
        self.assertGreater(len(passwords), 1)

    def test_issue_and_clear_must_change_password(self):
        user = User.objects.create_user(
            phone='9111111199',
            email='poc-pwd@test.com',
            password='oldpass12',
            role='Retailer',
            user_id='PWON1',
        )
        plain = issue_temporary_password(user)
        user.refresh_from_db()
        self.assertTrue(user.must_change_password)
        self.assertTrue(user.check_password(plain))
        clear_must_change_password(user)
        user.refresh_from_db()
        self.assertFalse(user.must_change_password)
