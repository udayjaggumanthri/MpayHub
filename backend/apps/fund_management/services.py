"""
Fund management business logic services.
"""
from django.db import transaction as db_transaction
from decimal import Decimal
from apps.fund_management.models import LoadMoney, Payout
from apps.wallets.models import Wallet
from apps.transactions.models import Transaction, PassbookEntry
from apps.core.utils import generate_service_id
from apps.core.exceptions import InsufficientBalance, TransactionFailed
from apps.admin_panel.models import PaymentGateway, PayoutGateway


def calculate_service_charge(amount, gateway_id=None, transaction_type='payin'):
    """
    Calculate service charge based on gateway or default rates.
    
    Args:
        amount: Transaction amount
        gateway_id: Optional gateway ID
        transaction_type: 'payin' or 'payout'
    
    Returns:
        dict with charge_rate, charge, and net_amount
    """
    if gateway_id:
        try:
            gateway = PaymentGateway.objects.get(id=gateway_id, status='active')
            charge_rate = Decimal(str(gateway.charge_rate)) / 100
            charge = amount * charge_rate
            net_amount = amount - charge
            return {
                'charge_rate': gateway.charge_rate,
                'charge': charge,
                'net_amount': net_amount
            }
        except PaymentGateway.DoesNotExist:
            pass
    
    # Default rates
    if transaction_type == 'payin':
        charge_rate = Decimal('0.01')  # 1%
    else:
        charge_rate = Decimal('0.001')  # 0.1%
    
    charge = amount * charge_rate
    net_amount = amount - charge
    
    return {
        'charge_rate': float(charge_rate * 100),
        'charge': charge,
        'net_amount': net_amount
    }


@db_transaction.atomic
def process_load_money(user, amount, gateway_id):
    """
    Process load money transaction.
    
    Args:
        user: User object
        amount: Amount to load
        gateway_id: Payment gateway ID
    
    Returns:
        LoadMoney object
    """
    # Calculate charges
    charge_info = calculate_service_charge(amount, gateway_id, 'payin')
    
    # Create load money record
    load_money = LoadMoney.objects.create(
        user=user,
        amount=amount,
        gateway=gateway_id or 'default',
        charge=charge_info['charge'],
        net_credit=charge_info['net_amount'],
        status='PENDING',
        transaction_id=generate_service_id('load_money')
    )
    
    # Process payment via gateway (mock for now)
    try:
        # In production, integrate with actual payment gateway
        gateway_transaction_id = f"GTX{load_money.transaction_id}"
        load_money.gateway_transaction_id = gateway_transaction_id
        load_money.status = 'SUCCESS'
        load_money.save(update_fields=['gateway_transaction_id', 'status'])
        
        # Credit main wallet
        main_wallet = Wallet.get_wallet(user, 'main')
        main_wallet.credit(charge_info['net_amount'], reference=load_money.transaction_id)
        
        # Create transaction record
        Transaction.objects.create(
            user=user,
            transaction_type='payin',
            amount=amount,
            charge=charge_info['charge'],
            net_amount=charge_info['net_amount'],
            status='SUCCESS',
            service_id=load_money.transaction_id,
            reference=gateway_transaction_id
        )
        
        # Create passbook entry
        opening_balance = main_wallet.balance - charge_info['net_amount']
        closing_balance = main_wallet.balance
        PassbookEntry.objects.create(
            user=user,
            service='LOAD MONEY',
            service_id=load_money.transaction_id,
            description=f"LOAD MONEY, GATEWAY: {gateway_id or 'default'}, AMOUNT: {amount}, CHARGE: {charge_info['charge']}",
            debit_amount=Decimal('0.00'),
            credit_amount=charge_info['net_amount'],
            opening_balance=opening_balance,
            closing_balance=closing_balance
        )
        
        return load_money
    except Exception as e:
        load_money.status = 'FAILED'
        load_money.failure_reason = str(e)
        load_money.save(update_fields=['status', 'failure_reason'])
        raise TransactionFailed(f"Load money failed: {str(e)}")


@db_transaction.atomic
def process_payout(user, bank_account_id, amount, gateway_id=None):
    """
    Process payout transaction.
    
    Args:
        user: User object
        bank_account_id: Bank account ID
        amount: Amount to payout
        gateway_id: Optional payout gateway ID
    
    Returns:
        Payout object
    """
    from apps.bank_accounts.models import BankAccount
    
    # Get bank account
    try:
        bank_account = BankAccount.objects.get(id=bank_account_id, user=user)
    except BankAccount.DoesNotExist:
        raise ValueError("Bank account not found")
    
    # Calculate charges
    charge_info = calculate_service_charge(amount, None, 'payout')
    platform_fee = Decimal('2.50')  # Fixed platform fee
    total_deducted = amount + charge_info['charge'] + platform_fee
    
    # Check main wallet balance
    main_wallet = Wallet.get_wallet(user, 'main')
    if main_wallet.balance < total_deducted:
        raise InsufficientBalance(
            f"Insufficient balance. Available: ₹{main_wallet.balance}, Required: ₹{total_deducted}"
        )
    
    # Create payout record
    payout = Payout.objects.create(
        user=user,
        bank_account=bank_account,
        amount=amount,
        charge=charge_info['charge'],
        platform_fee=platform_fee,
        total_deducted=total_deducted,
        status='PENDING',
        transaction_id=generate_service_id('payout')
    )
    
    # Process payout via gateway (mock for now)
    try:
        # In production, integrate with actual payout gateway
        gateway_transaction_id = f"PTX{payout.transaction_id}"
        payout.gateway_transaction_id = gateway_transaction_id
        payout.status = 'SUCCESS'
        payout.save(update_fields=['gateway_transaction_id', 'status'])
        
        # Debit main wallet
        opening_balance = main_wallet.balance
        main_wallet.debit(total_deducted, reference=payout.transaction_id)
        closing_balance = main_wallet.balance
        
        # Create transaction record
        Transaction.objects.create(
            user=user,
            transaction_type='payout',
            amount=amount,
            charge=charge_info['charge'],
            platform_fee=platform_fee,
            status='SUCCESS',
            service_id=payout.transaction_id,
            reference=gateway_transaction_id
        )
        
        # Create passbook entry
        PassbookEntry.objects.create(
            user=user,
            service='PAYOUT',
            service_id=payout.transaction_id,
            description=f"PAID FOR PAYOUT, ACCOUNT: {bank_account.account_number[-4:]}, IFSC: {bank_account.ifsc}, AMOUNT: {amount}, CHARGE: {charge_info['charge']}, PLATFORM FEE: {platform_fee}",
            debit_amount=total_deducted,
            credit_amount=Decimal('0.00'),
            opening_balance=opening_balance,
            closing_balance=closing_balance
        )
        
        return payout
    except Exception as e:
        payout.status = 'FAILED'
        payout.failure_reason = str(e)
        payout.save(update_fields=['status', 'failure_reason'])
        raise TransactionFailed(f"Payout failed: {str(e)}")


def get_available_gateways(user_role, gateway_type='payment'):
    """
    Get available gateways for a user role.
    
    Args:
        user_role: User role
        gateway_type: 'payment' or 'payout'
    
    Returns:
        QuerySet of gateways
    """
    if gateway_type == 'payment':
        return PaymentGateway.objects.filter(
            status='active',
            visible_to_roles__contains=[user_role]
        )
    else:
        return PayoutGateway.objects.filter(
            status='active',
            visible_to_roles__contains=[user_role]
        )
