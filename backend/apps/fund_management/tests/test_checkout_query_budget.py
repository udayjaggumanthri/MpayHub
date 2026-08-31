"""Query-budget checks for pay-in checkout options (no per-package N+1)."""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext

from apps.admin_panel.models import PaymentGateway
from apps.fund_management.checkout_options import list_payin_checkout_options_for_user
from apps.fund_management.models import PayInPackage, UserPackageAssignment
from apps.fund_management.package_gateways import sync_package_gateway_links
from apps.fund_management.package_qr_accounts import sync_package_qr_links
from apps.fund_management.models import PayInQrAccount
from django.core.files.uploadedfile import SimpleUploadedFile

User = get_user_model()


def _png():
    # Minimal 1x1 PNG
    return (
        b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01'
        b'\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\x0cIDATx\x9cc\xf8\x0f\x00'
        b'\x00\x01\x01\x00\x05\x18\xd8N\x00\x00\x00\x00IEND\xaeB`\x82'
    )


class CheckoutOptionsQueryBudgetTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            phone='9555555577',
            email='checkout-budget@test.com',
            password='secret123',
            role='Retailer',
            user_id='CHKBUD1',
        )

    def _make_package_with_rails(self, code: str):
        pkg = PayInPackage.objects.create(
            code=code,
            display_name=code,
            provider='mock',
            gateway_fee_pct=Decimal('1.0000'),
            admin_pct=Decimal('0.2400'),
            super_distributor_pct=Decimal('0.0100'),
            master_distributor_pct=Decimal('0.0200'),
            distributor_pct=Decimal('0.0300'),
            retailer_commission_pct=Decimal('0.0000'),
            sort_order=0,
            is_default=False,
        )
        gw = PaymentGateway.objects.create(
            name=f'GW-{code}',
            charge_rate=Decimal('1.00'),
            status='active',
            visible_to_roles=['Retailer'],
        )
        sync_package_gateway_links(pkg, [gw.id], default_gateway_id=gw.id)
        qr = PayInQrAccount.objects.create(
            display_name=f'QR-{code}',
            upi_vpa=f'{code}@upi',
            qr_image=SimpleUploadedFile(f'{code}.png', _png(), content_type='image/png'),
            status='active',
            sort_order=0,
        )
        sync_package_qr_links(pkg, [qr.id], default_qr_account_id=qr.id)
        UserPackageAssignment.objects.create(user=self.user, package=pkg)
        return pkg

    def test_checkout_options_query_count_stable_across_packages(self):
        self._make_package_with_rails('chk_a')
        with CaptureQueriesContext(connection) as ctx1:
            opts1 = list_payin_checkout_options_for_user(self.user)
        n1 = len(ctx1.captured_queries)
        self.assertGreaterEqual(len(opts1), 2)

        self._make_package_with_rails('chk_b')
        self._make_package_with_rails('chk_c')
        with CaptureQueriesContext(connection) as ctx3:
            opts3 = list_payin_checkout_options_for_user(self.user)
        n3 = len(ctx3.captured_queries)
        self.assertGreaterEqual(len(opts3), 6)
        # Prefetch keeps query growth flat (not +2 queries per extra package).
        self.assertLessEqual(n3, n1 + 3, f'n1={n1} n3={n3}')
        self.assertLessEqual(n3, 15)
