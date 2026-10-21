from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from apps.fund_management.models import LoadMoney, PayinTaxInvoice
from apps.fund_management.payin_tax_invoice import (
    amount_in_words,
    assign_invoice_number,
    build_draft_from_load_money,
    recompute_payload,
    tax_breakdown,
)

User = get_user_model()


class PayinTaxInvoiceTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            phone='9000000001',
            email='invoice-admin@test.com',
            password='testpass123',
            role='Admin',
            user_id='INVADM1',
            first_name='Admin',
            last_name='User',
        )
        self.retailer = User.objects.create_user(
            phone='9000000002',
            email='invoice-retailer@test.com',
            password='testpass123',
            role='Retailer',
            user_id='INVRET1',
            first_name='Ret',
            last_name='User',
        )
        self.lm = LoadMoney.objects.create(
            user=self.retailer,
            amount=Decimal('100.00'),
            gateway='Toucan',
            charge=Decimal('1.00'),
            net_credit=Decimal('99.00'),
            customer_name='Ravi Kumar',
            customer_email='ravi@example.com',
            customer_phone='9123456780',
            status='SUCCESS',
            transaction_id='PMLMINVTEST001',
        )
        self.client = APIClient()

    def test_tax_breakdown_inclusive(self):
        parts = tax_breakdown(Decimal('118.00'), 18)
        self.assertEqual(parts['taxable'], Decimal('100.00'))
        self.assertEqual(parts['cgst'], Decimal('9.00'))
        self.assertEqual(parts['sgst'], Decimal('9.00'))
        self.assertIn('Rupees', amount_in_words(parts['total']))

    def test_draft_uses_contact_fields(self):
        draft = build_draft_from_load_money(self.lm)
        self.assertEqual(draft['customer']['name'], 'Ravi Kumar')
        self.assertEqual(draft['customer']['phone'], '9123456780')
        self.assertEqual(draft['total'], '100.00')

    def test_admin_can_get_and_save(self):
        self.client.force_authenticate(user=self.admin)
        get_res = self.client.get(f'/api/reports/payin/{self.lm.transaction_id}/tax-invoice/')
        self.assertEqual(get_res.status_code, 200, get_res.content)
        invoice = get_res.json()['data']['invoice']
        invoice['customer']['name'] = 'Custom Name'
        invoice['lines'] = [
            {'title': 'Service A', 'quantity': 1, 'price': '120', 'listAmount': '120'},
            {'title': 'Service B', 'quantity': 1, 'price': '80', 'listAmount': '80'},
        ]
        invoice['coupons'] = [{'name': 'Launch offer', 'amount': '100'}]
        put_res = self.client.put(
            f'/api/reports/payin/{self.lm.transaction_id}/tax-invoice/',
            {'invoice': invoice},
            format='json',
        )
        self.assertEqual(put_res.status_code, 200, put_res.content)
        saved = put_res.json()['data']['invoice']
        self.assertRegex(saved['invoiceNumber'], r'^PRA\d{8}\d{4}$')
        self.assertEqual(saved['customer']['name'], 'Custom Name')
        self.assertEqual(saved['total'], '100.00')
        self.assertEqual(saved['couponTotal'], '100.00')
        self.assertTrue(saved['amountMatchesTransaction'])
        self.assertEqual(PayinTaxInvoice.objects.filter(load_money=self.lm).count(), 1)

    def test_pra_invoice_numbers_are_daily_sequences(self):
        first = assign_invoice_number(when=self.lm.created_at)
        self.assertRegex(first, r'^PRA\d{8}0001$')
        PayinTaxInvoice.objects.create(
            load_money=self.lm,
            invoice_number=first,
            payload={},
            created_by=self.admin,
        )
        other = LoadMoney.objects.create(
            user=self.retailer,
            amount=Decimal('50.00'),
            gateway='Toucan',
            charge=Decimal('0.50'),
            net_credit=Decimal('49.50'),
            status='SUCCESS',
            transaction_id='PMLMINVTEST002',
        )
        second = assign_invoice_number(when=self.lm.created_at)
        self.assertRegex(second, r'^PRA\d{8}0002$')
        self.assertEqual(first[:11], second[:11])
        PayinTaxInvoice.objects.create(
            load_money=other,
            invoice_number=second,
            payload={},
            created_by=self.admin,
        )

    def test_coupons_reduce_total(self):
        payload = recompute_payload({
            'lines': [{'title': 'Course', 'quantity': 1, 'listAmount': '150'}],
            'coupons': [{'name': 'Disc', 'amount': '50'}],
            'transactionAmount': '100',
            'company': {'gstRatePercent': '18'},
        })
        self.assertEqual(payload['total'], '100.00')
        self.assertEqual(payload['linesGross'], '150.00')
        self.assertEqual(payload['couponTotal'], '50.00')

    def test_completed_get_auto_assigns_pra_number(self):
        self.client.force_authenticate(user=self.admin)
        self.lm.status = 'SUCCESS'
        self.lm.save(update_fields=['status'])
        res = self.client.get(f'/api/reports/payin/{self.lm.transaction_id}/tax-invoice/')
        self.assertEqual(res.status_code, 200, res.content)
        invoice = res.json()['data']['invoice']
        self.assertRegex(invoice['invoiceNumber'], r'^PRA\d{8}\d{4}$')
        self.assertTrue(invoice['saved'])
        self.assertEqual(invoice['transactionId'], self.lm.transaction_id)
        self.assertEqual(PayinTaxInvoice.objects.filter(load_money=self.lm).count(), 1)

    def test_retailer_forbidden(self):
        self.client.force_authenticate(user=self.retailer)
        res = self.client.get(f'/api/reports/payin/{self.lm.transaction_id}/tax-invoice/')
        self.assertIn(res.status_code, (403, 401))
