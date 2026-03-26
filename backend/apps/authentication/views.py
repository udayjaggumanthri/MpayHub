"""
Authentication views for the mPayhub platform.
"""
from django.utils import timezone
from rest_framework import status, generics
from rest_framework.decorators import api_view, permission_classes
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
    UserSerializer
)
from apps.authentication.services import create_jwt_tokens, send_otp, verify_otp, reset_password
from apps.core.exceptions import InvalidMPIN, InvalidOTP


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
        
        # Create JWT tokens
        tokens = create_jwt_tokens(user)
        
        # Update last login
        user.last_login = timezone.now()
        user.save(update_fields=['last_login'])
        
        # Serialize user data
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
@permission_classes([IsAuthenticated])
def refresh_token_view(request):
    """
    Refresh JWT token endpoint.
    POST /api/auth/refresh-token/
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
    user_data = UserSerializer(request.user).data
    return Response({
        'success': True,
        'data': {'user': user_data},
        'message': 'User retrieved successfully',
        'errors': []
    }, status=status.HTTP_200_OK)
