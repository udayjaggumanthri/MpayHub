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
        .prefetch_related('payout_slabs')
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


def _get_smtp_config():
    return (
        SmtpConfig.objects.filter(is_deleted=False, is_active=True).order_by('-updated_at').first()
        or SmtpConfig.objects.filter(is_deleted=False).order_by('-updated_at').first()
    )


@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated, IsAdmin])
def smtp_config_view(request):
    """GET/POST admin SMTP configuration for transactional email."""
    config = _get_smtp_config()
    if request.method == 'GET':
        return Response(
            {
                'success': True,
                'data': {'config': SmtpConfigSerializer(config).data if config else None},
                'message': 'SMTP config retrieved successfully',
                'errors': [],
            },
            status=status.HTTP_200_OK,
        )

    data = dict(request.data)
    if config:
        ser = SmtpConfigSerializer(config, data=data, partial=True)
    else:
        ser = SmtpConfigSerializer(data=data)
    if not ser.is_valid():
        return Response(
            {'success': False, 'data': None, 'message': 'Invalid config', 'errors': ser.errors},
            status=status.HTTP_400_BAD_REQUEST,
        )
    cfg = ser.save()
    if cfg.is_active:
        SmtpConfig.objects.exclude(pk=cfg.pk).update(is_active=False)
    return Response(
        {
            'success': True,
            'data': {'config': SmtpConfigSerializer(cfg).data},
            'message': 'SMTP config saved',
            'errors': [],
        },
        status=status.HTTP_200_OK,
    )


@api_view(['POST'])
@permission_classes([IsAuthenticated, IsAdmin])
def smtp_config_secrets_view(request):
    """Update SMTP password only (encrypted at rest)."""
    config = _get_smtp_config()
    if not config:
        return Response(
            {'success': False, 'data': None, 'message': 'Create SMTP config first', 'errors': []},
            status=status.HTTP_400_BAD_REQUEST,
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
def smtp_config_test_view(request):
    """Send a test email using the active SMTP config."""
    from apps.integrations.email_service import EmailDeliveryError, send_email

    config = _get_smtp_config()
    if not config or not config.enabled:
        return Response(
            {
                'success': False,
                'data': None,
                'message': 'SMTP is not enabled. Save and enable SMTP config first.',
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
            subject='mPayhub SMTP test',
            body_plain='This is a test message from mPayhub SMTP settings.',
            body_html='<p>This is a <strong>test message</strong> from mPayhub SMTP settings.</p>',
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
            'data': {'sent_to': to_email},
            'message': (
                f'Test email accepted by SMTP server for {to_email}. '
                'Check inbox and spam; Zoho may take 1–2 minutes.'
            ),
            'errors': [],
        },
        status=status.HTTP_200_OK,
    )
