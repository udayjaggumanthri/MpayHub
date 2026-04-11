"""
Verify mock payment gateway setup and flow.

What this script does:
1) Ensures mock API Master config exists for payment provider.
2) Ensures PaymentGateway and PayInPackage (provider=mock) exist and are active.
3) Ensures a contact exists for the selected user.
4) Creates a mock pay-in order and completes it via complete_mock_payin().
5) Prints before/after wallet balances and transaction references.

Run:
  python scripts/verify_mock_payment_gateway.py
  python scripts/verify_mock_payment_gateway.py --amount 1500 --phone 9000001234
  python scripts/verify_mock_payment_gateway.py --user-phone 9876543210
"""
import argparse
import os
import sys
from decimal import Decimal

import django

CURRENT_DIR = os.path.dirname(__file__)
PROJECT_DIR = os.path.abspath(os.path.join(CURRENT_DIR, '..'))
if PROJECT_DIR not in sys.path:
    sys.path.insert(0, PROJECT_DIR)

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.development')
django.setup()

from apps.admin_panel.models import PaymentGateway  # noqa: E402
from apps.authentication.models import User  # noqa: E402
from apps.contacts.models import Contact  # noqa: E402
from apps.fund_management.models import PayInPackage  # noqa: E402
from apps.fund_management.services import complete_mock_payin, create_payin_order  # noqa: E402
from apps.integrations.models import ApiMaster  # noqa: E402
from apps.wallets.models import Wallet  # noqa: E402


ROLE_VISIBILITY = [
    'Admin',
    'Super Distributor',
    'Master Distributor',
    'Distributor',
    'Retailer',
]


def ensure_api_master_mock():
    row, _ = ApiMaster.objects.update_or_create(
        provider_code='mock_payment_gateway',
        defaults={
            'provider_name': 'Mock Payment Gateway',
            'provider_type': 'payments',
            'base_url': 'https://mock-gateway.local/api',
            'auth_type': 'custom',
            'status': 'active',
            'priority': 1,
            'is_default': False,
            'supports_webhook': False,
            'webhook_path': '',
            'config_json': {
                'test_mode': True,
                'notes': 'Local verification config for mock flow',
                'test_method': 'GET',
                'test_path': '',
            },
            'secrets_encrypted': row_secrets_placeholder(),
        },
    )
    return row


def row_secrets_placeholder():
    # Script keeps secrets simple for mock; API side already encrypts on CRUD.
    # We intentionally leave it empty for this local verification row.
    return ''


def ensure_payment_gateway():
    gw, _ = PaymentGateway.objects.update_or_create(
        name='Mock Payment Gateway',
        defaults={
            'charge_rate': Decimal('1.00'),
            'status': 'active',
            'visible_to_roles': ROLE_VISIBILITY,
            'category': 'third-party',
        },
    )
    return gw


def ensure_payin_package(payment_gateway):
    pkg, _ = PayInPackage.objects.update_or_create(
        code='mock_gateway_verification',
        defaults={
            'display_name': 'Mock Gateway Verification Package',
            'payment_gateway': payment_gateway,
            'provider': 'mock',
            'min_amount': Decimal('1.00'),
            'max_amount_per_txn': Decimal('200000.00'),
            'gateway_fee_pct': Decimal('1.0000'),
            'admin_pct': Decimal('0.2400'),
            'super_distributor_pct': Decimal('0.0100'),
            'master_distributor_pct': Decimal('0.0200'),
            'distributor_pct': Decimal('0.0300'),
            'retailer_commission_pct': Decimal('0.0600'),
            'is_active': True,
            'sort_order': 999,
        },
    )
    return pkg


def select_user(user_phone=None):
    if user_phone:
        user = User.objects.filter(phone=user_phone, is_active=True).first()
        if user:
            return user
    user = User.objects.filter(role='Admin', is_active=True).order_by('id').first()
    if user:
        return user
    user = User.objects.filter(is_active=True).order_by('id').first()
    if user:
        return user
    raise RuntimeError('No active user found. Create a user first.')


def ensure_contact(user, phone):
    phone = ''.join([c for c in str(phone) if c.isdigit()])[:10]
    if len(phone) != 10:
        raise ValueError('Contact phone must be exactly 10 digits.')
    contact, _ = Contact.objects.update_or_create(
        user=user,
        phone=phone,
        defaults={
            'name': 'Mock Test Beneficiary',
            'email': f'mock.{phone}@example.com',
            'contact_role': Contact.ContactRole.END_USER,
        },
    )
    return contact


def run_verification(amount, user_phone=None, contact_phone='9000001234'):
    amount = Decimal(str(amount)).quantize(Decimal('0.01'))
    if amount <= 0:
        raise ValueError('Amount must be > 0')

    user = select_user(user_phone=user_phone)
    main_wallet = Wallet.get_wallet(user, 'main')
    commission_wallet = Wallet.get_wallet(user, 'commission')
    before_main = Decimal(str(main_wallet.balance))
    before_commission = Decimal(str(commission_wallet.balance))

    api_master = ensure_api_master_mock()
    payment_gateway = ensure_payment_gateway()
    package = ensure_payin_package(payment_gateway)
    contact = ensure_contact(user, contact_phone)

    load_money, payload = create_payin_order(
        user=user,
        package_id=package.id,
        gross=amount,
        contact_id=contact.id,
    )

    finalized = complete_mock_payin(user, load_money.transaction_id)
    main_wallet.refresh_from_db()
    commission_wallet.refresh_from_db()

    after_main = Decimal(str(main_wallet.balance))
    after_commission = Decimal(str(commission_wallet.balance))

    print('\n=== MOCK PAYMENT GATEWAY VERIFICATION: SUCCESS ===')
    print(f'User: {user.phone} ({user.role})')
    print(f'API Master: {api_master.provider_code} [{api_master.status}]')
    print(f'Payment Gateway: {payment_gateway.name} [{payment_gateway.status}]')
    print(f'Package: {package.code} (provider={package.provider})')
    print(f'Contact: {contact.name} / {contact.phone}')
    print(f'Amount: INR {amount}')
    print(f'Transaction ID: {finalized.transaction_id}')
    print(f'Provider Payment ID: {finalized.provider_payment_id}')
    print(f'Status: {finalized.status}')
    print(f'Main Wallet: INR {before_main} -> INR {after_main} (Delta INR {after_main - before_main})')
    print(
        f'Commission Wallet: INR {before_commission} -> INR {after_commission} '
        f'(Delta INR {after_commission - before_commission})'
    )
    if payload.get('fee_preview'):
        print('Fee Preview Snapshot:', payload['fee_preview'])
    print('=================================================\n')


def main():
    parser = argparse.ArgumentParser(description='Verify mock payment gateway flow.')
    parser.add_argument('--amount', default='1000.00', help='Gross pay-in amount (default: 1000.00)')
    parser.add_argument('--user-phone', default='', help='Optional user phone to run under')
    parser.add_argument('--phone', default='9000001234', help='Contact phone for mock beneficiary')
    args = parser.parse_args()

    try:
        run_verification(
            amount=args.amount,
            user_phone=args.user_phone or None,
            contact_phone=args.phone,
        )
    except Exception as exc:
        print('\n=== MOCK PAYMENT GATEWAY VERIFICATION: FAILED ===')
        print(str(exc))
        print('================================================\n')
        raise


if __name__ == '__main__':
    main()
