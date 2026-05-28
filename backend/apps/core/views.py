"""Core system views."""
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.core.maintenance_mode import get_status


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
