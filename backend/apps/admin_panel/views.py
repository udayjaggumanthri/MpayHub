"""
Admin panel views for the mPayhub platform.
"""
from rest_framework import status, viewsets
from rest_framework.decorators import action
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
    ViewSet for announcement management (Admin only).
    """
    queryset = Announcement.objects.all()
    serializer_class = AnnouncementSerializer
    permission_classes = [IsAuthenticated, IsAdmin]
    
    def get_queryset(self):
        """Get active announcements for non-admin users."""
        if self.request.user.role == 'Admin':
            return Announcement.objects.all()
        else:
            # Return announcements visible to user's role
            return Announcement.objects.filter(
                is_active=True,
                target_roles__contains=[self.request.user.role]
            )


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
