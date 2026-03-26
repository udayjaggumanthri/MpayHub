"""
User management views for the mPayhub platform.
"""
from rest_framework import status, viewsets
from rest_framework.decorators import api_view, permission_classes, action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django_ratelimit.decorators import ratelimit
from django.db import models
from apps.authentication.models import User
from apps.users.models import UserProfile, KYC
from apps.users.serializers import (
    UserCreateSerializer,
    UserUpdateSerializer,
    UserListSerializer,
    UserDetailSerializer,
    PANVerificationSerializer,
    AadhaarOTPSerializer,
    AadhaarOTPVerificationSerializer
)
from apps.users.services import (
    create_user,
    verify_pan,
    send_aadhaar_otp,
    verify_aadhaar_otp,
    get_subordinates
)
from apps.core.permissions import IsAdmin, IsMasterDistributorOrAbove, IsDistributorOrAbove, IsHierarchy
from apps.core.exceptions import InvalidUserRole


class UserViewSet(viewsets.ModelViewSet):
    """
    ViewSet for user management.
    """
    queryset = User.objects.all()
    permission_classes = [IsAuthenticated]
    
    def get_serializer_class(self):
        if self.action == 'list':
            return UserListSerializer
        elif self.action == 'retrieve':
            return UserDetailSerializer
        elif self.action == 'create':
            return UserCreateSerializer
        elif self.action in ['update', 'partial_update']:
            return UserUpdateSerializer
        return UserListSerializer
    
    def get_queryset(self):
        """Filter users based on hierarchy."""
        user = self.request.user
        
        # Admin can see all users
        if user.role == 'Admin':
            queryset = User.objects.all()
        else:
            # Get subordinates
            subordinates = get_subordinates(user)
            queryset = User.objects.filter(id__in=[u.id for u in subordinates])
        
        # Filter by role if provided
        role = self.request.query_params.get('role')
        if role:
            queryset = queryset.filter(role=role)
        
        return queryset.select_related('profile', 'kyc')
    
    def list(self, request, *args, **kwargs):
        """List users with custom response format."""
        queryset = self.filter_queryset(self.get_queryset())
        
        # Handle search parameter if provided
        search = request.query_params.get('search', '').strip()
        if search:
            queryset = queryset.filter(
                models.Q(first_name__icontains=search) |
                models.Q(last_name__icontains=search) |
                models.Q(user_id__icontains=search) |
                models.Q(phone__icontains=search) |
                models.Q(email__icontains=search) |
                models.Q(profile__business_name__icontains=search)
            )
        
        # Get paginated results
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            # Return custom format matching frontend expectations
            return Response({
                'success': True,
                'data': {'users': serializer.data},
                'message': 'Users retrieved successfully',
                'errors': []
            })
        
        # If no pagination, return all results
        serializer = self.get_serializer(queryset, many=True)
        return Response({
            'success': True,
            'data': {'users': serializer.data},
            'message': 'Users retrieved successfully',
            'errors': []
        })
    
    def create(self, request, *args, **kwargs):
        """Create a new user."""
        serializer = UserCreateSerializer(data=request.data, context={'request': request})
        if serializer.is_valid():
            try:
                user = create_user(serializer.validated_data, request.user)
                user_data = UserDetailSerializer(user).data
                return Response({
                    'success': True,
                    'data': {'user': user_data},
                    'message': 'User created successfully',
                    'errors': []
                }, status=status.HTTP_201_CREATED)
            except InvalidUserRole as e:
                return Response({
                    'success': False,
                    'data': None,
                    'message': str(e),
                    'errors': []
                }, status=status.HTTP_403_FORBIDDEN)
        
        return Response({
            'success': False,
            'data': None,
            'message': 'User creation failed',
            'errors': serializer.errors
        }, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=True, methods=['post'])
    def verify_pan(self, request, pk=None):
        """Verify PAN for a user."""
        user = self.get_object()
        serializer = PANVerificationSerializer(data=request.data)
        
        if serializer.is_valid():
            pan = serializer.validated_data['pan']
            if verify_pan(user, pan):
                return Response({
                    'success': True,
                    'data': None,
                    'message': 'PAN verified successfully',
                    'errors': []
                }, status=status.HTTP_200_OK)
            else:
                return Response({
                    'success': False,
                    'data': None,
                    'message': 'PAN verification failed',
                    'errors': []
                }, status=status.HTTP_400_BAD_REQUEST)
        
        return Response({
            'success': False,
            'data': None,
            'message': 'PAN verification failed',
            'errors': serializer.errors
        }, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=True, methods=['post'])
    def send_aadhaar_otp(self, request, pk=None):
        """Send Aadhaar OTP for verification."""
        user = self.get_object()
        serializer = AadhaarOTPSerializer(data=request.data)
        
        if serializer.is_valid():
            try:
                aadhaar = serializer.validated_data['aadhaar']
                send_aadhaar_otp(user, aadhaar)
                return Response({
                    'success': True,
                    'data': None,
                    'message': 'Aadhaar OTP sent successfully',
                    'errors': []
                }, status=status.HTTP_200_OK)
            except ValueError as e:
                return Response({
                    'success': False,
                    'data': None,
                    'message': str(e),
                    'errors': []
                }, status=status.HTTP_400_BAD_REQUEST)
        
        return Response({
            'success': False,
            'data': None,
            'message': 'Failed to send Aadhaar OTP',
            'errors': serializer.errors
        }, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=True, methods=['post'])
    def verify_aadhaar_otp(self, request, pk=None):
        """Verify Aadhaar OTP."""
        user = self.get_object()
        serializer = AadhaarOTPVerificationSerializer(data=request.data)
        
        if serializer.is_valid():
            otp_code = serializer.validated_data['otp']
            if verify_aadhaar_otp(user, otp_code):
                return Response({
                    'success': True,
                    'data': None,
                    'message': 'Aadhaar verified successfully',
                    'errors': []
                }, status=status.HTTP_200_OK)
            else:
                return Response({
                    'success': False,
                    'data': None,
                    'message': 'Aadhaar OTP verification failed',
                    'errors': []
                }, status=status.HTTP_400_BAD_REQUEST)
        
        return Response({
            'success': False,
            'data': None,
            'message': 'Aadhaar OTP verification failed',
            'errors': serializer.errors
        }, status=status.HTTP_400_BAD_REQUEST)
    
    def update(self, request, *args, **kwargs):
        """Update a user."""
        partial = kwargs.pop('partial', False)
        instance = self.get_object()
        
        # Check permissions - only Admin or hierarchy parent can update
        if request.user.role != 'Admin':
            # Check if user is in hierarchy
            from apps.users.models import UserHierarchy
            if not UserHierarchy.objects.filter(parent_user=request.user, child_user=instance).exists():
                return Response({
                    'success': False,
                    'data': None,
                    'message': 'You do not have permission to update this user',
                    'errors': []
                }, status=status.HTTP_403_FORBIDDEN)
        
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        if serializer.is_valid():
            user = serializer.save()
            user_data = UserDetailSerializer(user).data
            return Response({
                'success': True,
                'data': {'user': user_data},
                'message': 'User updated successfully',
                'errors': []
            }, status=status.HTTP_200_OK)
        
        return Response({
            'success': False,
            'data': None,
            'message': 'User update failed',
            'errors': serializer.errors
        }, status=status.HTTP_400_BAD_REQUEST)
    
    def destroy(self, request, *args, **kwargs):
        """Delete a user."""
        instance = self.get_object()
        
        # Check permissions - only Admin can delete
        if request.user.role != 'Admin':
            return Response({
                'success': False,
                'data': None,
                'message': 'Only Admin can delete users',
                'errors': []
            }, status=status.HTTP_403_FORBIDDEN)
        
        # Prevent deleting yourself
        if instance.id == request.user.id:
            return Response({
                'success': False,
                'data': None,
                'message': 'You cannot delete your own account',
                'errors': []
            }, status=status.HTTP_400_BAD_REQUEST)
        
        user_id = instance.user_id
        instance.delete()
        
        return Response({
            'success': True,
            'data': {'user_id': user_id},
            'message': 'User deleted successfully',
            'errors': []
        }, status=status.HTTP_200_OK)
    
    @action(detail=False, methods=['get'])
    def subordinates(self, request):
        """Get all subordinate users."""
        subordinates = get_subordinates(request.user)
        serializer = UserListSerializer(subordinates, many=True)
        return Response({
            'success': True,
            'data': {'users': serializer.data},
            'message': 'Subordinates retrieved successfully',
            'errors': []
        }, status=status.HTTP_200_OK)
