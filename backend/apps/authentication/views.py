"""
Authentication views for the mPayhub platform.
"""
from django.utils import timezone
from rest_framework import status, generics
from rest_framework.decorators import api_view, permission_classes, authentication_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from django_ratelimit.decorators import ratelimit
from apps.authentication.models import User
from apps.authentication.serializers import (
    LoginSerializer,
    MPINVerificationSerializer,
    SendOTPSerializer,
    VerifyOTPSerializer,
    ResetPasswordSerializer,
    ResetMPINSerializer,
    ForcedPasswordResetSendOTPSerializer,
    ForcedPasswordResetCompleteSerializer,
    UserSerializer,
    OnboardingPANSerializer,
    OnboardingDigilockerInitSerializer,
    OnboardingDigilockerStatusSerializer,
    OnboardingDigilockerCompleteSerializer,
    OnboardingAadhaarSerializer,
    OnboardingAadhaarVerifyOTPSerializer,
    SetupMPINSerializer,
)
from apps.authentication.password_onboarding import clear_must_change_password
from apps.authentication.services import (
    create_jwt_tokens,
    send_otp,
    verify_otp,
    reset_password,
    reset_mpin,
    get_valid_otp,
    SmtpNotConfiguredError,
)
from apps.core.utils import mask_email, mask_phone
from apps.users.services import (
    self_service_verify_pan,
    init_digilocker_aadhaar,
    poll_digilocker_status,
    complete_digilocker_aadhaar,
    setup_initial_mpin,
)
from apps.core.exceptions import InvalidCredentials, InvalidMPIN, InvalidOTP

# SECURITY — unauthenticated / AllowAny JSON endpoints (mitigations):
# - login_view, send_otp_view, verify_otp_view, reset_password_view: AllowAny + django-ratelimit on POST
# - refresh_token_view: empty auth classes (refresh body only); IP rate limit on POST


@api_view(['POST'])
@permission_classes([AllowAny])
@ratelimit(key='ip', rate='5/m', method='POST')
def login_view(request):
    """
    User login endpoint.
    POST /api/auth/login/
    """
    serializer = LoginSerializer(data=request.data)
    if serializer.is_valid():
        user = serializer.validated_data['user']

        # Update last login
        user.last_login = timezone.now()
        user.save(update_fields=['last_login'])

        user = User.objects.select_related('kyc').get(pk=user.pk)

        # Create JWT tokens
        tokens = create_jwt_tokens(user)

        # Serialize user data (includes onboarding for post-login routing)
        user_data = UserSerializer(user).data
        from apps.core.maintenance_mode import get_status

        return Response({
            'success': True,
            'data': {
                'user': user_data,
                'tokens': tokens,
                'maintenance': get_status(include_internal=False),
            },
            'message': 'Login successful',
            'errors': []
        }, status=status.HTTP_200_OK)
    
    errors = serializer.errors
    message = 'Invalid phone number or password.'
    error_meta = None
    non_field = errors.get('non_field_errors') if isinstance(errors, dict) else None
    if non_field:
        first = non_field[0] if isinstance(non_field, list) else str(non_field)
        text = str(first)
        if getattr(first, 'code', None) == 'USER_DISABLED' or 'disabled' in text.lower():
            message = text
            error_meta = {'code': 'USER_DISABLED'}
        elif text and 'invalid' not in text.lower():
            message = text
    return Response(
        {
            'success': False,
            'data': None,
            'message': message,
            'errors': errors,
            'error': error_meta,
        },
        status=status.HTTP_400_BAD_REQUEST,
    )


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def verify_mpin_view(request):
    """
    MPIN verification endpoint.
    POST /api/auth/verify-mpin/
    """
    serializer = MPINVerificationSerializer(data=request.data, context={'request': request})
    if serializer.is_valid():
        return Response({
            'success': True,
            'data': None,
            'message': 'MPIN verified successfully',
            'errors': []
        }, status=status.HTTP_200_OK)
    
    return Response({
        'success': False,
        'data': None,
        'message': 'MPIN verification failed',
        'errors': serializer.errors
    }, status=status.HTTP_400_BAD_REQUEST)


@api_view(['POST'])
@permission_classes([AllowAny])
@ratelimit(key='ip', rate='3/m', method='POST')
def send_otp_view(request):
    """
    Send OTP endpoint.
    POST /api/auth/send-otp/
    """
    serializer = SendOTPSerializer(data=request.data)
    if serializer.is_valid():
        phone = serializer.validated_data['phone']
        purpose = serializer.validated_data.get('purpose', 'password-reset')
        
        if purpose in ('password-reset', 'mpin-reset'):
            try:
                target = User.objects.get(phone=phone)
            except User.DoesNotExist:
                return Response({
                    'success': False,
                    'data': None,
                    'message': 'Phone number not registered',
                    'errors': []
                }, status=status.HTTP_404_NOT_FOUND)
            if purpose == 'mpin-reset' and not target.mpin_hash:
                return Response({
                    'success': False,
                    'data': None,
                    'message': (
                        'MPIN is not set on this account. Complete onboarding first or contact support.'
                    ),
                    'errors': [],
                }, status=status.HTTP_400_BAD_REQUEST)
        
        channel = serializer.validated_data.get('channel', 'sms')
        try:
            send_otp(phone, purpose, channel=channel)
        except SmtpNotConfiguredError as exc:
            return Response({
                'success': False,
                'data': None,
                'message': str(exc),
                'errors': [],
            }, status=status.HTTP_400_BAD_REQUEST)

        if channel == 'email':
            user = User.objects.get(phone=phone)
            msg = f'OTP sent to your registered email ({mask_email(user.email)})'
        else:
            msg = f'OTP sent to {mask_phone(phone)}'

        return Response({
            'success': True,
            'data': None,
            'message': msg,
            'errors': []
        }, status=status.HTTP_200_OK)
    
    return Response({
        'success': False,
        'data': None,
        'message': 'Failed to send OTP',
        'errors': serializer.errors
    }, status=status.HTTP_400_BAD_REQUEST)


@api_view(['POST'])
@permission_classes([AllowAny])
@ratelimit(key='ip', rate='10/m', method='POST')
def verify_otp_view(request):
    """
    Verify OTP endpoint.
    POST /api/auth/verify-otp/
    """
    serializer = VerifyOTPSerializer(data=request.data)
    if serializer.is_valid():
        return Response({
            'success': True,
            'data': None,
            'message': 'OTP verified successfully',
            'errors': []
        }, status=status.HTTP_200_OK)
    
    return Response({
        'success': False,
        'data': None,
        'message': 'OTP verification failed',
        'errors': serializer.errors
    }, status=status.HTTP_400_BAD_REQUEST)


@api_view(['POST'])
@permission_classes([AllowAny])
@ratelimit(key='ip', rate='5/m', method='POST')
def reset_password_view(request):
    """
    Reset password endpoint.
    POST /api/auth/reset-password/
    """
    serializer = ResetPasswordSerializer(data=request.data)
    if serializer.is_valid():
        phone = serializer.validated_data['phone']
        otp_code = serializer.validated_data['otp']
        new_password = serializer.validated_data['new_password']
        
        try:
            reset_password(
                phone,
                otp_code,
                new_password,
                otp_record=serializer.validated_data['otp_record'],
            )
            return Response({
                'success': True,
                'data': None,
                'message': 'Password reset successfully',
                'errors': []
            }, status=status.HTTP_200_OK)
        except (InvalidOTP, InvalidCredentials) as e:
            return Response({
                'success': False,
                'data': None,
                'message': str(e),
                'errors': []
            }, status=status.HTTP_400_BAD_REQUEST)
    
    return Response({
        'success': False,
        'data': None,
        'message': 'Password reset failed',
        'errors': serializer.errors
    }, status=status.HTTP_400_BAD_REQUEST)


@api_view(['POST'])
@permission_classes([AllowAny])
@ratelimit(key='ip', rate='5/m', method='POST')
def reset_mpin_view(request):
    """
    Reset MPIN endpoint (forgot MPIN).
    POST /api/auth/reset-mpin/
    """
    serializer = ResetMPINSerializer(data=request.data)
    if serializer.is_valid():
        phone = serializer.validated_data['phone']
        otp_code = serializer.validated_data['otp']
        new_mpin = serializer.validated_data['new_mpin']

        try:
            reset_mpin(
                phone,
                otp_code,
                new_mpin,
                otp_record=serializer.validated_data['otp_record'],
            )
            return Response({
                'success': True,
                'data': None,
                'message': 'MPIN reset successfully',
                'errors': [],
            }, status=status.HTTP_200_OK)
        except (InvalidOTP, InvalidCredentials) as e:
            return Response({
                'success': False,
                'data': None,
                'message': str(e),
                'errors': [],
            }, status=status.HTTP_400_BAD_REQUEST)

    return Response({
        'success': False,
        'data': None,
        'message': 'MPIN reset failed',
        'errors': serializer.errors,
    }, status=status.HTTP_400_BAD_REQUEST)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
@ratelimit(key='user', rate='3/m', method='POST')
def send_forced_password_reset_otp_view(request):
    """
    Send OTP for mandatory first-login password reset.
    POST /api/auth/me/send-password-reset-otp/
    """
    user = request.user
    if not getattr(user, 'must_change_password', False):
        return Response(
            {
                'success': False,
                'data': None,
                'message': 'Password reset is not required for this account.',
                'errors': [],
            },
            status=status.HTTP_403_FORBIDDEN,
        )

    serializer = ForcedPasswordResetSendOTPSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(
            {
                'success': False,
                'data': None,
                'message': 'Failed to send OTP',
                'errors': serializer.errors,
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    channel = serializer.validated_data.get('channel', 'sms')
    try:
        send_otp(user.phone, 'password-reset', channel=channel)
    except SmtpNotConfiguredError as exc:
        return Response(
            {
                'success': False,
                'data': None,
                'message': str(exc),
                'errors': [],
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    if channel == 'email':
        msg = f'OTP sent to your registered email ({mask_email(user.email)})'
    else:
        msg = f'OTP sent to {mask_phone(user.phone)}'

    return Response(
        {
            'success': True,
            'data': None,
            'message': msg,
            'errors': [],
        },
        status=status.HTTP_200_OK,
    )


@api_view(['POST'])
@permission_classes([IsAuthenticated])
@ratelimit(key='user', rate='5/m', method='POST')
def complete_forced_password_reset_view(request):
    """
    Complete mandatory first-login password reset with OTP.
    POST /api/auth/me/complete-password-reset/
    """
    user = request.user
    if not getattr(user, 'must_change_password', False):
        return Response(
            {
                'success': False,
                'data': None,
                'message': 'Password reset is not required for this account.',
                'errors': [],
            },
            status=status.HTTP_403_FORBIDDEN,
        )

    serializer = ForcedPasswordResetCompleteSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(
            {
                'success': False,
                'data': None,
                'message': 'Password reset failed',
                'errors': serializer.errors,
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    otp_code = serializer.validated_data['otp']
    new_password = serializer.validated_data['new_password']

    try:
        otp_record = get_valid_otp(user.phone, otp_code, 'password-reset')
        reset_password(
            user.phone,
            otp_code,
            new_password,
            otp_record=otp_record,
        )
        clear_must_change_password(user)
        user = User.objects.select_related('kyc').get(pk=user.pk)
        user_data = UserSerializer(user).data
        return Response(
            {
                'success': True,
                'data': {'user': user_data},
                'message': 'Password updated successfully',
                'errors': [],
            },
            status=status.HTTP_200_OK,
        )
    except (InvalidOTP, InvalidCredentials) as exc:
        return Response(
            {
                'success': False,
                'data': None,
                'message': str(exc),
                'errors': [],
            },
            status=status.HTTP_400_BAD_REQUEST,
        )


@api_view(['POST'])
@authentication_classes([])
@permission_classes([])
@ratelimit(key='ip', rate='30/m', method='POST')
def refresh_token_view(request):
    """
    Refresh JWT token endpoint.
    POST /api/auth/refresh-token/
    No auth header required (used when access token is expired).
    """
    from rest_framework_simplejwt.tokens import RefreshToken

    refresh_token = request.data.get('refresh')
    if not refresh_token:
        return Response({
            'success': False,
            'data': None,
            'message': 'Refresh token is required',
            'errors': []
        }, status=status.HTTP_400_BAD_REQUEST)

    try:
        from apps.core.financial_access import user_may_login

        refresh = RefreshToken(refresh_token)
        uid = refresh.payload.get('user_id')
        if uid is not None:
            u = User.objects.filter(pk=uid).first()
            if not u or not user_may_login(u):
                return Response({
                    'success': False,
                    'data': None,
                    'message': 'User account is disabled.',
                    'errors': ['user_inactive'],
                }, status=status.HTTP_401_UNAUTHORIZED)
        tokens = {
            'access': str(refresh.access_token),
            'refresh': str(refresh),
        }
        return Response({
            'success': True,
            'data': {'tokens': tokens},
            'message': 'Token refreshed successfully',
            'errors': []
        }, status=status.HTTP_200_OK)
    except Exception as e:
        return Response({
            'success': False,
            'data': None,
            'message': 'Invalid refresh token',
            'errors': [str(e)]
        }, status=status.HTTP_400_BAD_REQUEST)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def logout_view(request):
    """
    Logout endpoint.
    POST /api/auth/logout/
    """
    # Invalidate refresh token (if using token blacklist)
    # For now, just return success
    return Response({
        'success': True,
        'data': None,
        'message': 'Logged out successfully',
        'errors': []
    }, status=status.HTTP_200_OK)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def current_user_view(request):
    """
    Get current authenticated user.
    GET /api/auth/me/
    """
    user = User.objects.select_related('kyc', 'profile').get(pk=request.user.pk)
    user_data = UserSerializer(user).data
    from apps.core.maintenance_mode import get_status

    return Response({
        'success': True,
        'data': {
            'user': user_data,
            'maintenance': get_status(include_internal=False),
        },
        'message': 'User retrieved successfully',
        'errors': []
    }, status=status.HTTP_200_OK)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
@ratelimit(key='user', rate='5/m', method='POST')
@ratelimit(key='ip', rate='15/m', method='POST')
def onboarding_kyc_verify_pan_view(request):
    """Step 1: verify PAN only. POST /api/auth/onboarding/kyc/pan/"""
    serializer = OnboardingPANSerializer(data=request.data)
    if not serializer.is_valid():
        first_err = ''
        for field_errors in serializer.errors.values():
            if isinstance(field_errors, list) and field_errors:
                first_err = str(field_errors[0])
                break
            if isinstance(field_errors, str):
                first_err = field_errors
                break
        return Response({
            'success': False,
            'data': None,
            'message': first_err or 'Validation failed',
            'errors': serializer.errors,
        }, status=status.HTTP_400_BAD_REQUEST)
    try:
        _kyc, kyc_details = self_service_verify_pan(
            request.user,
            serializer.validated_data['pan'],
            name=serializer.validated_data['name'],
        )
    except ValueError as e:
        return Response({
            'success': False,
            'data': None,
            'message': str(e),
            'errors': [],
        }, status=status.HTTP_400_BAD_REQUEST)
    u = User.objects.select_related('kyc').get(pk=request.user.pk)
    response_data = {
        'user': UserSerializer(u).data,
        'kyc_details': kyc_details,
    }
    if isinstance(kyc_details, dict) and kyc_details.get('profile_sync'):
        response_data['profile_sync'] = kyc_details['profile_sync']
    return Response({
        'success': True,
        'data': response_data,
        'message': 'PAN verified successfully',
        'errors': [],
    }, status=status.HTTP_200_OK)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
@ratelimit(key='user', rate='5/m', method='POST')
@ratelimit(key='ip', rate='15/m', method='POST')
def onboarding_kyc_digilocker_init_view(request):
    """Start Cashfree DigiLocker consent. POST /api/auth/onboarding/kyc/digilocker/init/"""
    serializer = OnboardingDigilockerInitSerializer(data=request.data)
    if not serializer.is_valid():
        return Response({
            'success': False,
            'data': None,
            'message': 'Validation failed',
            'errors': serializer.errors,
        }, status=status.HTTP_400_BAD_REQUEST)
    try:
        aadhaar = (serializer.validated_data.get('aadhaar') or '').strip() or None
        result = init_digilocker_aadhaar(request.user, aadhaar_number=aadhaar)
    except ValueError as e:
        return Response({
            'success': False,
            'data': None,
            'message': str(e),
            'errors': [],
        }, status=status.HTTP_400_BAD_REQUEST)
    return Response({
        'success': True,
        'data': {
            'url': result.url,
            'verification_id': result.verification_id,
            'status': result.status,
        },
        'message': 'Redirect to DigiLocker to complete Aadhaar verification.',
        'errors': [],
    }, status=status.HTTP_200_OK)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
@ratelimit(key='user', rate='30/m', method='GET')
@ratelimit(key='ip', rate='60/m', method='GET')
def onboarding_kyc_digilocker_status_view(request):
    """Poll DigiLocker status. GET /api/auth/onboarding/kyc/digilocker/status/?verification_id="""
    serializer = OnboardingDigilockerStatusSerializer(data=request.query_params)
    if not serializer.is_valid():
        return Response({
            'success': False,
            'data': None,
            'message': 'Validation failed',
            'errors': serializer.errors,
        }, status=status.HTTP_400_BAD_REQUEST)
    try:
        result = poll_digilocker_status(
            request.user,
            serializer.validated_data['verification_id'],
        )
    except ValueError as e:
        return Response({
            'success': False,
            'data': None,
            'message': str(e),
            'errors': [],
        }, status=status.HTTP_400_BAD_REQUEST)
    return Response({
        'success': True,
        'data': {
            'verification_id': result.verification_id,
            'status': result.status,
            'document_consent': result.document_consent,
        },
        'message': 'DigiLocker status retrieved.',
        'errors': [],
    }, status=status.HTTP_200_OK)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
@ratelimit(key='user', rate='10/m', method='POST')
@ratelimit(key='ip', rate='20/m', method='POST')
def onboarding_kyc_digilocker_complete_view(request):
    """Finalize DigiLocker after consent. POST /api/auth/onboarding/kyc/digilocker/complete/"""
    serializer = OnboardingDigilockerCompleteSerializer(data=request.data)
    if not serializer.is_valid():
        return Response({
            'success': False,
            'data': None,
            'message': 'Validation failed',
            'errors': serializer.errors,
        }, status=status.HTTP_400_BAD_REQUEST)
    try:
        _kyc, kyc_details = complete_digilocker_aadhaar(
            request.user,
            serializer.validated_data['verification_id'],
        )
    except ValueError as e:
        return Response({
            'success': False,
            'data': None,
            'message': str(e),
            'errors': [],
        }, status=status.HTTP_400_BAD_REQUEST)
    u = User.objects.select_related('kyc').get(pk=request.user.pk)
    response_data = {
        'user': UserSerializer(u).data,
        'kyc_details': kyc_details,
    }
    if isinstance(kyc_details, dict) and kyc_details.get('profile_sync'):
        response_data['profile_sync'] = kyc_details['profile_sync']
    return Response({
        'success': True,
        'data': response_data,
        'message': 'Aadhaar verified. KYC is complete.',
        'errors': [],
    }, status=status.HTTP_200_OK)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def profile_sync_pending_view(request):
    """List pending KYC → profile sync offers for the current user."""
    from apps.users.kyc_profile_sync_audit import get_pending_audits_for_user, serialize_pending_audit

    pending = [serialize_pending_audit(row) for row in get_pending_audits_for_user(request.user)]
    return Response({
        'success': True,
        'data': {'pending': pending},
        'message': 'Pending profile sync offers retrieved.',
        'errors': [],
    }, status=status.HTTP_200_OK)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
@ratelimit(key='user', rate='5/m', method='POST')
def profile_sync_confirm_view(request):
    """Apply verified KYC name/DOB to profile after user confirmation."""
    from apps.authentication.serializers import ProfileSyncTokenSerializer
    from apps.integrations.kyc.profile_sync_orchestrator import confirm_profile_sync

    serializer = ProfileSyncTokenSerializer(data=request.data)
    if not serializer.is_valid():
        return Response({
            'success': False,
            'data': None,
            'message': 'Validation failed',
            'errors': serializer.errors,
        }, status=status.HTTP_400_BAD_REQUEST)
    try:
        result = confirm_profile_sync(
            request.user,
            sync_token=serializer.validated_data['sync_token'],
        )
    except ValueError as e:
        return Response({
            'success': False,
            'data': None,
            'message': str(e),
            'errors': [],
        }, status=status.HTTP_400_BAD_REQUEST)
    u = User.objects.select_related('kyc', 'profile').get(pk=request.user.pk)
    return Response({
        'success': True,
        'data': {
            'user': UserSerializer(u).data,
            'profile_sync': result.to_api_dict() or {'status': 'applied', 'profile_updated': result.profile_updated},
        },
        'message': result.message,
        'errors': [],
    }, status=status.HTTP_200_OK)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
@ratelimit(key='user', rate='5/m', method='POST')
def profile_sync_decline_view(request):
    """Decline syncing verified KYC fields into profile."""
    from apps.authentication.serializers import ProfileSyncTokenSerializer
    from apps.integrations.kyc.profile_sync_orchestrator import decline_profile_sync

    serializer = ProfileSyncTokenSerializer(data=request.data)
    if not serializer.is_valid():
        return Response({
            'success': False,
            'data': None,
            'message': 'Validation failed',
            'errors': serializer.errors,
        }, status=status.HTTP_400_BAD_REQUEST)
    try:
        result = decline_profile_sync(
            request.user,
            sync_token=serializer.validated_data['sync_token'],
        )
    except ValueError as e:
        return Response({
            'success': False,
            'data': None,
            'message': str(e),
            'errors': [],
            'warning_code': 'PROFILE_SYNC_DECLINED',
        }, status=status.HTTP_400_BAD_REQUEST)
    return Response({
        'success': True,
        'data': {
            'profile_sync': {'status': 'declined', 'profile_updated': False},
        },
        'message': result.message,
        'errors': [],
        'warning_code': 'PROFILE_SYNC_DECLINED',
    }, status=status.HTTP_200_OK)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def onboarding_kyc_aadhaar_send_otp_view(request):
    """Deprecated — use DigiLocker init."""
    return Response({
        'success': False,
        'data': None,
        'message': 'Aadhaar OTP is no longer supported. Use DigiLocker verification.',
        'errors': [],
    }, status=status.HTTP_410_GONE)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def onboarding_kyc_aadhaar_verify_otp_view(request):
    """Deprecated — use DigiLocker complete."""
    return Response({
        'success': False,
        'data': None,
        'message': 'Aadhaar OTP is no longer supported. Use DigiLocker verification.',
        'errors': [],
    }, status=status.HTTP_410_GONE)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def setup_mpin_view(request):
    """
    First-time MPIN after KYC (hierarchy-onboarded users).
    POST /api/auth/onboarding/setup-mpin/
    """
    serializer = SetupMPINSerializer(data=request.data)
    if not serializer.is_valid():
        return Response({
            'success': False,
            'data': None,
            'message': 'Validation failed',
            'errors': serializer.errors,
        }, status=status.HTTP_400_BAD_REQUEST)
    try:
        setup_initial_mpin(
            request.user,
            serializer.validated_data['mpin'],
            serializer.validated_data['confirm_mpin'],
        )
    except ValueError as e:
        return Response({
            'success': False,
            'data': None,
            'message': str(e),
            'errors': [],
        }, status=status.HTTP_400_BAD_REQUEST)

    user = User.objects.select_related('kyc').get(pk=request.user.pk)
    return Response({
        'success': True,
        'data': {'user': UserSerializer(user).data},
        'message': 'MPIN set successfully',
        'errors': [],
    }, status=status.HTTP_200_OK)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def change_password_view(request):
    """
    Change password for authenticated user.
    POST /api/auth/change-password/
    Body: { "current_password": "...", "new_password": "..." }
    """
    current_password = request.data.get('current_password', '')
    new_password = request.data.get('new_password', '')

    if not current_password or not new_password:
        return Response({
            'success': False,
            'data': None,
            'message': 'Both current_password and new_password are required',
            'errors': [],
        }, status=status.HTTP_400_BAD_REQUEST)

    if len(new_password) < 6:
        return Response({
            'success': False,
            'data': None,
            'message': 'New password must be at least 6 characters',
            'errors': [],
        }, status=status.HTTP_400_BAD_REQUEST)

    user = request.user
    if not user.check_password(current_password):
        return Response({
            'success': False,
            'data': None,
            'message': 'Current password is incorrect',
            'errors': [],
        }, status=status.HTTP_400_BAD_REQUEST)

    user.set_password(new_password)
    user.save(update_fields=['password'])

    return Response({
        'success': True,
        'data': None,
        'message': 'Password changed successfully',
        'errors': [],
    }, status=status.HTTP_200_OK)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def change_mpin_view(request):
    """
    Change MPIN for authenticated user.
    POST /api/auth/change-mpin/
    Body: { "current_mpin": "123456", "new_mpin": "654321" }
    """
    current_mpin = str(request.data.get('current_mpin', '')).strip()
    new_mpin = str(request.data.get('new_mpin', '')).strip()

    if not current_mpin or not new_mpin:
        return Response({
            'success': False,
            'data': None,
            'message': 'Both current_mpin and new_mpin are required',
            'errors': [],
        }, status=status.HTTP_400_BAD_REQUEST)

    if len(new_mpin) != 6 or not new_mpin.isdigit():
        return Response({
            'success': False,
            'data': None,
            'message': 'New MPIN must be exactly 6 digits',
            'errors': [],
        }, status=status.HTTP_400_BAD_REQUEST)

    user = request.user
    if not user.check_mpin(current_mpin):
        return Response({
            'success': False,
            'data': None,
            'message': 'Current MPIN is incorrect',
            'errors': [],
        }, status=status.HTTP_400_BAD_REQUEST)

    user.set_mpin(new_mpin)

    return Response({
        'success': True,
        'data': None,
        'message': 'MPIN changed successfully',
        'errors': [],
    }, status=status.HTTP_200_OK)
