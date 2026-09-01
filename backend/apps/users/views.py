"""
User management views for the mPayhub platform.
"""
import logging

from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.pagination import PageNumberPagination
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
    KycAdminDecisionSerializer,
)
from apps.users.services import (
    admin_change_user_role,
    admin_approve_kyc,
    admin_reject_kyc,
    apply_user_access_controls,
    create_user,
    delete_user_account,
    verify_pan,
    get_subordinates,
    get_viewable_user_ids,
)
from apps.users.hierarchy_policy import (
    assignable_roles_for_admin_change,
    creatable_roles_for,
    policy_snapshot,
)
from apps.wallets.views import build_wallet_summary

logger = logging.getLogger(__name__)


class UserDirectoryPagination(PageNumberPagination):
    page_size = 25
    page_size_query_param = 'page_size'
    max_page_size = 100


class UserViewSet(viewsets.ModelViewSet):
    """
    ViewSet for user management.
    """
    queryset = User.objects.all()
    permission_classes = [IsAuthenticated]
    pagination_class = UserDirectoryPagination
    
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
                models.Q(display_code__icontains=search) |
                models.Q(member_id__icontains=search) |
                models.Q(phone__icontains=search) |
                models.Q(email__icontains=search) |
                models.Q(profile__business_name__icontains=search)
            )
        
        # Get paginated results
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            paginator = self.paginator
            page_obj = getattr(paginator, 'page', None)
            total = page_obj.paginator.count if page_obj is not None else queryset.count()
            page_number = page_obj.number if page_obj is not None else 1
            page_size = paginator.get_page_size(request)
            return Response({
                'success': True,
                'data': {
                    'users': serializer.data,
                    'total': total,
                    'page': page_number,
                    'page_size': page_size,
                },
                'message': 'Users retrieved successfully',
                'errors': []
            })
        
        serializer = self.get_serializer(queryset, many=True)
        return Response({
            'success': True,
            'data': {
                'users': serializer.data,
                'total': queryset.count(),
                'page': 1,
                'page_size': queryset.count(),
            },
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
                    from apps.users.identity import public_display_code

                    to_email = (user.email or '').strip()
                    if to_email:
                        EmailNotificationService.dispatch(
                            'onboarding.user_created',
                            to_email,
                            {
                                'name': user_display_name(user),
                                'user_id': public_display_code(user),
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
            except Exception as e:
                from django.db import IntegrityError

                if isinstance(e, IntegrityError):
                    logger.exception('User create failed: integrity error')
                    return Response({
                        'success': False,
                        'data': None,
                        'message': 'Could not assign a unique user ID. Please retry.',
                        'errors': [str(e)],
                    }, status=status.HTTP_400_BAD_REQUEST)
                logger.exception('User create failed')
                return Response({
                    'success': False,
                    'data': None,
                    'message': 'User creation failed',
                    'errors': [str(e)],
                }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        
        return Response({
            'success': False,
            'data': None,
            'message': 'User creation failed',
            'errors': serializer.errors
        }, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=True, methods=['post'])
    def verify_pan(self, request, pk=None):
        """Verify PAN for a user (Admin only; requires explicit name as per PAN)."""
        if getattr(request.user, 'role', None) != 'Admin' and not getattr(request.user, 'is_superuser', False):
            return Response({
                'success': False,
                'data': None,
                'message': 'Only administrators can verify PAN on behalf of users.',
                'errors': [],
            }, status=status.HTTP_403_FORBIDDEN)

        user = self.get_object()
        serializer = PANVerificationSerializer(data=request.data)
        
        if serializer.is_valid():
            pan = serializer.validated_data['pan']
            name = serializer.validated_data['name']
            if verify_pan(user, pan, name=name):
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
        """Deprecated — Aadhaar SMS OTP replaced by DigiLocker."""
        return Response({
            'success': False,
            'data': None,
            'message': 'Aadhaar OTP is no longer supported. Use DigiLocker verification.',
            'errors': [],
        }, status=status.HTTP_410_GONE)

    @action(detail=True, methods=['post'])
    def verify_aadhaar_otp(self, request, pk=None):
        """Deprecated — Aadhaar SMS OTP replaced by DigiLocker."""
        return Response({
            'success': False,
            'data': None,
            'message': 'Aadhaar OTP is no longer supported. Use DigiLocker verification.',
            'errors': [],
        }, status=status.HTTP_410_GONE)
    
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
        """Permanently delete a user and all related account data (Admin only)."""
        instance = self.get_object()
        try:
            user_id = delete_user_account(actor=request.user, target=instance)
        except ValueError as e:
            msg = str(e)
            code = status.HTTP_403_FORBIDDEN if 'Only administrators' in msg else status.HTTP_400_BAD_REQUEST
            return Response({
                'success': False,
                'data': None,
                'message': msg,
                'errors': [],
            }, status=code)
        except Exception:
            logger.exception('Failed to delete user %s', getattr(instance, 'pk', None))
            return Response({
                'success': False,
                'data': None,
                'message': 'Could not delete user. The account may have linked records that block removal.',
                'errors': [],
            }, status=status.HTTP_400_BAD_REQUEST)

        return Response({
            'success': True,
            'data': {'user_id': user_id},
            'message': 'User and all account data deleted permanently.',
            'errors': [],
        }, status=status.HTTP_200_OK)
    
    @action(detail=False, methods=['get'])
    def subordinates(self, request):
        """Get subordinate users (paginated)."""
        sub_ids = [u.pk for u in get_subordinates(request.user)]
        queryset = User.objects.filter(pk__in=sub_ids).select_related('profile', 'kyc').order_by('-created_at')
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = UserListSerializer(page, many=True)
            paginator = self.paginator
            page_obj = getattr(paginator, 'page', None)
            total = page_obj.paginator.count if page_obj is not None else queryset.count()
            page_number = page_obj.number if page_obj is not None else 1
            page_size = paginator.get_page_size(request)
            return Response({
                'success': True,
                'data': {
                    'users': serializer.data,
                    'total': total,
                    'page': page_number,
                    'page_size': page_size,
                },
                'message': 'Subordinates retrieved successfully',
                'errors': [],
            }, status=status.HTTP_200_OK)
        serializer = UserListSerializer(queryset, many=True)
        return Response({
            'success': True,
            'data': {'users': serializer.data, 'total': len(serializer.data), 'page': 1, 'page_size': len(serializer.data)},
            'message': 'Subordinates retrieved successfully',
            'errors': [],
        }, status=status.HTTP_200_OK)

    @action(detail=False, methods=['get'], url_path='creatable-roles')
    def creatable_roles(self, request):
        """Roles the current user may onboard as direct reports."""
        roles = creatable_roles_for(getattr(request.user, 'role', None))
        return Response({
            'success': True,
            'data': {
                'roles': roles,
                'policy': policy_snapshot(),
            },
            'message': 'Creatable roles retrieved successfully',
            'errors': [],
        }, status=status.HTTP_200_OK)

    @action(detail=False, methods=['get'], url_path='assignable-roles')
    def assignable_roles(self, request):
        """All roles an Admin may assign when changing a user's role."""
        if getattr(request.user, 'role', None) != 'Admin':
            return Response(
                {
                    'success': False,
                    'data': None,
                    'message': 'Only administrators may list assignable roles.',
                    'errors': [],
                },
                status=status.HTTP_403_FORBIDDEN,
            )
        return Response(
            {
                'success': True,
                'data': {'roles': assignable_roles_for_admin_change()},
                'message': 'Assignable roles retrieved successfully',
                'errors': [],
            },
            status=status.HTTP_200_OK,
        )

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

    @action(detail=True, methods=['post'], url_path='kyc-approval')
    def kyc_approval(self, request, pk=None):
        """Admin-only: approve or reject KYC after provider verification."""
        if getattr(request.user, 'role', None) != 'Admin':
            return Response(
                {
                    'success': False,
                    'data': None,
                    'message': 'Only administrators may approve or reject KYC.',
                    'errors': [],
                },
                status=status.HTTP_403_FORBIDDEN,
            )
        instance = self.get_object()
        serializer = KycAdminDecisionSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(
                {
                    'success': False,
                    'data': None,
                    'message': 'Invalid KYC approval payload',
                    'errors': serializer.errors,
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        decision = serializer.validated_data['decision']
        notes = serializer.validated_data.get('notes') or ''
        try:
            if decision == 'approve':
                admin_approve_kyc(actor=request.user, target_user=instance, notes=notes)
                message = 'KYC approved. User can complete onboarding and activate their account.'
            else:
                admin_reject_kyc(actor=request.user, target_user=instance, notes=notes)
                message = 'KYC rejected. User account remains inactive until KYC is approved.'
        except ValueError as e:
            return Response(
                {'success': False, 'data': None, 'message': str(e), 'errors': []},
                status=status.HTTP_400_BAD_REQUEST,
            )
        instance.refresh_from_db()
        user_data = UserDetailSerializer(instance, context=self.get_serializer_context()).data
        return Response(
            {
                'success': True,
                'data': {'user': user_data},
                'message': message,
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
