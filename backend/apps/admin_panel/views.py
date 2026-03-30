"""
Admin panel views for the mPayhub platform.
"""
from django.db.models import Q
from django.utils.dateparse import parse_date
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from apps.admin_panel.models import Announcement, PaymentGateway, PayoutGateway
from apps.admin_panel.serializers import (
    AnnouncementSerializer,
    PaymentGatewaySerializer,
    PayoutGatewaySerializer
)
from apps.core.permissions import IsAdmin


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
    queryset = PaymentGateway.objects.all()
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
