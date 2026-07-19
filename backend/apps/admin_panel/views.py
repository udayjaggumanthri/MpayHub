"""
Admin panel views for the mPayhub platform.
"""
from django.db.models import Q
from django.utils.dateparse import parse_date
from rest_framework import status, viewsets
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from apps.admin_panel.models import Announcement, PaymentGateway, PayoutGateway, PayoutSlabConfig, SmtpConfig
from apps.admin_panel.serializers import (
    AnnouncementSerializer,
    PayInPackageAdminSerializer,
    PaymentGatewaySerializer,
    PayoutGatewaySerializer,
    PayoutSlabConfigSerializer,
    SmtpConfigSerializer,
    SmtpSecretUpdateSerializer,
    SmtpTestEmailSerializer,
)
from apps.core.permissions import IsAdmin
from apps.fund_management.models import PayInPackage
from apps.fund_management.services import quote_payin


class AnnouncementViewSet(viewsets.ModelViewSet):
    """
    List/retrieve: any authenticated user sees active announcements for their role.
    Create/update/delete: Admin only.
    """

    queryset = Announcement.objects.all()
    serializer_class = AnnouncementSerializer
    permission_classes = [IsAuthenticated]
    parser_classes = [JSONParser, MultiPartParser, FormParser]

    def get_permissions(self):
        if self.action in ('list', 'retrieve'):
            return [IsAuthenticated()]
        return [IsAuthenticated(), IsAdmin()]

    def get_queryset(self):
        user = self.request.user
        base = Announcement.objects.all()

        if user.role != 'Admin':
            role = user.role
            return base.filter(
                is_active=True,
            ).filter(
                Q(target_roles__contains=[role]) | Q(target_roles__contains=['All'])
            )

        qs = base
        params = self.request.query_params

        search = (params.get('search') or params.get('q') or '').strip()
        if search:
            qs = qs.filter(
                Q(title__icontains=search) | Q(message__icontains=search)
            )

        priority = (params.get('priority') or '').strip().lower()
        if priority in ('low', 'medium', 'high'):
            qs = qs.filter(priority=priority)

        is_active_param = params.get('is_active')
        if is_active_param is not None and str(is_active_param).strip() != '':
            v = str(is_active_param).strip().lower()
            if v in ('true', '1', 'yes'):
                qs = qs.filter(is_active=True)
            elif v in ('false', '0', 'no'):
                qs = qs.filter(is_active=False)

        target_role = (params.get('target_role') or '').strip()
        if target_role:
            qs = qs.filter(target_roles__contains=[target_role])

        created_after = parse_date(params.get('created_after') or '')
        if created_after:
            qs = qs.filter(created_at__date__gte=created_after)

        created_before = parse_date(params.get('created_before') or '')
        if created_before:
            qs = qs.filter(created_at__date__lte=created_before)

        return qs.order_by('-created_at')

    def get_serializer_context(self):
        ctx = super().get_serializer_context()
        ctx['request'] = self.request
        return ctx


class PaymentGatewayViewSet(viewsets.ModelViewSet):
    """
    ViewSet for payment gateway management (Admin only).
    """
    queryset = PaymentGateway.objects.select_related('api_master').all()
    serializer_class = PaymentGatewaySerializer
    permission_classes = [IsAuthenticated, IsAdmin]
    
    @action(detail=True, methods=['post'])
    def toggle_status(self, request, pk=None):
        """Toggle gateway status."""
        gateway = self.get_object()
        gateway.status = 'down' if gateway.status == 'active' else 'active'
        gateway.save(update_fields=['status'])
        serializer = self.get_serializer(gateway)
        return Response({
            'success': True,
            'data': {'gateway': serializer.data},
            'message': 'Gateway status updated successfully',
            'errors': []
        }, status=status.HTTP_200_OK)


class PayoutGatewayViewSet(viewsets.ModelViewSet):
    """
    ViewSet for payout gateway management (Admin only).
    """
    queryset = PayoutGateway.objects.all()
    serializer_class = PayoutGatewaySerializer
    permission_classes = [IsAuthenticated, IsAdmin]
    
    @action(detail=True, methods=['post'])
    def toggle_status(self, request, pk=None):
        """Toggle gateway status."""
        gateway = self.get_object()
        gateway.status = 'down' if gateway.status == 'active' else 'active'
        gateway.save(update_fields=['status'])
        serializer = self.get_serializer(gateway)
        return Response({
            'success': True,
            'data': {'gateway': serializer.data},
            'message': 'Gateway status updated successfully',
            'errors': []
        }, status=status.HTTP_200_OK)


class PayInPackageViewSet(viewsets.ModelViewSet):
    """
    ViewSet for admin pay-in package + commission configuration.
    """

    queryset = (
        PayInPackage.objects.filter(is_deleted=False)
        .select_related('payment_gateway')
        .prefetch_related(
            'payout_slabs',
            'package_gateways__payment_gateway',
        )
        .order_by('sort_order', 'display_name')
    )
    serializer_class = PayInPackageAdminSerializer
    permission_classes = [IsAuthenticated, IsAdmin]

    @action(detail=True, methods=['post'])
    def preview(self, request, pk=None):
        """
        POST /api/admin/pay-in-packages/{id}/preview/
        Body: {"amount": "100000"}
        """
        package = self.get_object()
        amount = request.data.get('amount')
        if amount is None:
            return Response(
                {
                    'success': False,
                    'data': None,
                    'message': 'amount is required',
                    'errors': {'amount': ['This field is required.']},
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            q = quote_payin(package, amount)
        except ValueError as e:
            return Response(
                {'success': False, 'data': None, 'message': str(e), 'errors': []},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return Response(
            {
                'success': True,
                'data': {
                    'breakdown': q['snapshot'],
                    'lines': q['lines'],
                    'net_credit': str(q['net_credit']),
                    'total_deduction': str(q['total_deduction']),
                    'retailer_commission': str(q['retailer_commission']),
                    'retailer_share_absorbed_to_admin': str(q['retailer_share_absorbed_to_admin']),
                },
                'message': 'Preview generated',
                'errors': [],
            },
            status=status.HTTP_200_OK,
        )


@api_view(['GET', 'PUT'])
@permission_classes([IsAuthenticated, IsAdmin])
def payout_slab_config_view(request):
    """Get/update singleton payout slab configuration used by payout quote/processing."""
    config = (
        PayoutSlabConfig.objects.filter(is_active=True).order_by('-updated_at', '-id').first()
        or PayoutSlabConfig.objects.order_by('-updated_at', '-id').first()
    )

    if request.method == 'GET':
        if not config:
            config = PayoutSlabConfig.objects.create()
        ser = PayoutSlabConfigSerializer(config)
        return Response(
            {
                'success': True,
                'data': {
                    'config': ser.data,
                    'role': 'system_fallback',
                    'description': (
                        'Fallback two-tier slab when a pay-in package has no payout tiers. '
                        'Prefer configuring payout_slabs on each package.'
                    ),
                },
                'message': 'Payout slab config retrieved',
                'errors': [],
            },
            status=status.HTTP_200_OK,
        )

    if not config:
        config = PayoutSlabConfig.objects.create()
    ser = PayoutSlabConfigSerializer(config, data=request.data, partial=True)
    if not ser.is_valid():
        return Response(
            {'success': False, 'data': None, 'message': 'Invalid input', 'errors': ser.errors},
            status=status.HTTP_400_BAD_REQUEST,
        )
    cfg = ser.save()
    out = PayoutSlabConfigSerializer(cfg).data
    return Response(
        {
            'success': True,
            'data': {
                'config': out,
                'role': 'system_fallback',
                'description': (
                    'Fallback two-tier slab when a pay-in package has no payout tiers. '
                    'Prefer configuring payout_slabs on each package.'
                ),
            },
            'message': 'Payout slab config updated',
            'errors': [],
        },
        status=status.HTTP_200_OK,
    )


def _smtp_configs_queryset():
    return SmtpConfig.objects.filter(is_deleted=False).order_by('-is_active', '-updated_at', 'name')


def _get_smtp_config(pk=None):
    if pk is not None:
        return SmtpConfig.objects.filter(pk=pk, is_deleted=False).first()
    return (
        SmtpConfig.objects.filter(is_deleted=False, is_active=True).order_by('-updated_at').first()
        or SmtpConfig.objects.filter(is_deleted=False).order_by('-updated_at').first()
    )


def _deactivate_other_smtp_configs(exclude_pk):
    SmtpConfig.objects.filter(is_deleted=False).exclude(pk=exclude_pk).update(is_active=False)


def _smtp_profile_summary(cfg: SmtpConfig) -> str:
    host = (cfg.host or '').strip() or '—'
    return f'{host}:{cfg.port}'


@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated, IsAdmin])
def smtp_config_list_view(request):
    """List all SMTP profiles (GET) or create a new profile (POST)."""
    if request.method == 'GET':
        configs = _smtp_configs_queryset()
        active = configs.filter(is_active=True).first()
        serialized = SmtpConfigSerializer(configs, many=True).data
        return Response(
            {
                'success': True,
                'data': {
                    'configs': serialized,
                    'active_config': SmtpConfigSerializer(active).data if active else None,
                    'config': SmtpConfigSerializer(active).data if active else None,
                },
                'message': 'SMTP profiles retrieved successfully',
                'errors': [],
            },
            status=status.HTTP_200_OK,
        )

    ser = SmtpConfigSerializer(data=request.data)
    if not ser.is_valid():
        return Response(
            {'success': False, 'data': None, 'message': 'Invalid SMTP profile', 'errors': ser.errors},
            status=status.HTTP_400_BAD_REQUEST,
        )
    cfg = ser.save()
    if cfg.is_active:
        _deactivate_other_smtp_configs(cfg.pk)
    return Response(
        {
            'success': True,
            'data': {'config': SmtpConfigSerializer(cfg).data},
            'message': f'SMTP profile "{cfg.name}" created',
            'errors': [],
        },
        status=status.HTTP_201_CREATED,
    )


@api_view(['GET', 'PUT', 'DELETE'])
@permission_classes([IsAuthenticated, IsAdmin])
def smtp_config_detail_view(request, pk):
    """Retrieve, update, or soft-delete a single SMTP profile."""
    config = _get_smtp_config(pk)
    if not config:
        return Response(
            {'success': False, 'data': None, 'message': 'SMTP profile not found', 'errors': []},
            status=status.HTTP_404_NOT_FOUND,
        )

    if request.method == 'GET':
        return Response(
            {
                'success': True,
                'data': {'config': SmtpConfigSerializer(config).data},
                'message': 'SMTP profile retrieved',
                'errors': [],
            },
            status=status.HTTP_200_OK,
        )

    if request.method == 'DELETE':
        was_active = config.is_active
        config.soft_delete()
        if was_active:
            replacement = _smtp_configs_queryset().first()
            if replacement:
                replacement.is_active = True
                replacement.save(update_fields=['is_active', 'updated_at'])
        return Response(
            {
                'success': True,
                'data': None,
                'message': f'SMTP profile "{config.name}" deleted',
                'errors': [],
            },
            status=status.HTTP_200_OK,
        )

    ser = SmtpConfigSerializer(config, data=request.data, partial=True)
    if not ser.is_valid():
        return Response(
            {'success': False, 'data': None, 'message': 'Invalid SMTP profile', 'errors': ser.errors},
            status=status.HTTP_400_BAD_REQUEST,
        )
    cfg = ser.save()
    if cfg.is_active:
        _deactivate_other_smtp_configs(cfg.pk)
    return Response(
        {
            'success': True,
            'data': {'config': SmtpConfigSerializer(cfg).data},
            'message': f'SMTP profile "{cfg.name}" updated',
            'errors': [],
        },
        status=status.HTTP_200_OK,
    )


@api_view(['POST'])
@permission_classes([IsAuthenticated, IsAdmin])
def smtp_config_activate_view(request, pk):
    """Mark one profile as active (only one active at a time)."""
    config = _get_smtp_config(pk)
    if not config:
        return Response(
            {'success': False, 'data': None, 'message': 'SMTP profile not found', 'errors': []},
            status=status.HTTP_404_NOT_FOUND,
        )
    if not config.enabled:
        return Response(
            {
                'success': False,
                'data': None,
                'message': 'Enable this profile before activating it.',
                'errors': [],
            },
            status=status.HTTP_400_BAD_REQUEST,
        )
    if not config.get_password():
        return Response(
            {
                'success': False,
                'data': None,
                'message': 'Set an SMTP password on this profile before activating.',
                'errors': [],
            },
            status=status.HTTP_400_BAD_REQUEST,
        )
    config.is_active = True
    config.save(update_fields=['is_active', 'updated_at'])
    _deactivate_other_smtp_configs(config.pk)
    return Response(
        {
            'success': True,
            'data': {'config': SmtpConfigSerializer(config).data},
            'message': f'"{config.name}" is now the active SMTP profile for OTP email',
            'errors': [],
        },
        status=status.HTTP_200_OK,
    )


@api_view(['POST'])
@permission_classes([IsAuthenticated, IsAdmin])
def smtp_config_deactivate_view(request, pk):
    """Remove active flag from a profile (no profile sends OTP email until another is activated)."""
    config = _get_smtp_config(pk)
    if not config:
        return Response(
            {'success': False, 'data': None, 'message': 'SMTP profile not found', 'errors': []},
            status=status.HTTP_404_NOT_FOUND,
        )
    config.is_active = False
    config.save(update_fields=['is_active', 'updated_at'])
    return Response(
        {
            'success': True,
            'data': {'config': SmtpConfigSerializer(config).data},
            'message': f'"{config.name}" deactivated. Activate another profile to send OTP email.',
            'errors': [],
        },
        status=status.HTTP_200_OK,
    )


@api_view(['POST'])
@permission_classes([IsAuthenticated, IsAdmin])
def smtp_config_secrets_view(request, pk):
    """Update SMTP password for a specific profile (encrypted at rest)."""
    config = _get_smtp_config(pk)
    if not config:
        return Response(
            {'success': False, 'data': None, 'message': 'SMTP profile not found', 'errors': []},
            status=status.HTTP_404_NOT_FOUND,
        )
    ser = SmtpSecretUpdateSerializer(data=request.data)
    if not ser.is_valid():
        return Response(
            {'success': False, 'data': None, 'message': 'Invalid secrets', 'errors': ser.errors},
            status=status.HTTP_400_BAD_REQUEST,
        )
    val = ser.validated_data
    if 'password' in val and (val.get('password') or '').strip():
        config.set_password((val.get('password') or '').strip())
        config.save(update_fields=['password_encrypted', 'updated_at'])
    return Response(
        {
            'success': True,
            'data': {'config': SmtpConfigSerializer(config).data},
            'message': 'SMTP password saved',
            'errors': [],
        },
        status=status.HTTP_200_OK,
    )


@api_view(['POST'])
@permission_classes([IsAuthenticated, IsAdmin])
def smtp_config_test_view(request, pk):
    """Send a test email using the selected SMTP profile."""
    from apps.integrations.email_service import EmailDeliveryError, send_email

    config = _get_smtp_config(pk)
    if not config:
        return Response(
            {'success': False, 'data': None, 'message': 'SMTP profile not found', 'errors': []},
            status=status.HTTP_404_NOT_FOUND,
        )
    if not config.enabled:
        return Response(
            {
                'success': False,
                'data': None,
                'message': 'Enable this SMTP profile before sending a test email.',
                'errors': [],
            },
            status=status.HTTP_400_BAD_REQUEST,
        )
    if not config.get_password():
        return Response(
            {
                'success': False,
                'data': None,
                'message': 'Set an SMTP password on this profile before testing.',
                'errors': [],
            },
            status=status.HTTP_400_BAD_REQUEST,
        )
    ser = SmtpTestEmailSerializer(data=request.data)
    if not ser.is_valid():
        return Response(
            {'success': False, 'data': None, 'message': 'Invalid input', 'errors': ser.errors},
            status=status.HTTP_400_BAD_REQUEST,
        )
    to_email = (ser.validated_data.get('to_email') or '').strip() or getattr(request.user, 'email', '') or ''
    if not to_email:
        return Response(
            {
                'success': False,
                'data': None,
                'message': 'Provide to_email or ensure your admin account has an email address.',
                'errors': [],
            },
            status=status.HTTP_400_BAD_REQUEST,
        )
    try:
        send_email(
            to_email=to_email,
            subject=f'mPayhub SMTP test — {config.name}',
            body_plain=f'Test message from SMTP profile "{config.name}" ({_smtp_profile_summary(config)}).',
            body_html=(
                f'<p>Test message from SMTP profile <strong>{config.name}</strong> '
                f'(<code>{_smtp_profile_summary(config)}</code>).</p>'
            ),
            cfg=config,
        )
    except EmailDeliveryError as exc:
        return Response(
            {'success': False, 'data': None, 'message': str(exc), 'errors': []},
            status=status.HTTP_400_BAD_REQUEST,
        )
    return Response(
        {
            'success': True,
            'data': {'sent_to': to_email, 'profile': config.name},
            'message': (
                f'Test email accepted by SMTP server for {to_email} using profile "{config.name}". '
                'Check inbox and spam; delivery may take 1–2 minutes.'
            ),
            'errors': [],
        },
        status=status.HTTP_200_OK,
    )


# Legacy aliases (single-config clients): list + active profile; secrets/test require profile id in URL.
smtp_config_view = smtp_config_list_view


def _sms_configs_queryset():
    from apps.notifications.models import SmsProviderConfig

    return SmsProviderConfig.objects.filter(is_deleted=False).order_by('-is_active', '-updated_at', 'name')


def _get_sms_config(pk=None):
    from apps.notifications.models import SmsProviderConfig

    if pk is not None:
        return SmsProviderConfig.objects.filter(pk=pk, is_deleted=False).first()
    return (
        SmsProviderConfig.objects.filter(is_deleted=False, is_active=True).order_by('-updated_at').first()
        or SmsProviderConfig.objects.filter(is_deleted=False).order_by('-updated_at').first()
    )


def _deactivate_other_sms_configs(exclude_pk):
    from apps.notifications.models import SmsProviderConfig

    SmsProviderConfig.objects.filter(is_deleted=False).exclude(pk=exclude_pk).update(is_active=False)


@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated, IsAdmin])
def sms_config_list_view(request):
    """List all SMS provider profiles (GET) or create a new profile (POST)."""
    from apps.admin_panel.serializers import SmsProviderConfigSerializer

    if request.method == 'GET':
        configs = _sms_configs_queryset()
        active = configs.filter(is_active=True).first()
        serialized = SmsProviderConfigSerializer(configs, many=True).data
        return Response(
            {
                'success': True,
                'data': {
                    'configs': serialized,
                    'active_config': SmsProviderConfigSerializer(active).data if active else None,
                    'config': SmsProviderConfigSerializer(active).data if active else None,
                },
                'message': 'SMS profiles retrieved successfully',
                'errors': [],
            },
            status=status.HTTP_200_OK,
        )

    ser = SmsProviderConfigSerializer(data=request.data)
    if not ser.is_valid():
        return Response(
            {'success': False, 'data': None, 'message': 'Invalid SMS profile', 'errors': ser.errors},
            status=status.HTTP_400_BAD_REQUEST,
        )
    cfg = ser.save()
    # Optional authkey on create (MSG91) — never returned in responses
    auth_key = (request.data.get('auth_key') or '').strip()
    if auth_key:
        cfg.set_auth_key(auth_key)
        cfg.save(update_fields=['auth_key_encrypted', 'updated_at'])
    if cfg.provider == 'msg91' and not cfg.get_auth_key():
        # Allow create without key, but do not leave as active until key exists
        if cfg.is_active:
            cfg.is_active = False
            cfg.save(update_fields=['is_active', 'updated_at'])
    elif cfg.is_active:
        _deactivate_other_sms_configs(cfg.pk)
    return Response(
        {
            'success': True,
            'data': {'config': SmsProviderConfigSerializer(cfg).data},
            'message': f'SMS profile "{cfg.name}" created',
            'errors': [],
        },
        status=status.HTTP_201_CREATED,
    )


@api_view(['GET', 'PUT', 'DELETE'])
@permission_classes([IsAuthenticated, IsAdmin])
def sms_config_detail_view(request, pk):
    from apps.admin_panel.serializers import SmsProviderConfigSerializer

    config = _get_sms_config(pk)
    if not config:
        return Response(
            {'success': False, 'data': None, 'message': 'SMS profile not found', 'errors': []},
            status=status.HTTP_404_NOT_FOUND,
        )

    if request.method == 'GET':
        return Response(
            {
                'success': True,
                'data': {'config': SmsProviderConfigSerializer(config).data},
                'message': 'SMS profile retrieved',
                'errors': [],
            },
            status=status.HTTP_200_OK,
        )

    if request.method == 'DELETE':
        was_active = config.is_active
        config.soft_delete()
        if was_active:
            replacement = _sms_configs_queryset().first()
            if replacement:
                replacement.is_active = True
                replacement.save(update_fields=['is_active', 'updated_at'])
        return Response(
            {
                'success': True,
                'data': None,
                'message': f'SMS profile "{config.name}" deleted',
                'errors': [],
            },
            status=status.HTTP_200_OK,
        )

    ser = SmsProviderConfigSerializer(config, data=request.data, partial=True)
    if not ser.is_valid():
        return Response(
            {'success': False, 'data': None, 'message': 'Invalid SMS profile', 'errors': ser.errors},
            status=status.HTTP_400_BAD_REQUEST,
        )
    cfg = ser.save()
    if cfg.is_active:
        _deactivate_other_sms_configs(cfg.pk)
    return Response(
        {
            'success': True,
            'data': {'config': SmsProviderConfigSerializer(cfg).data},
            'message': f'SMS profile "{cfg.name}" updated',
            'errors': [],
        },
        status=status.HTTP_200_OK,
    )


@api_view(['POST'])
@permission_classes([IsAuthenticated, IsAdmin])
def sms_config_activate_view(request, pk):
    from apps.admin_panel.serializers import SmsProviderConfigSerializer

    config = _get_sms_config(pk)
    if not config:
        return Response(
            {'success': False, 'data': None, 'message': 'SMS profile not found', 'errors': []},
            status=status.HTTP_404_NOT_FOUND,
        )
    if not config.enabled:
        return Response(
            {
                'success': False,
                'data': None,
                'message': 'Enable this profile before activating it.',
                'errors': [],
            },
            status=status.HTTP_400_BAD_REQUEST,
        )
    if not config.get_auth_key():
        return Response(
            {
                'success': False,
                'data': None,
                'message': 'Set an MSG91 auth key on this profile before activating.',
                'errors': [],
            },
            status=status.HTTP_400_BAD_REQUEST,
        )
    config.is_active = True
    config.save(update_fields=['is_active', 'updated_at'])
    _deactivate_other_sms_configs(config.pk)
    return Response(
        {
            'success': True,
            'data': {'config': SmsProviderConfigSerializer(config).data},
            'message': f'"{config.name}" is now the active SMS profile for notifications',
            'errors': [],
        },
        status=status.HTTP_200_OK,
    )


@api_view(['POST'])
@permission_classes([IsAuthenticated, IsAdmin])
def sms_config_deactivate_view(request, pk):
    from apps.admin_panel.serializers import SmsProviderConfigSerializer

    config = _get_sms_config(pk)
    if not config:
        return Response(
            {'success': False, 'data': None, 'message': 'SMS profile not found', 'errors': []},
            status=status.HTTP_404_NOT_FOUND,
        )
    config.is_active = False
    config.save(update_fields=['is_active', 'updated_at'])
    return Response(
        {
            'success': True,
            'data': {'config': SmsProviderConfigSerializer(config).data},
            'message': f'"{config.name}" deactivated. Activate another profile to send SMS.',
            'errors': [],
        },
        status=status.HTTP_200_OK,
    )


@api_view(['POST'])
@permission_classes([IsAuthenticated, IsAdmin])
def sms_config_secrets_view(request, pk):
    from apps.admin_panel.serializers import SmsProviderConfigSerializer, SmsSecretUpdateSerializer

    config = _get_sms_config(pk)
    if not config:
        return Response(
            {'success': False, 'data': None, 'message': 'SMS profile not found', 'errors': []},
            status=status.HTTP_404_NOT_FOUND,
        )
    ser = SmsSecretUpdateSerializer(data=request.data)
    if not ser.is_valid():
        return Response(
            {'success': False, 'data': None, 'message': 'Invalid secrets', 'errors': ser.errors},
            status=status.HTTP_400_BAD_REQUEST,
        )
    val = ser.validated_data
    if 'auth_key' in val and (val.get('auth_key') or '').strip():
        config.set_auth_key((val.get('auth_key') or '').strip())
        config.save(update_fields=['auth_key_encrypted', 'updated_at'])
    return Response(
        {
            'success': True,
            'data': {'config': SmsProviderConfigSerializer(config).data},
            'message': 'SMS auth key saved',
            'errors': [],
        },
        status=status.HTTP_200_OK,
    )


@api_view(['POST'])
@permission_classes([IsAuthenticated, IsAdmin])
def sms_config_test_view(request, pk):
    from apps.admin_panel.serializers import SmsTestSerializer
    from apps.notifications.services.dispatch import SmsNotificationService

    config = _get_sms_config(pk)
    if not config:
        return Response(
            {'success': False, 'data': None, 'message': 'SMS profile not found', 'errors': []},
            status=status.HTTP_404_NOT_FOUND,
        )
    if not config.enabled:
        return Response(
            {
                'success': False,
                'data': None,
                'message': 'Enable this SMS profile before sending a test.',
                'errors': [],
            },
            status=status.HTTP_400_BAD_REQUEST,
        )
    if not config.get_auth_key() and config.provider == 'msg91':
        return Response(
            {
                'success': False,
                'data': None,
                'message': 'Set an MSG91 auth key on this profile before testing.',
                'errors': [],
            },
            status=status.HTTP_400_BAD_REQUEST,
        )
    ser = SmsTestSerializer(data=request.data)
    if not ser.is_valid():
        return Response(
            {'success': False, 'data': None, 'message': 'Invalid input', 'errors': ser.errors},
            status=status.HTTP_400_BAD_REQUEST,
        )
    phone = ser.validated_data['phone']
    template_id = (ser.validated_data.get('template_id') or '').strip()
    variables = ser.validated_data.get('variables') or {}
    if not template_id:
        return Response(
            {
                'success': False,
                'data': None,
                'message': 'template_id is required for test SMS',
                'errors': [],
            },
            status=status.HTTP_400_BAD_REQUEST,
        )
    result = SmsNotificationService.send_raw_template(
        phone, template_id, variables, cfg=config
    )
    if result.get('sent'):
        return Response(
            {
                'success': True,
                'data': {'sent': True, 'provider_message_id': result.get('provider_message_id')},
                'message': f'Test SMS sent using profile "{config.name}"',
                'errors': [],
            },
            status=status.HTTP_200_OK,
        )
    return Response(
        {
            'success': False,
            'data': {'sent': False, 'error': result.get('error')},
            'message': result.get('error') or 'Test SMS failed',
            'errors': [],
        },
        status=status.HTTP_400_BAD_REQUEST,
    )


sms_config_view = sms_config_list_view


@api_view(['GET'])
@permission_classes([IsAuthenticated, IsAdmin])
def sms_templates_list_view(request):
    from apps.notifications.catalog import SMS_EVENT_CATALOG
    from apps.notifications.models import SmsNotificationTemplate

    db_rows = {
        t.event_key: t
        for t in SmsNotificationTemplate.objects.filter(is_deleted=False)
    }
    templates = []
    for entry in SMS_EVENT_CATALOG:
        row = db_rows.get(entry['event_key'])
        health = {}
        if row:
            from apps.notifications.services.template_sync import mapping_health

            health = mapping_health(row)
        templates.append(
            {
                'event_key': entry['event_key'],
                'module': entry['module'],
                'label': entry['label'],
                'description': entry.get('description', ''),
                'variable_schema': (row.variable_schema if row else entry.get('variable_schema', []))
                or entry.get('variable_schema', []),
                'is_enabled': bool(row.is_enabled) if row else False,
                'template_id': (row.template_id if row else '') or '',
                'sample_variables': (row.sample_variables if row else entry.get('sample_variables', {})) or {},
                'variable_map': (row.variable_map if row else {}) or {},
                'default_variable_map': entry.get('default_variable_map') or {},
                'mapping_source': (row.mapping_source if row else '') or '',
                'msg91_template_name': (row.msg91_template_name if row else '') or '',
                'msg91_template_body': (row.msg91_template_body if row else '') or '',
                'msg91_detected_vars': list((row.msg91_detected_vars if row else []) or []),
                'msg91_sender_id': (row.msg91_sender_id if row else '') or '',
                'msg91_dlt_id': (row.msg91_dlt_id if row else '') or '',
                'msg91_synced_at': row.msg91_synced_at.isoformat() if row and row.msg91_synced_at else None,
                'mapping_health': health,
            }
        )
    return Response(
        {
            'success': True,
            'data': {'templates': templates},
            'message': 'SMS templates retrieved',
            'errors': [],
        },
        status=status.HTTP_200_OK,
    )


@api_view(['PUT'])
@permission_classes([IsAuthenticated, IsAdmin])
def sms_template_update_view(request, event_key):
    from apps.admin_panel.serializers import SmsTemplateUpdateSerializer
    from apps.notifications.catalog import CATALOG_EVENT_KEYS
    from apps.notifications.models import SmsNotificationTemplate

    if event_key not in CATALOG_EVENT_KEYS:
        return Response(
            {'success': False, 'data': None, 'message': 'Unknown event_key', 'errors': []},
            status=status.HTTP_404_NOT_FOUND,
        )
    try:
        template = SmsNotificationTemplate.objects.get(event_key=event_key, is_deleted=False)
    except SmsNotificationTemplate.DoesNotExist:
        return Response(
            {'success': False, 'data': None, 'message': 'Template not seeded', 'errors': []},
            status=status.HTTP_404_NOT_FOUND,
        )
    ser = SmsTemplateUpdateSerializer(data=request.data)
    if not ser.is_valid():
        return Response(
            {'success': False, 'data': None, 'message': 'Invalid input', 'errors': ser.errors},
            status=status.HTTP_400_BAD_REQUEST,
        )
    val = ser.validated_data
    update_fields = ['updated_at']
    if 'is_enabled' in val:
        template.is_enabled = val['is_enabled']
        update_fields.append('is_enabled')
    if 'template_id' in val:
        template.template_id = (val.get('template_id') or '').strip()
        update_fields.append('template_id')
    if 'sample_variables' in val:
        template.sample_variables = val['sample_variables'] or {}
        update_fields.append('sample_variables')
    if 'variable_map' in val:
        template.variable_map = val['variable_map'] or {}
        update_fields.append('variable_map')
        template.mapping_source = 'manual'
        update_fields.append('mapping_source')
    template.save(update_fields=update_fields)
    from apps.notifications.services.template_sync import mapping_health

    return Response(
        {
            'success': True,
            'data': {
                'template': {
                    'event_key': template.event_key,
                    'module': template.module,
                    'label': template.label,
                    'description': template.description,
                    'is_enabled': template.is_enabled,
                    'template_id': template.template_id,
                    'variable_schema': template.variable_schema,
                    'sample_variables': template.sample_variables,
                    'variable_map': template.variable_map or {},
                    'mapping_source': template.mapping_source or '',
                    'msg91_detected_vars': list(template.msg91_detected_vars or []),
                    'msg91_synced_at': template.msg91_synced_at.isoformat()
                    if template.msg91_synced_at
                    else None,
                    'mapping_health': mapping_health(template),
                }
            },
            'message': 'SMS template updated',
            'errors': [],
        },
        status=status.HTTP_200_OK,
    )


@api_view(['POST'])
@permission_classes([IsAuthenticated, IsAdmin])
def sms_template_fetch_msg91_view(request, event_key):
    """Fetch MSG91 getTemplateVersions for this event's template_id (or body.template_id)."""
    from apps.admin_panel.serializers import SmsTemplateFetchSerializer
    from apps.notifications.catalog import CATALOG_EVENT_KEYS
    from apps.notifications.models import SmsNotificationTemplate
    from apps.notifications.providers.msg91 import Msg91Adapter

    if event_key not in CATALOG_EVENT_KEYS:
        return Response(
            {'success': False, 'data': None, 'message': 'Unknown event_key', 'errors': []},
            status=status.HTTP_404_NOT_FOUND,
        )
    try:
        template = SmsNotificationTemplate.objects.get(event_key=event_key, is_deleted=False)
    except SmsNotificationTemplate.DoesNotExist:
        return Response(
            {'success': False, 'data': None, 'message': 'Template not seeded', 'errors': []},
            status=status.HTTP_404_NOT_FOUND,
        )

    ser = SmsTemplateFetchSerializer(data=request.data or {})
    if not ser.is_valid():
        return Response(
            {'success': False, 'data': None, 'message': 'Invalid input', 'errors': ser.errors},
            status=status.HTTP_400_BAD_REQUEST,
        )

    tid = (ser.validated_data.get('template_id') or template.template_id or '').strip()
    if not tid:
        return Response(
            {
                'success': False,
                'data': None,
                'message': 'Provide template_id to fetch from MSG91',
                'errors': [],
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    config = _get_sms_config()
    if not config or config.provider != 'msg91':
        return Response(
            {
                'success': False,
                'data': None,
                'message': 'Activate an MSG91 SMS profile with auth key first.',
                'errors': [],
            },
            status=status.HTTP_400_BAD_REQUEST,
        )
    auth_key = config.get_auth_key()
    if not auth_key:
        return Response(
            {
                'success': False,
                'data': None,
                'message': 'MSG91 auth key is missing on the active profile.',
                'errors': [],
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    adapter = Msg91Adapter(
        auth_key=auth_key,
        api_base_url=config.api_base_url or 'https://control.msg91.com',
        route=config.route or '',
    )
    result = adapter.get_template_versions(tid)
    if not result.get('success'):
        return Response(
            {
                'success': False,
                'data': {'template_id': tid},
                'message': result.get('error') or 'Failed to fetch MSG91 template',
                'errors': [],
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    # Persist template_id if caller fetched with a new id
    if tid != (template.template_id or '').strip():
        template.template_id = tid
        template.save(update_fields=['template_id', 'updated_at'])

    from apps.notifications.services.template_sync import apply_msg91_primary_to_template, mapping_health

    primary = result.get('primary') or {}
    sync = apply_msg91_primary_to_template(template, primary)

    return Response(
        {
            'success': True,
            'data': {
                'event_key': event_key,
                'template_id': tid,
                'primary': {
                    **(primary if isinstance(primary, dict) else {}),
                    'detected_vars': sync.detected_vars,
                },
                'versions': result.get('versions') or [],
                'variable_schema': template.variable_schema,
                'variable_map': template.variable_map or {},
                'suggested_variable_map': sync.variable_map,
                'mapping_source': template.mapping_source,
                'msg91_synced_at': template.msg91_synced_at.isoformat()
                if template.msg91_synced_at
                else None,
                'unmapped_required': sync.unmapped_required,
                'unused_placeholders': sync.unused_placeholders,
                'mapping_health': mapping_health(template),
            },
            'message': (
                f'Auto-mapped from MSG91 placeholders: {", ".join(sync.detected_vars) or "none"}'
                if sync.detected_vars
                else 'MSG91 template retrieved (no placeholders detected)'
            ),
            'errors': [],
        },
        status=status.HTTP_200_OK,
    )


@api_view(['POST'])
@permission_classes([IsAuthenticated, IsAdmin])
def sms_template_test_view(request, event_key):
    from apps.admin_panel.serializers import SmsTemplateTestSerializer
    from apps.notifications.catalog import CATALOG_EVENT_KEYS
    from apps.notifications.models import SmsNotificationTemplate
    from apps.notifications.services.dispatch import SmsNotificationService
    from apps.notifications.services.variable_map import apply_variable_map

    if event_key not in CATALOG_EVENT_KEYS:
        return Response(
            {'success': False, 'data': None, 'message': 'Unknown event_key', 'errors': []},
            status=status.HTTP_404_NOT_FOUND,
        )
    try:
        template = SmsNotificationTemplate.objects.get(event_key=event_key, is_deleted=False)
    except SmsNotificationTemplate.DoesNotExist:
        return Response(
            {'success': False, 'data': None, 'message': 'Template not seeded', 'errors': []},
            status=status.HTTP_404_NOT_FOUND,
        )
    if not (template.template_id or '').strip():
        return Response(
            {
                'success': False,
                'data': None,
                'message': 'Configure template_id for this event first',
                'errors': [],
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    ser = SmsTemplateTestSerializer(data=request.data)
    if not ser.is_valid():
        return Response(
            {'success': False, 'data': None, 'message': 'Invalid input', 'errors': ser.errors},
            status=status.HTTP_400_BAD_REQUEST,
        )
    phone = ser.validated_data['phone']
    context = ser.validated_data.get('variables') or template.sample_variables or {}
    variables = apply_variable_map(context, template.variable_map or {})
    active_cfg = _get_sms_config()
    if not active_cfg or not active_cfg.enabled:
        return Response(
            {
                'success': False,
                'data': None,
                'message': 'No active enabled SMS profile. Activate a profile first.',
                'errors': [],
            },
            status=status.HTTP_400_BAD_REQUEST,
        )
    result = SmsNotificationService.send_raw_template(
        phone,
        template.template_id,
        variables,
        cfg=active_cfg,
    )
    if result.get('sent'):
        return Response(
            {
                'success': True,
                'data': {
                    'sent': True,
                    'provider_message_id': result.get('provider_message_id'),
                    'mapped_variables': variables,
                },
                'message': f'Test SMS sent for {event_key}',
                'errors': [],
            },
            status=status.HTTP_200_OK,
        )
    return Response(
        {
            'success': False,
            'data': {'sent': False, 'error': result.get('error'), 'mapped_variables': variables},
            'message': result.get('error') or 'Test SMS failed',
            'errors': [],
        },
        status=status.HTTP_400_BAD_REQUEST,
    )


@api_view(['GET'])
@permission_classes([IsAuthenticated, IsAdmin])
def sms_delivery_logs_view(request):
    from apps.admin_panel.serializers import SmsDeliveryLogSerializer
    from apps.notifications.models import SmsDeliveryLog

    qs = SmsDeliveryLog.objects.filter(is_deleted=False).order_by('-created_at')
    event_key = (request.query_params.get('event_key') or '').strip()
    status_filter = (request.query_params.get('status') or '').strip().lower()
    if event_key:
        qs = qs.filter(event_key=event_key)
    if status_filter in ('sent', 'failed', 'skipped'):
        qs = qs.filter(status=status_filter)

    try:
        limit = min(max(int(request.query_params.get('limit') or 50), 1), 200)
    except (TypeError, ValueError):
        limit = 50

    rows = list(qs[:limit])
    return Response(
        {
            'success': True,
            'data': {
                'logs': SmsDeliveryLogSerializer(rows, many=True).data,
                'count': len(rows),
            },
            'message': 'SMS delivery logs retrieved',
            'errors': [],
        },
        status=status.HTTP_200_OK,
    )


def _email_template_payload(entry, row):
    from apps.admin_panel.serializers import EmailNotificationTemplateSerializer

    if row:
        data = EmailNotificationTemplateSerializer(row).data
        data['variable_schema'] = entry.get('variable_schema', row.variable_schema)
        data['description'] = entry.get('description', row.description)
        return data
    return {
        'event_key': entry['event_key'],
        'module': entry['module'],
        'label': entry['label'],
        'description': entry.get('description', ''),
        'variable_schema': entry.get('variable_schema', []),
        'is_enabled': False,
        'subject_template': entry.get('default_subject', ''),
        'body_html_template': entry.get('default_body_html', ''),
        'body_plain_template': entry.get('default_body_plain', ''),
        'sample_variables': entry.get('sample_variables', {}),
    }


@api_view(['GET'])
@permission_classes([IsAuthenticated, IsAdmin])
def email_templates_list_view(request):
    from apps.notifications.email_catalog import EMAIL_EVENT_CATALOG
    from apps.notifications.models import EmailNotificationTemplate

    db_rows = {t.event_key: t for t in EmailNotificationTemplate.objects.filter(is_deleted=False)}
    templates = [_email_template_payload(entry, db_rows.get(entry['event_key'])) for entry in EMAIL_EVENT_CATALOG]
    return Response(
        {
            'success': True,
            'data': {'templates': templates},
            'message': 'Email templates retrieved',
            'errors': [],
        },
        status=status.HTTP_200_OK,
    )


@api_view(['GET', 'PUT'])
@permission_classes([IsAuthenticated, IsAdmin])
def email_template_detail_view(request, event_key):
    from apps.notifications.email_catalog import EMAIL_CATALOG_EVENT_KEYS, EMAIL_EVENT_CATALOG
    from apps.notifications.models import EmailNotificationTemplate

    if event_key not in EMAIL_CATALOG_EVENT_KEYS:
        return Response(
            {'success': False, 'data': None, 'message': 'Unknown event_key', 'errors': []},
            status=status.HTTP_404_NOT_FOUND,
        )
    entry = next((e for e in EMAIL_EVENT_CATALOG if e['event_key'] == event_key), None)
    try:
        template = EmailNotificationTemplate.objects.get(event_key=event_key, is_deleted=False)
    except EmailNotificationTemplate.DoesNotExist:
        return Response(
            {'success': False, 'data': None, 'message': 'Template not seeded', 'errors': []},
            status=status.HTTP_404_NOT_FOUND,
        )

    if request.method == 'GET':
        return Response(
            {
                'success': True,
                'data': {'template': _email_template_payload(entry, template)},
                'message': 'Email template retrieved',
                'errors': [],
            },
            status=status.HTTP_200_OK,
        )

    from apps.admin_panel.serializers import EmailNotificationTemplateSerializer, EmailTemplateUpdateSerializer

    ser = EmailTemplateUpdateSerializer(data=request.data)
    if not ser.is_valid():
        return Response(
            {'success': False, 'data': None, 'message': 'Invalid input', 'errors': ser.errors},
            status=status.HTTP_400_BAD_REQUEST,
        )
    val = ser.validated_data
    update_fields = ['updated_at']
    for field in ('is_enabled', 'subject_template', 'body_html_template', 'body_plain_template', 'sample_variables'):
        if field in val:
            setattr(template, field, val[field])
            update_fields.append(field)
    template.save(update_fields=update_fields)
    return Response(
        {
            'success': True,
            'data': {'template': EmailNotificationTemplateSerializer(template).data},
            'message': 'Email template updated',
            'errors': [],
        },
        status=status.HTTP_200_OK,
    )


@api_view(['POST'])
@permission_classes([IsAuthenticated, IsAdmin])
def email_template_test_view(request, event_key):
    from apps.admin_panel.serializers import EmailTemplateTestSerializer
    from apps.integrations.email_service import EmailDeliveryError, get_active_smtp_config
    from apps.notifications.email_catalog import EMAIL_CATALOG_EVENT_KEYS
    from apps.notifications.models import EmailNotificationTemplate
    from apps.notifications.services.email_dispatch import EmailNotificationService

    if event_key not in EMAIL_CATALOG_EVENT_KEYS:
        return Response(
            {'success': False, 'data': None, 'message': 'Unknown event_key', 'errors': []},
            status=status.HTTP_404_NOT_FOUND,
        )
    if not get_active_smtp_config():
        return Response(
            {
                'success': False,
                'data': None,
                'message': 'No active enabled SMTP profile. Configure SMTP first.',
                'errors': [],
            },
            status=status.HTTP_400_BAD_REQUEST,
        )
    try:
        template = EmailNotificationTemplate.objects.get(event_key=event_key, is_deleted=False)
    except EmailNotificationTemplate.DoesNotExist:
        return Response(
            {'success': False, 'data': None, 'message': 'Template not seeded', 'errors': []},
            status=status.HTTP_404_NOT_FOUND,
        )
    ser = EmailTemplateTestSerializer(data=request.data)
    if not ser.is_valid():
        return Response(
            {'success': False, 'data': None, 'message': 'Invalid input', 'errors': ser.errors},
            status=status.HTTP_400_BAD_REQUEST,
        )
    to_email = (ser.validated_data.get('to_email') or '').strip() or getattr(request.user, 'email', '') or ''
    if not to_email:
        return Response(
            {
                'success': False,
                'data': None,
                'message': 'Provide to_email or ensure your admin account has an email.',
                'errors': [],
            },
            status=status.HTTP_400_BAD_REQUEST,
        )
    from apps.notifications.email_catalog import EMAIL_EVENT_CATALOG
    import uuid

    catalog_entry = next((e for e in EMAIL_EVENT_CATALOG if e['event_key'] == event_key), None)
    catalog_samples = (catalog_entry or {}).get('sample_variables') or {}
    db_samples = template.sample_variables if isinstance(template.sample_variables, dict) else {}
    request_vars = ser.validated_data.get('variables') if isinstance(ser.validated_data.get('variables'), dict) else {}
    variables = {**catalog_samples, **db_samples, **request_vars}

    try:
        result = EmailNotificationService.dispatch(
            event_key,
            to_email,
            variables,
            idempotency_key=f'email-test:{event_key}:{uuid.uuid4().hex}',
            raise_on_failure=True,
            for_test=True,
        )
    except EmailDeliveryError as exc:
        return Response(
            {'success': False, 'data': None, 'message': str(exc), 'errors': []},
            status=status.HTTP_400_BAD_REQUEST,
        )
    if result.get('status') == 'sent':
        return Response(
            {
                'success': True,
                'data': {'sent': True, 'to_email': to_email},
                'message': f'Test email sent for {event_key}',
                'errors': [],
            },
            status=status.HTTP_200_OK,
        )
    skip = result.get('skip_reason') or ''
    friendly = {
        'event_disabled': 'Enable the template or use test send (should not occur).',
        'empty_template': 'Add subject and HTML body before testing.',
        'invalid_context': 'Missing required template variables. Check sample data in the editor.',
        'smtp_disabled': 'No active SMTP profile.',
        'template_not_seeded': 'Run seed_email_event_templates on the server.',
    }.get(skip, skip)
    return Response(
        {
            'success': False,
            'data': result,
            'message': result.get('error') or friendly or 'Test email failed',
            'errors': [],
        },
        status=status.HTTP_400_BAD_REQUEST,
    )


@api_view(['GET', 'PATCH'])
@permission_classes([IsAuthenticated, IsAdmin])
def maintenance_config_view(request):
    """
    Admin maintenance mode configuration.
    GET/PATCH /api/admin/maintenance/
    """
    from apps.core.maintenance_mode import get_status, update_config
    from apps.core.serializers import SystemMaintenanceUpdateSerializer

    if request.method == 'GET':
        return Response(
            {
                'success': True,
                'data': {'maintenance': get_status(include_internal=True)},
                'message': 'OK',
                'errors': [],
            },
            status=status.HTTP_200_OK,
        )

    ser = SystemMaintenanceUpdateSerializer(data=request.data, partial=True)
    if not ser.is_valid():
        return Response(
            {
                'success': False,
                'data': None,
                'message': 'Invalid input',
                'errors': ser.errors,
            },
            status=status.HTTP_400_BAD_REQUEST,
        )
    maintenance = update_config(changed_by=request.user, patch=ser.validated_data)
    return Response(
        {
            'success': True,
            'data': {'maintenance': maintenance},
            'message': 'Maintenance settings updated',
            'errors': [],
        },
        status=status.HTTP_200_OK,
    )
