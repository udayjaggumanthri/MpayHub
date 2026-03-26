"""
User management business logic services.
"""
from django.db import transaction
from apps.authentication.models import User
from apps.users.models import UserProfile, KYC, UserHierarchy
from apps.core.utils import generate_user_id, validate_pan, validate_aadhaar
from apps.core.exceptions import InvalidUserRole
from apps.wallets.models import Wallet
from apps.authentication.services import send_otp


@transaction.atomic
def create_user(user_data, created_by):
    """
    Create a new user with profile, KYC, and wallets.
    
    Args:
        user_data: Dictionary containing user data
        created_by: User who is creating this user
    
    Returns:
        Created User object
    """
    # Validate role permissions
    target_role = user_data.get('role')
    if not UserHierarchy.can_create_role(created_by, target_role):
        raise InvalidUserRole(f"You cannot create users with role: {target_role}")
    
    # Generate user ID
    existing_user_ids = list(User.objects.filter(role=target_role).values_list('user_id', flat=True))
    user_id = generate_user_id(target_role, existing_user_ids)
    
    # Create user
    user = User.objects.create_user(
        phone=user_data['phone'],
        email=user_data['email'],
        password=user_data['password'],
        role=target_role,
        user_id=user_id,
        first_name=user_data.get('first_name', ''),
        last_name=user_data.get('last_name', '')
    )
    
    # Set MPIN (mandatory)
    if 'mpin' not in user_data or not user_data.get('mpin'):
        raise ValueError("MPIN is required and cannot be blank.")
    mpin = user_data['mpin']
    if len(mpin) != 6 or not mpin.isdigit():
        raise ValueError("MPIN must be exactly 6 digits.")
    user.set_mpin(mpin)
    
    # Create user profile
    UserProfile.objects.create(
        user=user,
        first_name=user_data.get('first_name', ''),
        last_name=user_data.get('last_name', ''),
        alternate_phone=user_data.get('alternate_phone', ''),
        business_name=user_data.get('business_name', ''),
        business_address=user_data.get('business_address', '')
    )
    
    # Create KYC record
    kyc = KYC.objects.create(user=user)
    if 'pan' in user_data and user_data['pan']:
        kyc.pan = user_data['pan'].upper()
        kyc.save(update_fields=['pan'])
    
    if 'aadhaar' in user_data and user_data['aadhaar']:
        kyc.aadhaar = user_data['aadhaar']
        kyc.save(update_fields=['aadhaar'])
    
    # Create hierarchy relationship
    UserHierarchy.objects.create(
        parent_user=created_by,
        child_user=user
    )
    
    # Create wallets for user
    Wallet.objects.create(user=user, wallet_type='main', balance=0.00)
    Wallet.objects.create(user=user, wallet_type='commission', balance=0.00)
    Wallet.objects.create(user=user, wallet_type='bbps', balance=0.00)
    
    return user


def verify_pan(user, pan):
    """
    Verify PAN number (mock implementation - integrate with actual PAN verification API).
    
    Args:
        user: User object
        pan: PAN number to verify
    
    Returns:
        bool: True if verified, False otherwise
    """
    if not validate_pan(pan):
        return False
    
    # Mock verification - in production, integrate with PAN verification API
    # For now, accept any valid PAN format
    kyc, created = KYC.objects.get_or_create(user=user)
    kyc.pan = pan.upper()
    kyc.pan_verified = True
    kyc.save(update_fields=['pan', 'pan_verified'])
    
    return True


def send_aadhaar_otp(user, aadhaar):
    """
    Send OTP for Aadhaar verification.
    
    Args:
        user: User object
        aadhaar: Aadhaar number
    
    Returns:
        OTP object
    """
    if not validate_aadhaar(aadhaar):
        raise ValueError("Invalid Aadhaar format")
    
    # Update KYC with Aadhaar
    kyc, created = KYC.objects.get_or_create(user=user)
    kyc.aadhaar = aadhaar
    kyc.save(update_fields=['aadhaar'])
    
    # Send OTP
    otp = send_otp(user.phone, purpose='aadhaar-verification')
    
    return otp


def verify_aadhaar_otp(user, otp_code):
    """
    Verify Aadhaar OTP and mark Aadhaar as verified.
    
    Args:
        user: User object
        otp_code: OTP code to verify
    
    Returns:
        bool: True if verified, False otherwise
    """
    from apps.authentication.services import verify_otp
    
    try:
        verify_otp(user.phone, otp_code, purpose='aadhaar-verification')
        
        # Mark Aadhaar as verified
        kyc = KYC.objects.get(user=user)
        kyc.aadhaar_verified = True
        kyc.save(update_fields=['aadhaar_verified'])
        
        return True
    except Exception:
        return False


def get_subordinates(user, role=None):
    """
    Get all subordinate users for a given user.
    
    Args:
        user: User object
        role: Optional role filter
    
    Returns:
        QuerySet of User objects
    """
    subordinates = UserHierarchy.get_subordinates(user)
    
    if role:
        subordinates = [u for u in subordinates if u.role == role]
    
    return subordinates
