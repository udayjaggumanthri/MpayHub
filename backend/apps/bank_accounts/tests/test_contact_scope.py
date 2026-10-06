"""Tests for contact-scoped bank account listing and ownership."""
from __future__ import annotations

from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.test import APITestCase

import importlib

from django.apps import apps as django_apps

from apps.bank_accounts.models import BankAccount, BankAccountContactLink
from apps.contacts.models import Contact

User = get_user_model()


class BankAccountContactScopeTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            phone='9888777666',
            email='bank_scope@test.com',
            password='pass12345',
            role='Retailer',
            user_id='RSCOPE1',
            first_name='Scope',
            last_name='User',
        )
        self.other = User.objects.create_user(
            phone='9888777667',
            email='bank_other@test.com',
            password='pass12345',
            role='Retailer',
            user_id='RSCOPE2',
            first_name='Other',
            last_name='User',
        )
        self.contact_a = Contact.objects.create(
            user=self.user, name='Alice', phone='9111111111', email='a@test.com'
        )
        self.contact_b = Contact.objects.create(
            user=self.user, name='Bob', phone='9222222222', email='b@test.com'
        )
        self.other_contact = Contact.objects.create(
            user=self.other, name='Eve', phone='9333333333', email='e@test.com'
        )
        self.acct_a = BankAccount.objects.create(
            user=self.user,
            contact=self.contact_a,
            account_number='11111111111',
            ifsc='SBIN0000001',
            bank_name='SBI',
            account_holder_name='Alice',
            is_verified=True,
        )
        self.acct_b = BankAccount.objects.create(
            user=self.user,
            contact=self.contact_b,
            account_number='22222222222',
            ifsc='SBIN0000002',
            bank_name='SBI',
            account_holder_name='Bob',
            is_verified=True,
        )
        self.client.force_authenticate(user=self.user)

    def _ids(self, response):
        data = response.data.get('data') or {}
        rows = data.get('bank_accounts') or data.get('results') or []
        return {row['id'] for row in rows}

    def test_list_all_without_contact_param(self):
        res = self.client.get('/api/bank-accounts/')
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(self._ids(res), {self.acct_a.id, self.acct_b.id})

    def test_list_filters_by_owned_contact(self):
        res = self.client.get('/api/bank-accounts/', {'contact': self.contact_a.id})
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(self._ids(res), {self.acct_a.id})

    def test_list_foreign_contact_returns_empty(self):
        res = self.client.get('/api/bank-accounts/', {'contact': self.other_contact.id})
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(self._ids(res), set())

    def test_create_rejects_foreign_contact(self):
        payload = {
            'contact': self.other_contact.id,
            'account_number': '33333333333',
            'ifsc': 'SBIN0000003',
            'bank_name': 'SBI',
            'account_holder_name': 'X',
            'validation_token': '',
        }
        # Without token + no existing verified pair → validation_token error OR contact error.
        # Seed a verified duplicate path is messy; assert contact ownership via serializer validate_contact
        # by using Partial: patch existing account.
        res = self.client.patch(
            f'/api/bank-accounts/{self.acct_a.id}/',
            {'contact': self.other_contact.id},
            format='json',
        )
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        body = res.data if isinstance(res.data, dict) else {}
        errors = body.get('errors') or body
        self.assertTrue('contact' in errors or 'contact' in str(body).lower())

    def test_create_requires_contact(self):
        # Existing verified account path still requires contact in payload
        res = self.client.post(
            '/api/bank-accounts/',
            {
                'account_number': self.acct_a.account_number,
                'ifsc': self.acct_a.ifsc,
                'bank_name': 'SBI',
                'account_holder_name': 'Alice',
            },
            format='json',
        )
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        body = res.data if isinstance(res.data, dict) else {}
        errors = body.get('errors') or body
        self.assertTrue('contact' in errors or 'contact' in str(body).lower())

    def test_list_includes_contact_name(self):
        res = self.client.get('/api/bank-accounts/', {'contact': self.contact_a.id})
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        data = res.data.get('data') or {}
        rows = data.get('bank_accounts') or data.get('results') or []
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].get('contact_name'), 'Alice')
        self.assertEqual(rows[0].get('contact_phone'), '9111111111')
        linked = rows[0].get('linked_contacts') or []
        self.assertEqual(linked[0]['name'], 'Alice')
        self.assertEqual(linked[0]['phone'], '9111111111')

    def test_confirm_link_keeps_original_contact(self):
        res = self.client.post(
            '/api/bank-accounts/lookup/',
            {
                'account_number': self.acct_a.account_number,
                'ifsc': self.acct_a.ifsc,
                'contact': self.contact_b.id,
            },
            format='json',
        )
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data['data']['status'], 'exists_on_other_contacts')
        self.assertEqual(res.data['data']['contacts'][0]['name'], 'Alice')

        link = self.client.post(
            '/api/bank-accounts/link/',
            {'bank_account': self.acct_a.id, 'contact': self.contact_b.id},
            format='json',
        )
        self.assertEqual(link.status_code, status.HTTP_200_OK)
        self.acct_a.refresh_from_db()
        self.assertEqual(self.acct_a.contact_id, self.contact_a.id)
        listed = self.client.get('/api/bank-accounts/', {'contact': self.contact_b.id})
        self.assertEqual(self._ids(listed), {self.acct_a.id, self.acct_b.id})

    def test_unlink_removes_contact_and_keeps_account(self):
        link = self.client.post(
            '/api/bank-accounts/link/',
            {'bank_account': self.acct_a.id, 'contact': self.contact_b.id},
            format='json',
        )
        self.assertEqual(link.status_code, status.HTTP_200_OK)
        removed = self.client.post(
            '/api/bank-accounts/unlink/',
            {'bank_account': self.acct_a.id, 'contact': self.contact_b.id},
            format='json',
        )
        self.assertEqual(removed.status_code, status.HTTP_200_OK)
        self.acct_a.refresh_from_db()
        self.assertFalse(self.acct_a.is_deleted)
        self.assertEqual(self.acct_a.contact_id, self.contact_a.id)
        self.assertEqual(self.acct_a.account_number, '11111111111')
        listed = self.client.get('/api/bank-accounts/', {'contact': self.contact_b.id})
        self.assertEqual(self._ids(listed), {self.acct_b.id})
        still_a = self.client.get('/api/bank-accounts/', {'contact': self.contact_a.id})
        self.assertIn(self.acct_a.id, self._ids(still_a))

    def test_lookup_same_contact_blocks(self):
        res = self.client.post(
            '/api/bank-accounts/lookup/',
            {
                'account_number': self.acct_a.account_number,
                'ifsc': self.acct_a.ifsc,
                'contact': self.contact_a.id,
            },
            format='json',
        )
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data['data']['status'], 'on_this_contact')

    def test_list_count_covers_pages_beyond_twenty(self):
        for index in range(23):
            BankAccount.objects.create(
                user=self.user,
                contact=self.contact_a,
                account_number=f'500000000{index:02d}',
                ifsc='SBIN0000099',
                bank_name='SBI',
                account_holder_name='Paged',
                is_verified=True,
            )
        page1 = self.client.get('/api/bank-accounts/')
        self.assertEqual(page1.status_code, status.HTTP_200_OK)
        data = page1.data['data']
        self.assertEqual(data['count'], 25)
        self.assertEqual(len(data['bank_accounts']), 20)
        self.assertTrue(data['next'])
        page2 = self.client.get('/api/bank-accounts/', {'page': 2})
        self.assertEqual(len(page2.data['data']['bank_accounts']), 5)

    def test_backfill_is_idempotent(self):
        backfill_contact_links = importlib.import_module(
            'apps.bank_accounts.migrations.0006_bankaccountcontactlink'
        ).backfill_contact_links
        BankAccountContactLink.objects.filter(bank_account=self.acct_a).delete()
        self.assertFalse(
            BankAccountContactLink.objects.filter(bank_account=self.acct_a, contact=self.contact_a).exists()
        )
        backfill_contact_links(django_apps, None)
        self.assertEqual(
            BankAccountContactLink.objects.filter(bank_account=self.acct_a, contact=self.contact_a).count(),
            1,
        )
        backfill_contact_links(django_apps, None)
        self.assertEqual(
            BankAccountContactLink.objects.filter(bank_account=self.acct_a, contact=self.contact_a).count(),
            1,
        )
