"""
User management views for the mPayhub platform.
"""
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.db import models
from apps.authentication.models import User
from apps.users.serializers import (
    UserCreateSerializer,
    UserUpdateSerializer,
    UserListSerializer,
    UserDetailSerializer,
    UserRoleChangeSerializer,
    UserActiveStatusSerializer,
    UserAccessControlsSerializer,
    AdminUserContactSerializer,
    PANVerificationSerializer,
    AadhaarOTPSerializer,
    AadhaarOTPVerificationSerializer,
)
from apps.users.services import (
    admin_change_user_role,
    apply_user_access_controls,
    create_user,
    verify_pan,
    send_aadhaar_otp,
    verify_aadhaar_otp,
    get_subordinates,
    get_viewable_user_ids,
)
from apps.core.exceptions import InvalidUserRole
from apps.wallets.views import build_wallet_summary


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
            queryset = User.objects.filter(id__in=get_viewable_user_ids(user))
        
        # Filter by role if provided
        role = self.request.query_params.get('role')
        if role and role.lower() != 'all':
            queryset = queryset.filter(role=role)

        # Admin: filter by account status (active / disabled)
        if getattr(user, 'role', None) == 'Admin':
            acct = (self.request.query_params.get('account_status') or '').strip().lower()
            if acct == 'active':
                queryset = queryset.filter(is_active=True)
            elif acct in ('inactive', 'disabled'):
                queryset = queryset.filter(is_active=False)
            elif acct == 'restricted':
                queryset = queryset.filter(is_restricted=True)
            elif acct == 'payments_locked':
                queryset = queryset.filter(payments_locked=True)

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
                user, temporary_password = create_user(serializer.validated_data, request.user)
                try:
                    from apps.notifications.email_helpers import login_url_default, user_display_name
                    from apps.notifications.services.email_dispatch import EmailNotificationService

                    to_email = (user.email or '').strip()
                    if to_email:
                        EmailNotificationService.dispatch(
                            'onboarding.user_created',
                            to_email,
                            {
                                'name': user_display_name(user),
                                'user_id': user.user_id or '',
                                'phone': user.phone or '',
                                'email': to_email,
                                'temporary_password': temporary_password or '',
                                'role': user.role or '',
                                'login_url': login_url_default(),
                            },
                            user_id=user.pk,
                            idempotency_key=f'onboarding:{user.pk}',
                        )
                except Exception:
                    pass
                user_data = UserDetailSerializer(user, context=self.get_serializer_context()).data
                data = {'user': user_data}
                if temporary_password:
                    data['temporary_password'] = temporary_password
                msg = 'User created successfully. The user must complete KYC and MPIN after first login.'
                if temporary_password:
                    msg = (
                        'User created successfully. A unique temporary password was generated '
                        '(emailed when configured). The user must reset their password via OTP on '
                        'first login, then complete KYC and MPIN.'
                    )
                return Response({
                    'success': True,
                    'data': data,
                    'message': msg,
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
            aadhaar = serializer.validated_data['aadhaar']
            if verify_aadhaar_otp(user, otp_code, aadhaar=aadhaar):
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
        
        # Check permissions - Admin, or any user in the requester's subtree (direct/indirect)
        if request.user.role != 'Admin':
            subordinate_ids = {u.id for u in get_subordinates(request.user)}
            if instance.id not in subordinate_ids:
                return Response({
                    'success': False,
                    'data': None,
                    'message': 'You do not have permission to update this user',
                    'errors': []
                }, status=status.HTTP_403_FORBIDDEN)
        
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        if serializer.is_valid():
            user = serializer.save()
            user_data = UserDetailSerializer(user, context=self.get_serializer_context()).data
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

    @action(detail=True, methods=['get'], url_path='wallets')
    def user_wallets(self, request, pk=None):
        """Admin-only: read wallet balances for any user."""
        if getattr(request.user, 'role', None) != 'Admin':
            return Response(
                {
                    'success': False,
                    'data': None,
                    'message': 'Only administrators may view user wallet balances.',
                    'errors': [],
                },
                status=status.HTTP_403_FORBIDDEN,
            )
        instance = self.get_object()
        return Response(
            {
                'success': True,
                'data': {'wallets': build_wallet_summary(instance)},
                'message': 'User wallets retrieved successfully',
                'errors': [],
            },
            status=status.HTTP_200_OK,
        )

    @action(detail=True, methods=['patch'], url_path='contact')
    def update_contact(self, request, pk=None):
        """Admin-only: update another user's mobile (login) and email."""
        if getattr(request.user, 'role', None) != 'Admin':
            return Response(
                {
                    'success': False,
                    'data': None,
                    'message': 'Only administrators may update user contact details.',
                    'errors': [],
                },
                status=status.HTTP_403_FORBIDDEN,
            )
        instance = self.get_object()
        if instance.pk == request.user.pk:
            return Response(
                {
                    'success': False,
                    'data': None,
                    'message': 'You cannot change your own contact details here. Ask another administrator.',
                    'errors': [],
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        serializer = AdminUserContactSerializer(
            instance,
            data=request.data,
            partial=False,
            context=self.get_serializer_context(),
        )
        if not serializer.is_valid():
            return Response(
                {
                    'success': False,
                    'data': None,
                    'message': 'Invalid contact details',
                    'errors': serializer.errors,
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        user = serializer.save()
        user_data = UserDetailSerializer(user, context=self.get_serializer_context()).data
        return Response(
            {
                'success': True,
                'data': {'user': user_data},
                'message': 'Contact details updated successfully',
                'errors': [],
            },
            status=status.HTTP_200_OK,
        )

    @action(detail=True, methods=['patch'], url_path='role')
    def change_role(self, request, pk=None):
        """Admin-only: promote/demote user role with hierarchy checks."""
        if getattr(request.user, 'role', None) != 'Admin':
            return Response(
                {
                    'success': False,
                    'data': None,
                    'message': 'Only administrators may change user roles.',
                    'errors': [],
                },
                status=status.HTTP_403_FORBIDDEN,
            )
        instance = self.get_object()
        serializer = UserRoleChangeSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(
                {
                    'success': False,
                    'data': None,
                    'message': 'Invalid role payload',
                    'errors': serializer.errors,
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            admin_change_user_role(
                actor=request.user,
                target=instance,
                new_role=serializer.validated_data['role'],
            )
        except ValueError as e:
            return Response(
                {
                    'success': False,
                    'data': None,
                    'message': str(e),
                    'errors': [],
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        instance.refresh_from_db()
        user_data = UserDetailSerializer(instance, context=self.get_serializer_context()).data
        return Response(
            {
                'success': True,
                'data': {'user': user_data},
                'message': 'User role updated successfully',
                'errors': [],
            },
            status=status.HTTP_200_OK,
        )

    @action(detail=True, methods=['patch'], url_path='active-status')
    def set_active_status(self, request, pk=None):
        """Admin-only: enable or disable login / API access for a user (is_active)."""
        if getattr(request.user, 'role', None) != 'Admin':
            return Response(
                {
                    'success': False,
                    'data': None,
                    'message': 'Only administrators may enable or disable user accounts.',
                    'errors': [],
                },
                status=status.HTTP_403_FORBIDDEN,
            )
        instance = self.get_object()
        serializer = UserActiveStatusSerializer(
            data=request.data,
            context={'request': request, 'target': instance},
        )
        if not serializer.is_valid():
            return Response(
                {
                    'success': False,
                    'data': None,
                    'message': 'Invalid account status payload',
                    'errors': serializer.errors,
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        patch = {'is_active': serializer.validated_data['is_active']}
        if 'pay_in_allowed_when_disabled' in serializer.validated_data:
            patch['pay_in_allowed_when_disabled'] = serializer.validated_data['pay_in_allowed_when_disabled']
        try:
            instance = apply_user_access_controls(
                actor=request.user,
                target=instance,
                patch=patch,
            )
        except ValueError as e:
            return Response(
                {'success': False, 'data': None, 'message': str(e), 'errors': []},
                status=status.HTTP_400_BAD_REQUEST,
            )
        from apps.users.access_messages import message_for_access_controls_update

        user_data = UserDetailSerializer(instance, context=self.get_serializer_context()).data
        return Response(
            {
                'success': True,
                'data': {'user': user_data},
                'message': message_for_access_controls_update(instance, patch),
                'errors': [],
            },
            status=status.HTTP_200_OK,
        )

    @action(detail=True, methods=['patch'], url_path='access-controls')
    def set_access_controls(self, request, pk=None):
        """Admin-only: restrict, lock payments, disable, or allow pay-in when disabled."""
        if getattr(request.user, 'role', None) != 'Admin':
            return Response(
                {
                    'success': False,
                    'data': None,
                    'message': 'Only administrators may change user access controls.',
                    'errors': [],
                },
                status=status.HTTP_403_FORBIDDEN,
            )
        instance = self.get_object()
        serializer = UserAccessControlsSerializer(
            data=request.data,
            context={'request': request, 'target': instance},
        )
        if not serializer.is_valid():
            return Response(
                {
                    'success': False,
                    'data': None,
                    'message': 'Invalid access controls payload',
                    'errors': serializer.errors,
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            instance = apply_user_access_controls(
                actor=request.user,
                target=instance,
                patch=serializer.validated_data,
            )
        except ValueError as e:
            return Response(
                {'success': False, 'data': None, 'message': str(e), 'errors': []},
                status=status.HTTP_400_BAD_REQUEST,
            )
        from apps.users.access_messages import message_for_access_controls_update

        user_data = UserDetailSerializer(instance, context=self.get_serializer_context()).data
        return Response(
            {
                'success': True,
                'data': {'user': user_data},
                'message': message_for_access_controls_update(instance, serializer.validated_data),
                'errors': [],
            },
            status=status.HTTP_200_OK,
        )
