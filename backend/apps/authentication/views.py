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
    UserSerializer,
    OnboardingPANSerializer,
    OnboardingAadhaarSerializer,
    OnboardingAadhaarVerifyOTPSerializer,
    SetupMPINSerializer,
)
from apps.authentication.services import create_jwt_tokens, send_otp, verify_otp, reset_password
from apps.users.services import (
    self_service_verify_pan,
    self_service_send_aadhaar_otp,
    self_service_verify_aadhaar_otp_only,
    setup_initial_mpin,
)
from apps.core.exceptions import InvalidCredentials, InvalidMPIN, InvalidOTP


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
        
        return Response({
            'success': True,
            'data': {
                'user': user_data,
                'tokens': tokens
            },
            'message': 'Login successful',
            'errors': []
        }, status=status.HTTP_200_OK)
    
    return Response({
        'success': False,
        'data': None,
        'message': 'Login failed',
        'errors': serializer.errors
    }, status=status.HTTP_400_BAD_REQUEST)


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
        
        # Check if user exists (for password reset)
        if purpose == 'password-reset':
            try:
                User.objects.get(phone=phone)
            except User.DoesNotExist:
                return Response({
                    'success': False,
                    'data': None,
                    'message': 'Phone number not registered',
                    'errors': []
                }, status=status.HTTP_404_NOT_FOUND)
        
        # Send OTP
        send_otp(phone, purpose)
        
        return Response({
            'success': True,
            'data': None,
            'message': f'OTP sent to {phone[:2]}****{phone[6:]}',
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
            reset_password(phone, otp_code, new_password)
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
@authentication_classes([])
@permission_classes([])
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
        refresh = RefreshToken(refresh_token)
        uid = refresh.payload.get('user_id')
        if uid is not None:
            u = User.objects.filter(pk=uid).first()
            if not u or not u.is_active:
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
    user = User.objects.select_related('kyc').get(pk=request.user.pk)
    user_data = UserSerializer(user).data
    return Response({
        'success': True,
        'data': {'user': user_data},
        'message': 'User retrieved successfully',
        'errors': []
    }, status=status.HTTP_200_OK)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def onboarding_kyc_verify_pan_view(request):
    """Step 1: verify PAN only. POST /api/auth/onboarding/kyc/pan/"""
    serializer = OnboardingPANSerializer(data=request.data)
    if not serializer.is_valid():
        return Response({
            'success': False,
            'data': None,
            'message': 'Validation failed',
            'errors': serializer.errors,
        }, status=status.HTTP_400_BAD_REQUEST)
    try:
        self_service_verify_pan(request.user, serializer.validated_data['pan'])
    except ValueError as e:
        return Response({
            'success': False,
            'data': None,
            'message': str(e),
            'errors': [],
        }, status=status.HTTP_400_BAD_REQUEST)
    u = User.objects.select_related('kyc').get(pk=request.user.pk)
    return Response({
        'success': True,
        'data': {'user': UserSerializer(u).data},
        'message': 'PAN verified successfully',
        'errors': [],
    }, status=status.HTTP_200_OK)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def onboarding_kyc_aadhaar_send_otp_view(request):
    """Step 2a: save Aadhaar and send OTP to registered mobile. POST /api/auth/onboarding/kyc/aadhaar/send-otp/"""
    serializer = OnboardingAadhaarSerializer(data=request.data)
    if not serializer.is_valid():
        return Response({
            'success': False,
            'data': None,
            'message': 'Validation failed',
            'errors': serializer.errors,
        }, status=status.HTTP_400_BAD_REQUEST)
    try:
        self_service_send_aadhaar_otp(request.user, serializer.validated_data['aadhaar'])
    except ValueError as e:
        return Response({
            'success': False,
            'data': None,
            'message': str(e),
            'errors': [],
        }, status=status.HTTP_400_BAD_REQUEST)
    u = User.objects.select_related('kyc').get(pk=request.user.pk)
    return Response({
        'success': True,
        'data': {
            'user': UserSerializer(u).data,
            'demo_otp_hint': 'If SMS is not available, use OTP 123456 in demo mode.',
        },
        'message': 'OTP sent to your registered mobile number.',
        'errors': [],
    }, status=status.HTTP_200_OK)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def onboarding_kyc_aadhaar_verify_otp_view(request):
    """Step 2b: verify Aadhaar OTP (SMS code or demo 123456). POST /api/auth/onboarding/kyc/aadhaar/verify-otp/"""
    serializer = OnboardingAadhaarVerifyOTPSerializer(data=request.data)
    if not serializer.is_valid():
        return Response({
            'success': False,
            'data': None,
            'message': 'Validation failed',
            'errors': serializer.errors,
        }, status=status.HTTP_400_BAD_REQUEST)
    try:
        self_service_verify_aadhaar_otp_only(request.user, serializer.validated_data['otp'])
    except ValueError as e:
        return Response({
            'success': False,
            'data': None,
            'message': str(e),
            'errors': [],
        }, status=status.HTTP_400_BAD_REQUEST)
    u = User.objects.select_related('kyc').get(pk=request.user.pk)
    return Response({
        'success': True,
        'data': {'user': UserSerializer(u).data},
        'message': 'Aadhaar verified. KYC is complete.',
        'errors': [],
    }, status=status.HTTP_200_OK)


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
