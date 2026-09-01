"""Core system views."""
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response

from apps.core.appearance import get_status as get_appearance_status
from apps.core.maintenance_mode import get_status


@api_view(['GET'])
@permission_classes([AllowAny])
def health_view(request):
    """Lightweight liveness probe for monitoring and load balancers."""
    return Response({'status': 'ok', 'service': 'mpayhub-api'}, status=status.HTTP_200_OK)


@api_view(['GET'])
@permission_classes([AllowAny])
def appearance_status_view(request):
    """
    Public branding and theme settings for login and app bootstrap.
    GET /api/system/appearance/
    """
    return Response(
        {
            'success': True,
            'data': {'appearance': get_appearance_status(request=request)},
            'message': 'OK',
            'errors': [],
        },
        status=status.HTTP_200_OK,
    )


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def maintenance_status_view(request):
    """
    Read-only maintenance flags for authenticated users (no internal reason).
    GET /api/system/maintenance-status/
    """
    return Response(
        {
            'success': True,
            'data': {'maintenance': get_status(include_internal=False)},
            'message': 'OK',
            'errors': [],
        },
        status=status.HTTP_200_OK,
    )
