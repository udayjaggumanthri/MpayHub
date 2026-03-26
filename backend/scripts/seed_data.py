"""
Seed initial data script.
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.development')
django.setup()

from apps.authentication.models import User
from apps.users.models import UserProfile, KYC
from apps.wallets.models import Wallet
from apps.admin_panel.models import PaymentGateway, PayoutGateway

def seed_data():
    """Seed initial data."""
    # Create admin user if not exists
    if not User.objects.filter(role='Admin').exists():
        admin = User.objects.create_user(
            phone='9876543210',
            email='admin@mpayhub.com',
            password='admin123',
            role='Admin',
            user_id='ADMIN001',
            first_name='Admin',
            last_name='User'
        )
        admin.set_mpin('123456')
        UserProfile.objects.create(
            user=admin,
            first_name='Admin',
            last_name='User',
            business_name='mPayhub',
            business_address='Head Office'
        )
        KYC.objects.create(user=admin, pan_verified=True, aadhaar_verified=True)
        Wallet.objects.create(user=admin, wallet_type='main', balance=500000.00)
        Wallet.objects.create(user=admin, wallet_type='commission', balance=45000.00)
        Wallet.objects.create(user=admin, wallet_type='bbps', balance=25000.00)
        print("Admin user created successfully")
    
    # Create payment gateways
    if not PaymentGateway.objects.exists():
        PaymentGateway.objects.create(
            name='SLPE Gold Travel - Lite',
            charge_rate=1.0,
            status='active',
            visible_to_roles=['Admin', 'Master Distributor', 'Distributor', 'Retailer'],
            category='slpe-gold'
        )
        PaymentGateway.objects.create(
            name='Razorpay',
            charge_rate=1.1,
            status='active',
            visible_to_roles=['Admin', 'Master Distributor', 'Distributor', 'Retailer'],
            category='third-party'
        )
        print("Payment gateways created successfully")
    
    # Create payout gateways
    if not PayoutGateway.objects.exists():
        PayoutGateway.objects.create(
            name='IDFC Payout',
            status='active',
            visible_to_roles=['Admin', 'Master Distributor', 'Distributor', 'Retailer']
        )
        PayoutGateway.objects.create(
            name='PAYMAMA - PAYOUT',
            status='active',
            visible_to_roles=['Admin', 'Master Distributor', 'Distributor', 'Retailer']
        )
        print("Payout gateways created successfully")
    
    print("Data seeding completed!")

if __name__ == '__main__':
    seed_data()
