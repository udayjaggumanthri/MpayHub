"""
BBPS business logic services.
"""
from django.db import transaction as db_transaction
from decimal import Decimal
from django.conf import settings
from apps.bbps.models import Biller, Bill, BillPayment
from apps.wallets.models import Wallet
from apps.transactions.agent_snapshot import passbook_initiator_db_fields, transaction_agent_db_fields
from apps.transactions.models import Transaction, PassbookEntry
from apps.core.utils import generate_service_id
from apps.core.exceptions import InsufficientBalance, TransactionFailed
from apps.integrations.bbps_client import BBPSClient
import random
import string


def calculate_bbps_charge(amount):
    """
    Calculate BBPS service charge (fixed ₹5.00).
    
    Args:
        amount: Bill amount
    
    Returns:
        dict with charge and total_deducted
    """
    charge = Decimal(str(settings.BBPS_SERVICE_CHARGE))
    total_deducted = amount + charge
    
    return {
        'charge': charge,
        'total_deducted': total_deducted
    }


def generate_request_id():
    """Generate a unique request ID for BBPS transactions."""
    chars = string.ascii_uppercase + string.digits
    return ''.join(random.choices(chars, k=20))


def fetch_bill(biller_name, category, **kwargs):
    """
    Fetch bill details from BBPS.
    
    Args:
        biller_name: Name of the biller
        category: Bill category
        **kwargs: Category-specific parameters
    
    Returns:
        Bill object or None
    """
    # Try to get biller
    try:
        biller = Biller.objects.get(name__icontains=biller_name, category=category, is_active=True)
    except Biller.DoesNotExist:
        # Create a mock biller if not found
        biller = Biller.objects.create(
            name=biller_name,
            category=category,
            biller_id=f"BILLER_{category.upper()}_{random.randint(1000, 9999)}"
        )
    
    # Fetch bill via BBPS client (with mock fallback)
    bbps_client = BBPSClient()
    
    try:
        bill_data = bbps_client.fetch_bill(biller.biller_id, category, **kwargs)
    except Exception:
        # Mock bill data for development
        bill_data = {
            'amount': Decimal('1000.00'),
            'due_date': None,
            'customer_details': kwargs
        }
    
    # Create bill record
    bill = Bill.objects.create(
        biller=biller,
        customer_details=kwargs,
        amount=bill_data.get('amount', Decimal('1000.00')),
        due_date=bill_data.get('due_date'),
        status='pending'
    )
    
    return bill


@db_transaction.atomic
def process_bill_payment(user, bill_data):
    """
    Process bill payment.
    
    Args:
        user: User object
        bill_data: Dictionary containing bill payment data
    
    Returns:
        BillPayment object
    """
    amount = Decimal(str(bill_data['amount']))
    charge_info = calculate_bbps_charge(amount)
    
    # Check BBPS wallet balance
    bbps_wallet = Wallet.get_wallet(user, 'bbps')
    if bbps_wallet.balance < charge_info['total_deducted']:
        raise InsufficientBalance(
            f"Insufficient BBPS wallet balance. Available: ₹{bbps_wallet.balance}, Required: ₹{charge_info['total_deducted']}"
        )
    
    # Create bill payment record
    bill_payment = BillPayment.objects.create(
        user=user,
        biller=bill_data.get('biller', ''),
        biller_id=bill_data.get('biller_id', ''),
        bill_type=bill_data.get('bill_type', ''),
        amount=amount,
        charge=charge_info['charge'],
        total_deducted=charge_info['total_deducted'],
        status='PENDING',
        service_id=generate_service_id('bbps'),
        request_id=generate_request_id()
    )
    
    # Process payment via BBPS client
    bbps_client = BBPSClient()
    
    try:
        # In production, integrate with actual BBPS API
        payment_result = bbps_client.process_payment(
            bill_payment.service_id,
            bill_payment.request_id,
            amount,
            bill_data
        )
        
        if payment_result.get('status') == 'SUCCESS':
            bill_payment.status = 'SUCCESS'
            bill_payment.save(update_fields=['status'])
            
            # Debit BBPS wallet
            opening_balance = bbps_wallet.balance
            bbps_wallet.debit(charge_info['total_deducted'], reference=bill_payment.service_id)
            closing_balance = bbps_wallet.balance
            
            # Create transaction record
            Transaction.objects.create(
                user=user,
                transaction_type='bbps',
                amount=amount,
                charge=charge_info['charge'],
                status='SUCCESS',
                service_id=bill_payment.service_id,
                request_id=bill_payment.request_id,
                bill_type=bill_data.get('bill_type', ''),
                biller=bill_data.get('biller', ''),
                service_family='bbps',
                **transaction_agent_db_fields(user),
            )

            # Create passbook entry
            PassbookEntry.objects.create(
                user=user,
                wallet_type='bbps',
                service='BBPS',
                service_id=bill_payment.service_id,
                description=f"PAID FOR {bill_data.get('bill_type', 'BILL PAYMENT')}, BILLER: {bill_data.get('biller', 'N/A')}, AMOUNT: {amount}, CHARGE: {charge_info['charge']}",
                debit_amount=charge_info['total_deducted'],
                credit_amount=Decimal('0.00'),
                opening_balance=opening_balance,
                closing_balance=closing_balance,
                service_charge=charge_info['charge'],
                principal_amount=amount,
                **passbook_initiator_db_fields(user),
            )
            
            return bill_payment
        else:
            bill_payment.status = 'FAILED'
            bill_payment.failure_reason = payment_result.get('message', 'Payment failed')
            bill_payment.save(update_fields=['status', 'failure_reason'])
            raise TransactionFailed(payment_result.get('message', 'Payment failed'))
    except Exception as e:
        bill_payment.status = 'FAILED'
        bill_payment.failure_reason = str(e)
        bill_payment.save(update_fields=['status', 'failure_reason'])
        raise TransactionFailed(f"Bill payment failed: {str(e)}")


def get_bill_categories():
    """Get list of bill categories."""
    return [
        {'id': 'credit-card', 'name': 'Credit Card'},
        {'id': 'electricity', 'name': 'Electricity'},
        {'id': 'insurance', 'name': 'Insurance'},
        {'id': 'mobile-recharge', 'name': 'Mobile Recharge'},
        {'id': 'dth', 'name': 'DTH'},
        {'id': 'fasttag', 'name': 'FASTag'},
        {'id': 'water', 'name': 'Water'},
        {'id': 'gas', 'name': 'Piped Gas'},
        {'id': 'municipal-tax', 'name': 'Municipal Tax'},
        {'id': 'education', 'name': 'Education'},
        {'id': 'loan-emi', 'name': 'Loan EMI'},
        {'id': 'broadband', 'name': 'Broadband'},
        {'id': 'landline', 'name': 'Landline Postpaid'},
        {'id': 'housing', 'name': 'Housing'},
        {'id': 'subscriptions', 'name': 'Subscriptions'},
    ]


def get_billers_by_category(category):
    """Get billers for a specific category."""
    return Biller.objects.filter(category=category, is_active=True)
