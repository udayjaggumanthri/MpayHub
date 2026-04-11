"""
User management business logic services.
"""
from django.db import transaction
from django.db.models import Q
from apps.authentication.models import User
from apps.users.models import UserProfile, KYC, UserHierarchy
from apps.core.utils import generate_user_id, validate_pan, validate_aadhaar
from apps.core.exceptions import InvalidUserRole
from apps.wallets.models import Wallet
from apps.authentication.services import send_otp, verify_otp

# Fixed first-login password when hierarchy creates a user without supplying one.
DEFAULT_ONBOARDING_PASSWORD = 'default123'


def assert_admin_may_deactivate_user(*, actor: User, target: User) -> None:
    """
    Enforce safe deactivation: no self-lockout, keep at least one active Admin or superuser.
    Raises ValueError with a user-facing message on violation.
    """
    if getattr(actor, 'role', None) != 'Admin':
        raise ValueError('Only administrators may disable user accounts.')
    if target.pk == actor.pk:
        raise ValueError('You cannot disable your own account.')
    if target.is_superuser or target.role == 'Admin':
        others = (
            User.objects.filter(is_active=True)
            .exclude(pk=target.pk)
            .filter(Q(is_superuser=True) | Q(role='Admin'))
        )
        if not others.exists():
            raise ValueError('Cannot disable the last active administrator account.')


def sync_kyc_verification_status(kyc):
    """Set verification_status to verified when both PAN and Aadhaar are verified."""
    if not kyc:
        return
    if kyc.pan_verified and kyc.aadhaar_verified and kyc.verification_status != 'verified':
        kyc.verification_status = 'verified'
        kyc.save(update_fields=['verification_status'])


@transaction.atomic
def create_user(user_data, created_by):
    """
    Create a new user with profile, KYC, and wallets.

    Hierarchy users submit basic details only. MPIN and full KYC are completed later by the user.

    Args:
        user_data: Dictionary containing user data
        created_by: User who is creating this user

    Returns:
        tuple: (Created User object, temporary_plain_password or None)
    """
    # Validate role permissions
    target_role = user_data.get('role')
    if not UserHierarchy.can_create_role(created_by, target_role):
        raise InvalidUserRole(f"You cannot create users with role: {target_role}")
    
    # Generate user ID
    existing_user_ids = list(User.objects.filter(role=target_role).values_list('user_id', flat=True))
    user_id = generate_user_id(target_role, existing_user_ids)

    raw_password = (user_data.get('password') or '').strip()
    temporary_plain_password = None
    if not raw_password:
        temporary_plain_password = DEFAULT_ONBOARDING_PASSWORD
        raw_password = DEFAULT_ONBOARDING_PASSWORD
    
    # Create user
    user = User.objects.create_user(
        phone=user_data['phone'],
        email=user_data['email'],
        password=raw_password,
        role=target_role,
        user_id=user_id,
        first_name=user_data.get('first_name', ''),
        last_name=user_data.get('last_name', '')
    )
    
    # MPIN: optional at creation — user sets after self-service KYC
    mpin = user_data.get('mpin')
    if mpin:
        if len(mpin) != 6 or not str(mpin).isdigit():
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
    
    # KYC shell — completed later by the end user (PAN / Aadhaar / OTP)
    kyc = KYC.objects.create(user=user)
    if user_data.get('pan'):
        kyc.pan = str(user_data['pan']).upper().strip()
        kyc.save(update_fields=['pan'])
    if user_data.get('aadhaar'):
        kyc.aadhaar = str(user_data['aadhaar']).strip()
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
    
    return user, temporary_plain_password


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

    normalized = str(pan).upper().strip()
    if KYC.objects.filter(pan=normalized).exclude(user=user).exists():
        return False

    # Mock verification - in production, integrate with PAN verification API
    kyc, _ = KYC.objects.get_or_create(user=user)
    kyc.pan = normalized
    kyc.pan_verified = True
    kyc.save(update_fields=['pan', 'pan_verified'])
    sync_kyc_verification_status(kyc)

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


def verify_aadhaar_otp(user, otp_code, aadhaar=None):
    """
    Verify Aadhaar OTP and mark Aadhaar as verified.

    If ``aadhaar`` is provided, it must match the number stored at send-otp time
    (prevents confusing the API with a mismatched body while reusing an OTP).

    Args:
        user: User object
        otp_code: OTP code to verify
        aadhaar: Optional; must match KYC.aadhaar when provided

    Returns:
        bool: True if verified, False otherwise
    """
    from apps.authentication.services import verify_otp

    try:
        kyc = KYC.objects.get(user=user)
    except KYC.DoesNotExist:
        return False

    if not kyc.aadhaar:
        return False

    if aadhaar is not None and str(aadhaar).strip() != str(kyc.aadhaar).strip():
        return False

    try:
        verify_otp(user.phone, otp_code, purpose='aadhaar-verification')
        kyc.aadhaar_verified = True
        kyc.save(update_fields=['aadhaar_verified'])
        sync_kyc_verification_status(kyc)
        return True
    except Exception:
        return False


def self_service_verify_pan(user, pan):
    """Step 1: PAN only (mock document check — valid format + uniqueness)."""
    normalized = str(pan).upper().strip()
    if not validate_pan(normalized):
        raise ValueError('Invalid PAN format.')

    if KYC.objects.filter(pan=normalized).exclude(user=user).exists():
        raise ValueError('PAN is already linked to another account.')

    kyc, _ = KYC.objects.get_or_create(user=user)
    if kyc.pan_verified and kyc.pan == normalized:
        return kyc
    if kyc.pan_verified and kyc.pan != normalized:
        raise ValueError('PAN is already verified for this account. Contact support to change it.')

    kyc.pan = normalized
    kyc.pan_verified = True
    kyc.save()
    sync_kyc_verification_status(kyc)
    return kyc


def self_service_send_aadhaar_otp(user, aadhaar):
    """Step 2a: store Aadhaar and send OTP to registered mobile (demo: also accept 123456 on verify)."""
    kyc = KYC.objects.filter(user=user).first()
    if not kyc or not kyc.pan_verified:
        raise ValueError('Verify PAN before Aadhaar.')

    normalized = str(aadhaar).strip()
    if not validate_aadhaar(normalized):
        raise ValueError('Invalid Aadhaar format.')

    if KYC.objects.filter(aadhaar=normalized).exclude(user=user).exists():
        raise ValueError('Aadhaar is already linked to another account.')

    kyc.aadhaar = normalized
    kyc.aadhaar_verified = False
    kyc.save(update_fields=['aadhaar', 'aadhaar_verified'])

    send_otp(user.phone, purpose='aadhaar-verification')
    return kyc


def self_service_verify_aadhaar_otp_only(user, otp_code):
    """Step 2b: verify OTP sent to mobile; demo shortcut OTP 123456."""
    from apps.core.exceptions import InvalidOTP

    kyc = KYC.objects.filter(user=user).first()
    if not kyc or not kyc.pan_verified:
        raise ValueError('Complete PAN verification first.')
    if not kyc.aadhaar:
        raise ValueError('Enter Aadhaar and request OTP first.')

    code = str(otp_code).strip()
    if code != '123456':
        try:
            verify_otp(user.phone, code, purpose='aadhaar-verification')
        except InvalidOTP as e:
            raise ValueError(str(e)) from e

    kyc.aadhaar_verified = True
    kyc.save(update_fields=['aadhaar_verified'])
    sync_kyc_verification_status(kyc)
    return kyc


def setup_initial_mpin(user, mpin, confirm_mpin):
    """First-time MPIN after KYC (hierarchy-onboarded users)."""
    if user.mpin_hash:
        raise ValueError('MPIN is already set. Use profile or support to reset.')
    kyc = KYC.objects.filter(user=user).first()
    if not kyc or not (kyc.pan_verified and kyc.aadhaar_verified):
        raise ValueError('Complete KYC before setting MPIN.')
    mpin = str(mpin).strip()
    confirm_mpin = str(confirm_mpin).strip()
    if len(mpin) != 6 or not mpin.isdigit():
        raise ValueError('MPIN must be exactly 6 digits.')
    if mpin != confirm_mpin:
        raise ValueError('MPIN and confirmation do not match.')
    user.set_mpin(mpin)
    return user


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


def _user_display_name(u: User) -> str:
    name = (u.get_full_name() or '').strip()
    return name or (u.email or u.phone or str(u.pk))


def build_user_lineage(user: User) -> dict:
    """
    Upline (root → immediate parent), direct parent links (who added / when),
    and a compact map path for admin UI.
    """
    # Direct parent edges (normal case: one row)
    direct_parents = []
    for rel in (
        UserHierarchy.objects.filter(child_user=user)
        .select_related('parent_user')
        .order_by('created_at')
    ):
        p = rel.parent_user
        direct_parents.append(
            {
                'user_id': p.user_id,
                'role': p.role,
                'name': _user_display_name(p),
                'linked_at': rel.created_at.isoformat() if rel.created_at else None,
            }
        )

    # Walk upline using first parent edge per level (matches commission upline behaviour)
    upline_steps = []
    seen = set()
    current = user
    while current is not None and current.id not in seen:
        seen.add(current.id)
        rel = (
            UserHierarchy.objects.filter(child_user=current)
            .select_related('parent_user')
            .order_by('created_at')
            .first()
        )
        if not rel:
            break
        p = rel.parent_user
        upline_steps.append(
            {
                'user_id': p.user_id,
                'role': p.role,
                'name': _user_display_name(p),
                'link_created_at': rel.created_at.isoformat() if rel.created_at else None,
            }
        )
        current = p

    upline_steps.reverse()

    path_ids = [s['user_id'] for s in upline_steps]
    if user.user_id:
        path_ids.append(user.user_id)
    map_path = ' → '.join(path_ids) if path_ids else (user.user_id or str(user.pk))

    # Direct reports (one level)
    direct_reports = []
    for rel in (
        UserHierarchy.objects.filter(parent_user=user)
        .select_related('child_user')
        .order_by('created_at')[:50]
    ):
        c = rel.child_user
        direct_reports.append(
            {
                'user_id': c.user_id,
                'role': c.role,
                'name': _user_display_name(c),
                'linked_at': rel.created_at.isoformat() if rel.created_at else None,
            }
        )

    return {
        'upline': upline_steps,
        'direct_parents': direct_parents,
        'map_path': map_path,
        'direct_reports': direct_reports,
        'direct_reports_total': UserHierarchy.objects.filter(parent_user=user).count(),
    }


@transaction.atomic
def admin_change_user_role(*, actor: User, target: User, new_role: str) -> User:
    """
    Admin-only role change with hierarchy safety checks.
    Does not regenerate user_id (stable identifiers).
    """
    if getattr(actor, 'role', None) != 'Admin':
        raise ValueError('Only administrators may change user roles.')
    if actor.pk == target.pk:
        raise ValueError('You cannot change your own role from this screen.')
    valid_roles = [c[0] for c in User.ROLE_CHOICES]
    if new_role not in valid_roles:
        raise ValueError('Invalid role.')
    if target.role == new_role:
        return target

    if target.role == 'Admin' and new_role != 'Admin':
        others = User.objects.filter(role='Admin', is_active=True).exclude(pk=target.pk).count()
        if others < 1:
            raise ValueError('Cannot demote the only active administrator.')

    # Subordinates must remain valid under the new role
    for rel in UserHierarchy.objects.filter(parent_user=target).select_related('child_user'):
        child = rel.child_user
        if not UserHierarchy.can_parent_role_create_child_role(new_role, child.role):
            raise ValueError(
                f'Cannot change role: subordinate {child.user_id} ({child.role}) is not allowed '
                f'under role {new_role}. Reassign or remove subordinates first.'
            )

    # Parent links must still allow this role (skip when promoting to Admin)
    if new_role != 'Admin':
        for rel in UserHierarchy.objects.filter(child_user=target).select_related('parent_user'):
            parent = rel.parent_user
            if not UserHierarchy.can_create_role(parent, new_role):
                raise ValueError(
                    f'Cannot change role: parent {parent.user_id} ({parent.role}) cannot have a direct '
                    f'report with role {new_role}. Use hierarchy tools or promote/demote parents first.'
                )

    target.role = new_role
    target.save(update_fields=['role', 'updated_at'])
    return target
