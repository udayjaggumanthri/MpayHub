"""
User management business logic services.
"""
import json
import logging

from django.db import transaction
from django.db.models import Q

from apps.authentication.models import User

logger = logging.getLogger(__name__)

ACCESS_CONTROL_FIELDS = (
    'is_active',
    'is_restricted',
    'payments_locked',
    'pay_in_allowed_when_disabled',
)
from apps.users.models import UserProfile, KYC, UserHierarchy, KycVerificationAttempt
from apps.core.utils import generate_user_id, validate_pan, validate_aadhaar
from apps.core.exceptions import InvalidUserRole
from apps.wallets.models import Wallet
from apps.authentication.password_onboarding import issue_temporary_password
from apps.authentication.services import send_otp, verify_otp


def _access_controls_snapshot(user: User) -> dict:
    return {f: bool(getattr(user, f, False)) for f in ACCESS_CONTROL_FIELDS}


@transaction.atomic
def apply_user_access_controls(*, actor: User, target: User, patch: dict) -> User:
    """
    Admin-only: update account access flags (login, restrict, lock payments, pay-in when disabled).

    When re-enabling (is_active=True), clears pay_in_allowed_when_disabled.
    """
    if getattr(actor, 'role', None) != 'Admin':
        raise ValueError('Only administrators may change user access controls.')

    before = _access_controls_snapshot(target)
    update_fields: list[str] = []

    if 'is_active' in patch:
        new_active = bool(patch['is_active'])
        if not new_active and new_active != target.is_active:
            assert_admin_may_deactivate_user(actor=actor, target=target)
        target.is_active = new_active
        update_fields.append('is_active')
        if new_active:
            target.pay_in_allowed_when_disabled = False
            if 'pay_in_allowed_when_disabled' not in patch:
                update_fields.append('pay_in_allowed_when_disabled')

    for field in ('is_restricted', 'payments_locked', 'pay_in_allowed_when_disabled'):
        if field in patch:
            setattr(target, field, bool(patch[field]))
            update_fields.append(field)

    if not update_fields:
        return target

    if not target.is_active and not target.pay_in_allowed_when_disabled:
        target.pay_in_allowed_when_disabled = False
        if 'pay_in_allowed_when_disabled' not in update_fields:
            update_fields.append('pay_in_allowed_when_disabled')

    target.save(update_fields=list(dict.fromkeys(update_fields)))
    target.refresh_from_db()

    after = _access_controls_snapshot(target)
    if before != after:
        logger.info(
            '%s',
            json.dumps(
                {
                    'event': 'user_access_controls_changed',
                    'actor_id': actor.pk,
                    'target_id': target.pk,
                    'target_user_id': str(target.user_id or ''),
                    'before': before,
                    'after': after,
                },
                default=str,
            ),
        )
    return target


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


def assert_admin_may_delete_user(*, actor: User, target: User) -> None:
    """
    Enforce safe permanent deletion: admin only, no self-delete, keep at least one admin,
    and no users with active subordinates in the hierarchy.
    """
    if getattr(actor, 'role', None) != 'Admin' and not getattr(actor, 'is_superuser', False):
        raise ValueError('Only administrators may delete user accounts.')
    if target.pk == actor.pk:
        raise ValueError('You cannot delete your own account.')
    if target.is_superuser or target.role == 'Admin':
        others = User.objects.filter(Q(is_superuser=True) | Q(role='Admin')).exclude(pk=target.pk)
        if not others.exists():
            raise ValueError('Cannot delete the last administrator account.')
    if UserHierarchy.objects.filter(parent_user=target, is_deleted=False).exists():
        raise ValueError(
            'Cannot delete a user who has subordinates. Reassign or delete their downline users first.'
        )


def delete_user_account(*, actor: User, target: User) -> str:
    """
    Permanently delete a user and all related data (CASCADE).
    Returns the deleted user's public user_id for audit/logging.
    """
    assert_admin_may_delete_user(actor=actor, target=target)
    public_id = str(target.user_id or target.pk)
    actor_id = str(getattr(actor, 'user_id', None) or actor.pk)
    with transaction.atomic():
        target.delete()
    logger.info(
        'User account permanently deleted: target=%s by_admin=%s',
        public_id,
        actor_id,
    )
    return public_id


def sync_kyc_verification_status(kyc):
    """Set verification_status to verified when both PAN and Aadhaar are verified."""
    if not kyc:
        return
    if kyc.pan_verified and kyc.aadhaar_verified and kyc.verification_status != 'verified':
        kyc.verification_status = 'verified'
        kyc.save(update_fields=['verification_status'])
        try:
            from apps.notifications.email_helpers import login_url_default, mask_pan, user_display_name
            from apps.notifications.services.email_dispatch import EmailNotificationService

            user = kyc.user
            to_email = (getattr(user, 'email', None) or '').strip()
            if to_email:
                EmailNotificationService.dispatch(
                    'kyc.verification.complete',
                    to_email,
                    {
                        'name': user_display_name(user),
                        'user_id': getattr(user, 'user_id', '') or '',
                        'pan_masked': mask_pan(getattr(kyc, 'pan', '') or ''),
                        'verification_status': 'verified',
                    },
                    user_id=user.pk,
                    idempotency_key=f'kyc:verified:{user.pk}',
                )
        except Exception:
            pass


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
    
    raw_password = (user_data.get('password') or '').strip()
    temporary_plain_password = None

    # Allocate user_id against all rows sharing this prefix (user_id is globally unique).
    user = None
    last_integrity_error = None
    for _attempt in range(5):
        user_id = generate_user_id(target_role)
        try:
            user = User.objects.create_user(
                phone=user_data['phone'],
                email=user_data['email'],
                password=raw_password if raw_password else None,
                role=target_role,
                user_id=user_id,
                first_name=user_data.get('first_name', ''),
                last_name=user_data.get('last_name', ''),
            )
            break
        except Exception as exc:
            from django.db import IntegrityError

            if isinstance(exc, IntegrityError) and 'user_id' in str(exc).lower():
                last_integrity_error = exc
                continue
            raise
    if user is None:
        if last_integrity_error is not None:
            raise last_integrity_error
        raise RuntimeError('Could not allocate a unique user_id.')
    if not raw_password:
        temporary_plain_password = issue_temporary_password(user)
    
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

    # Auto-assign default package (if configured) or packages passed during creation (Admin only)
    from apps.fund_management.services import auto_assign_default_package, assign_package_to_user

    creator_role = (getattr(created_by, 'role', None) or '').strip()
    package_ids = user_data.get('package_ids', []) if creator_role == 'Admin' else []
    if package_ids:
        # Assign specific packages passed during user creation (Admin only)
        for pkg_id in package_ids:
            assign_package_to_user(
                assigner=created_by,
                target_user=user,
                package_id=pkg_id,
            )
    else:
        # Auto-assign default package for new users
        auto_assign_default_package(user, assigner=created_by)
    
    return user, temporary_plain_password


def _resolve_pan_holder_name(user, name: str | None = None) -> str:
    explicit = str(name or '').strip()
    if explicit:
        return explicit
    profile = getattr(user, 'profile', None)
    if profile is not None:
        fn = f'{profile.first_name or ""} {profile.last_name or ""}'.strip()
        if fn:
            return fn
    full = (user.get_full_name() or '').strip()
    if full:
        return full
    raise ValueError('Name as per PAN is required for verification.')


def parse_kyc_dob_safe(value):
    from apps.integrations.kyc.profile_sync import parse_kyc_dob
    return parse_kyc_dob(value)


def _apply_pan_verified(user, *, pan: str, provider_code: str, result):
    from django.db import transaction
    from django.utils import timezone

    from apps.integrations.kyc.profile_sync import build_kyc_details, extract_dob_from_raw
    from apps.integrations.kyc.profile_sync_orchestrator import handle_post_kyc_profile_sync
    from apps.integrations.kyc.types import PanVerifyResult

    with transaction.atomic():
        if KYC.objects.select_for_update().filter(pan=pan).exclude(user=user).exists():
            raise ValueError('PAN is already linked to another account.')
        kyc, _ = KYC.objects.select_for_update().get_or_create(user=user)
        kyc.pan = pan
        kyc.pan_verified = True
        kyc.pan_verified_at = timezone.now()
        kyc.save(update_fields=['pan', 'pan_verified', 'pan_verified_at', 'updated_at'])

    kyc_details = {}
    if isinstance(result, PanVerifyResult):
        registered_name = result.registered_name or ''
        dob = extract_dob_from_raw(result.raw) or parse_kyc_dob_safe(result.date_of_birth)
        sync_result = handle_post_kyc_profile_sync(
            user,
            source='pan',
            trigger='onboarding_pan',
            verified_name=registered_name,
            verified_dob=dob,
            metadata={'provider_code': provider_code, 'reference_id': str(result.reference_id or '')},
        )
        profile_updated = sync_result.profile_updated
        kyc_details = build_kyc_details(
            pan=pan,
            name=registered_name,
            dob=dob,
            pan_type=result.pan_type,
            profile_updated=profile_updated,
        )
        if sync_result.to_api_dict():
            kyc_details['profile_sync'] = sync_result.to_api_dict()
        KycVerificationAttempt.objects.create(
            user=user,
            provider_code=provider_code,
            verification_id=result.verification_id,
            reference_id=str(result.reference_id or ''),
            status=result.status or 'VALID',
            request_meta={'pan': pan},
            response_meta={
                'registered_name': registered_name,
                'date_of_birth': kyc_details.get('date_of_birth', ''),
                'pan_type': result.pan_type,
                'message': result.message,
                'name_match_score': result.raw.get('name_match_score') if isinstance(result.raw, dict) else '',
                'name_match_result': result.raw.get('name_match_result') if isinstance(result.raw, dict) else '',
                'aadhaar_seeding_status': result.raw.get('aadhaar_seeding_status') if isinstance(result.raw, dict) else '',
                'father_name': result.raw.get('father_name') if isinstance(result.raw, dict) else '',
                'pan_status': result.status or ('VALID' if isinstance(result.raw, dict) and result.raw.get('valid') else ''),
            },
        )
        from apps.users.kyc_display import persist_pan_verified_identity

        persist_pan_verified_identity(
            kyc,
            pan=pan,
            name=registered_name,
            dob=dob,
            pan_type=result.pan_type,
            provider_code=provider_code,
            reference_id=result.reference_id,
            verified_at=kyc.pan_verified_at,
            profile_updated=profile_updated,
            raw=result.raw if isinstance(result.raw, dict) else None,
        )
    sync_kyc_verification_status(kyc)
    return kyc, kyc_details


def verify_pan(user, pan, name: str | None = None):
    """
    Verify PAN via configured Cashfree provider (admin / hierarchy flow).
    """
    if not validate_pan(pan):
        return False

    normalized = str(pan).upper().strip()
    if KYC.objects.filter(pan=normalized).exclude(user=user).exists():
        return False

    try:
        holder_name = _resolve_pan_holder_name(user, name)
        from apps.integrations.kyc.exceptions import KycConfigurationError, KycVerificationFailed
        from apps.integrations.kyc.registry import resolve_pan_provider

        provider = resolve_pan_provider()
        result = provider.verify_pan(user=user, pan=normalized, name=holder_name)
        _apply_pan_verified(user, pan=normalized, provider_code=provider.provider_code, result=result)
        return True  # noqa: profile synced inside _apply_pan_verified
    except (KycConfigurationError, KycVerificationFailed, ValueError):
        return False
    except Exception:
        logger.exception('PAN verification failed for user %s', getattr(user, 'pk', None))
        return False


def send_aadhaar_otp(user, aadhaar):
    """Deprecated: use init_digilocker_aadhaar."""
    raise ValueError('Aadhaar OTP is no longer supported. Use DigiLocker verification.')


def verify_aadhaar_otp(user, otp_code, aadhaar=None):
    """Deprecated: use complete_digilocker_aadhaar."""
    return False


def self_service_verify_pan(user, pan, name: str | None = None):
    """Step 1: verify PAN via Cashfree (sync or PAN 360 per ApiMaster config)."""
    from django.db import transaction

    from apps.integrations.kyc.exceptions import KycConfigurationError, KycVerificationFailed
    from apps.integrations.kyc.registry import resolve_pan_provider

    normalized = str(pan).upper().strip()
    if not validate_pan(normalized):
        raise ValueError('Invalid PAN format.')

    holder_name = str(name or '').strip()
    if not holder_name:
        raise ValueError('Name as per PAN is required for verification.')

    with transaction.atomic():
        kyc = KYC.objects.select_for_update().filter(user=user).first()
        if not kyc:
            kyc = KYC.objects.create(user=user)
        if kyc.pan_verified and kyc.pan == normalized:
            return kyc, {}
        if kyc.pan_verified and kyc.pan != normalized:
            raise ValueError('PAN is already verified for this account. Contact support to change it.')
        if KYC.objects.filter(pan=normalized).exclude(user=user).exists():
            raise ValueError('PAN is already linked to another account.')

    try:
        provider = resolve_pan_provider()
    except KycConfigurationError as e:
        raise ValueError(str(e)) from e
    try:
        result = provider.verify_pan(user=user, pan=normalized, name=holder_name)
    except KycVerificationFailed as e:
        raise ValueError(str(e)) from e
    except Exception as e:
        logger.exception('Cashfree PAN verification error')
        raise ValueError('PAN verification is temporarily unavailable. Please try again.') from e

    try:
        return _apply_pan_verified(
            user, pan=normalized, provider_code=provider.provider_code, result=result
        )
    except ValueError:
        raise


def init_digilocker_aadhaar(user, aadhaar_number: str | None = None):
    """Start Cashfree DigiLocker consent flow; returns init result with redirect URL."""
    from apps.integrations.kyc.exceptions import KycConfigurationError, KycVerificationFailed
    from apps.integrations.kyc.registry import resolve_aadhaar_provider

    kyc = KYC.objects.filter(user=user).first()
    if not kyc or not kyc.pan_verified:
        raise ValueError('Verify PAN before Aadhaar.')

    if aadhaar_number:
        normalized = str(aadhaar_number).strip()
        if not validate_aadhaar(normalized):
            raise ValueError('Invalid Aadhaar format.')
        if KYC.objects.filter(aadhaar=normalized).exclude(user=user).exists():
            raise ValueError('Aadhaar is already linked to another account.')

    try:
        provider = resolve_aadhaar_provider()
    except KycConfigurationError as e:
        raise ValueError(str(e)) from e
    try:
        return provider.init_session(user=user, aadhaar_number=aadhaar_number)
    except KycVerificationFailed as e:
        raise ValueError(str(e)) from e
    except Exception as e:
        logger.exception('DigiLocker init failed')
        raise ValueError('Could not start DigiLocker verification. Please try again.') from e


def poll_digilocker_status(user, verification_id: str):
    """Poll Cashfree DigiLocker session status."""
    from apps.integrations.kyc.registry import resolve_aadhaar_provider
    from apps.users.models import KycDigilockerSession

    vid = str(verification_id or '').strip()
    if not vid:
        raise ValueError('verification_id is required.')
    if not KycDigilockerSession.objects.filter(user=user, verification_id=vid, is_deleted=False).exists():
        raise ValueError('Invalid or expired DigiLocker session.')
    provider = resolve_aadhaar_provider()
    return provider.get_status(verification_id=vid)


def complete_digilocker_aadhaar(user, verification_id: str):
    """Finalize DigiLocker after AUTHENTICATED; marks aadhaar_verified on KYC."""
    from django.db import transaction
    from django.utils import timezone

    from apps.integrations.kyc.exceptions import KycVerificationFailed
    from apps.integrations.kyc.profile_sync import build_kyc_details, extract_dob_from_raw
    from apps.integrations.kyc.profile_sync_orchestrator import handle_post_kyc_profile_sync
    from apps.integrations.kyc.registry import resolve_aadhaar_provider
    from apps.users.kyc_display import persist_aadhaar_verified_identity
    from apps.users.models import KycDigilockerSession

    vid = str(verification_id or '').strip()
    if not vid:
        raise ValueError('verification_id is required.')
    if not KycDigilockerSession.objects.filter(user=user, verification_id=vid, is_deleted=False).exists():
        raise ValueError('Invalid or expired DigiLocker session.')

    with transaction.atomic():
        kyc = KYC.objects.select_for_update().filter(user=user).first()
        if not kyc or not kyc.pan_verified:
            raise ValueError('Complete PAN verification first.')
        if kyc.aadhaar_verified:
            return kyc, build_kyc_details(
                pan=kyc.pan or '',
                name='',
                aadhaar_masked=kyc.aadhaar or '',
            )

    provider = resolve_aadhaar_provider()
    try:
        doc = provider.complete_if_authenticated(user=user, verification_id=vid)
    except KycVerificationFailed as e:
        raise ValueError(str(e)) from e

    with transaction.atomic():
        kyc = KYC.objects.select_for_update().filter(user=user).first()
        if not kyc:
            raise ValueError('Complete PAN verification first.')
        if kyc.aadhaar_verified:
            return kyc, build_kyc_details(
                pan=kyc.pan or '',
                name=doc.name or '',
                aadhaar_masked=kyc.aadhaar or '',
            )
        if doc.uid_masked and KYC.objects.filter(aadhaar=doc.uid_masked).exclude(user=user).exists():
            raise ValueError('Aadhaar is already linked to another account.')
        if doc.uid_masked:
            kyc.aadhaar = doc.uid_masked
        kyc.aadhaar_verified = True
        kyc.aadhaar_verified_at = timezone.now()
        kyc.save(update_fields=['aadhaar', 'aadhaar_verified', 'aadhaar_verified_at', 'updated_at'])

        dob = extract_dob_from_raw(doc.raw) or parse_kyc_dob_safe(doc.date_of_birth)
        sync_result = handle_post_kyc_profile_sync(
            user,
            source='aadhaar',
            trigger='onboarding_aadhaar',
            verified_name=doc.name or '',
            verified_dob=dob,
            metadata={
                'provider_code': provider.provider_code,
                'reference_id': str(doc.raw.get('reference_id') or '') if isinstance(doc.raw, dict) else '',
            },
        )
        profile_updated = sync_result.profile_updated
        kyc_details = build_kyc_details(
            pan=kyc.pan or '',
            name=doc.name or '',
            dob=dob,
            aadhaar_masked=doc.uid_masked or kyc.aadhaar or '',
            profile_updated=profile_updated,
        )
        if sync_result.to_api_dict():
            kyc_details['profile_sync'] = sync_result.to_api_dict()
        persist_aadhaar_verified_identity(
            kyc,
            uid_masked=doc.uid_masked or kyc.aadhaar or '',
            name=doc.name or '',
            dob=dob,
            gender=doc.gender or '',
            provider_code=provider.provider_code,
            reference_id=str(doc.raw.get('reference_id') or '') if isinstance(doc.raw, dict) else '',
            verified_at=kyc.aadhaar_verified_at,
            profile_updated=profile_updated,
            raw=doc.raw if isinstance(doc.raw, dict) else None,
        )
        sync_kyc_verification_status(kyc)

    session = KycDigilockerSession.objects.filter(user=user, verification_id=vid, is_deleted=False).first()
    if session and isinstance(doc.raw, dict):
        raw_status = dict(session.raw_status or {})
        raw_status['document'] = doc.raw
        session.raw_status = raw_status
        session.save(update_fields=['raw_status', 'updated_at'])
    return kyc, kyc_details


def self_service_send_aadhaar_otp(user, aadhaar):
    """Deprecated: Aadhaar SMS OTP replaced by DigiLocker."""
    raise ValueError('Aadhaar OTP verification is no longer supported. Use DigiLocker verification.')


def self_service_verify_aadhaar_otp_only(user, otp_code):
    """Deprecated: Aadhaar SMS OTP replaced by DigiLocker."""
    raise ValueError('Aadhaar OTP verification is no longer supported. Use DigiLocker verification.')


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


def get_viewable_user_ids(user) -> set:
    """
    User IDs a non-admin may list/retrieve: all subordinates, direct parents of
    those subordinates (point of contact from profile links), and self.
    """
    subordinates = UserHierarchy.get_subordinates(user)
    subordinate_ids = {u.id for u in subordinates}
    parent_ids = set()
    if subordinate_ids:
        parent_ids = set(
            UserHierarchy.objects.filter(child_user_id__in=subordinate_ids).values_list(
                'parent_user_id', flat=True
            )
        )
    return subordinate_ids | parent_ids | {user.id}


def _user_display_name(u: User) -> str:
    name = (u.get_full_name() or '').strip()
    return name or (u.email or u.phone or str(u.pk))


def _hierarchy_public_ref(u: User) -> str:
    """Non-null string for lineage paths (join-safe). Some legacy rows have empty user_id."""
    uid = getattr(u, 'user_id', None)
    if uid is not None:
        s = str(uid).strip()
        if s:
            return s
    return str(u.pk)


def _direct_parent_contacts(user: User, *, include_pk: bool = False) -> list:
    """Immediate parent hierarchy edges for a user (who they report to)."""
    contacts = []
    for rel in (
        UserHierarchy.objects.filter(child_user=user)
        .select_related('parent_user')
        .order_by('created_at')
    ):
        p = rel.parent_user
        entry = {
            'user_id': p.user_id,
            'role': p.role,
            'name': _user_display_name(p),
            'linked_at': rel.created_at.isoformat() if rel.created_at else None,
        }
        if include_pk:
            entry['id'] = p.pk
        contacts.append(entry)
    return contacts


def build_point_of_contact(user: User) -> dict:
    """
    Non-admin profile view: direct parent(s) of the profile user only.
    """
    return {'contacts': _direct_parent_contacts(user, include_pk=True)}


def build_user_lineage(user: User) -> dict:
    """
    Upline (root → immediate parent), direct parent links (who added / when),
    and a compact map path for admin UI.
    """
    direct_parents = _direct_parent_contacts(user, include_pk=False)

    # Walk upline using first parent edge per level (matches commission upline behaviour)
    upline_steps = []
    upline_path_segments = []
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
        upline_path_segments.append(_hierarchy_public_ref(p))
        current = p

    upline_steps.reverse()
    upline_path_segments.reverse()

    path_ids = list(upline_path_segments)
    path_ids.append(_hierarchy_public_ref(user))
    map_path = ' → '.join(path_ids) if path_ids else _hierarchy_public_ref(user)

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
