"""
Admin API for session security settings, audit logs, and multi-session exceptions.
"""
from django.db.models import Q
from rest_framework import serializers, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.authentication.models import User, UserSession
from apps.core.permissions import IsAdmin
from apps.session_security.constants import IDLE_TIMEOUT_MAX, IDLE_TIMEOUT_MIN
from apps.session_security.models import UserLoginAuditLog
from apps.session_security.services.audit_query import (
    build_audit_xlsx,
    export_limit_default,
    filter_audit_queryset,
    paginate_queryset,
    serialize_audit_row,
)
from apps.session_security.services.sessions import get_session_lifecycle
from apps.session_security.services.settings import (
    get_settings,
    settings_to_dict,
    update_settings,
)


class SessionSecuritySettingsSerializer(serializers.Serializer):
    ip_location_enforcement_enabled = serializers.BooleanField(required=False)
    audit_logging_enabled = serializers.BooleanField(required=False)
    single_session_enforcement_enabled = serializers.BooleanField(required=False)
    idle_timeout_minutes = serializers.IntegerField(
        required=False,
        min_value=IDLE_TIMEOUT_MIN,
        max_value=IDLE_TIMEOUT_MAX,
    )


class ConcurrentExceptionSerializer(serializers.Serializer):
    user_id = serializers.IntegerField()
    allow_concurrent_sessions = serializers.BooleanField()


def _user_brief(u: User) -> dict:
    return {
        'id': u.id,
        'display_code': getattr(u, 'display_code', None) or getattr(u, 'user_id', None),
        'member_id': getattr(u, 'member_id', None),
        'phone': u.phone,
        'email': u.email,
        'full_name': u.get_full_name() or '',
        'role': u.role,
        'allow_concurrent_sessions': bool(getattr(u, 'allow_concurrent_sessions', False)),
    }


def _audit_filters_from_request(request):
    return {
        'user_id': request.query_params.get('user_id'),
        'event_type': request.query_params.get('event_type') or '',
        'category': request.query_params.get('category') or 'all',
        'date_from': request.query_params.get('date_from'),
        'date_to': request.query_params.get('date_to'),
    }


@api_view(['GET', 'PATCH'])
@permission_classes([IsAuthenticated, IsAdmin])
def settings_view(request):
    """
    GET/PATCH /api/admin/session-security/settings/
    """
    if request.method == 'GET':
        return Response(
            {
                'success': True,
                'data': {'settings': settings_to_dict()},
                'message': 'OK',
                'errors': [],
            }
        )

    ser = SessionSecuritySettingsSerializer(data=request.data)
    if not ser.is_valid():
        return Response(
            {
                'success': False,
                'data': None,
                'message': 'Invalid settings payload',
                'errors': ser.errors,
            },
            status=status.HTTP_400_BAD_REQUEST,
        )
    config = update_settings(changed_by=request.user, **ser.validated_data)
    return Response(
        {
            'success': True,
            'data': {'settings': settings_to_dict(config)},
            'message': 'Session security settings updated',
            'errors': [],
        }
    )


@api_view(['GET'])
@permission_classes([IsAuthenticated, IsAdmin])
def audit_logs_view(request):
    """
    GET /api/admin/session-security/audit-logs/
    ?user_id=&event_type=&category=&date_from=&date_to=&page=&page_size=

    Admin role only. Non-admins must use /api/auth/my-activity/.
    """
    # Defense in depth beyond IsAdmin
    if getattr(request.user, 'role', None) != 'Admin':
        return Response(
            {
                'success': False,
                'data': None,
                'message': 'Only Admin can view all-account audit logs.',
                'errors': ['FORBIDDEN'],
            },
            status=status.HTTP_403_FORBIDDEN,
        )
    qs = filter_audit_queryset(**_audit_filters_from_request(request))
    try:
        page = int(request.query_params.get('page', 1))
    except (TypeError, ValueError):
        page = 1
    try:
        page_size = int(request.query_params.get('page_size', 25))
    except (TypeError, ValueError):
        page_size = 25

    rows, pagination = paginate_queryset(qs, page=page, page_size=page_size)
    results = [serialize_audit_row(row, user_brief_fn=_user_brief) for row in rows]
    return Response(
        {
            'success': True,
            'data': {'results': results, 'pagination': pagination},
            'message': 'OK',
            'errors': [],
        }
    )


@api_view(['GET'])
@permission_classes([IsAuthenticated, IsAdmin])
def audit_logs_export_view(request):
    """GET /api/admin/session-security/audit-logs/export/?... → .xlsx"""
    if getattr(request.user, 'role', None) != 'Admin':
        return Response(
            {
                'success': False,
                'data': None,
                'message': 'Only Admin can export all-account audit logs.',
                'errors': ['FORBIDDEN'],
            },
            status=status.HTTP_403_FORBIDDEN,
        )
    qs = filter_audit_queryset(**_audit_filters_from_request(request))
    rows = list(qs.select_related('user')[: export_limit_default()])
    user_id = request.query_params.get('user_id') or 'all'
    filename = f'user-activity-{user_id}.xlsx'
    return build_audit_xlsx(rows, filename=filename)


@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated, IsAdmin])
def concurrent_exceptions_view(request):
    """
    GET  /api/admin/session-security/concurrent-exceptions/
    POST /api/admin/session-security/concurrent-exceptions/  {user_id, allow_concurrent_sessions}
    """
    if request.method == 'GET':
        q = (request.query_params.get('q') or '').strip()
        qs = User.objects.filter(allow_concurrent_sessions=True).order_by('id')
        if q:
            qs = qs.filter(
                Q(phone__icontains=q)
                | Q(email__icontains=q)
                | Q(display_code__icontains=q)
                | Q(member_id__icontains=q)
                | Q(user_id__icontains=q)
                | Q(first_name__icontains=q)
                | Q(last_name__icontains=q)
            )
        return Response(
            {
                'success': True,
                'data': {'users': [_user_brief(u) for u in qs[:100]]},
                'message': 'OK',
                'errors': [],
            }
        )

    ser = ConcurrentExceptionSerializer(data=request.data)
    if not ser.is_valid():
        return Response(
            {
                'success': False,
                'data': None,
                'message': 'Invalid payload',
                'errors': ser.errors,
            },
            status=status.HTTP_400_BAD_REQUEST,
        )
    try:
        user = User.objects.get(pk=ser.validated_data['user_id'])
    except User.DoesNotExist:
        return Response(
            {
                'success': False,
                'data': None,
                'message': 'User not found',
                'errors': ['not_found'],
            },
            status=status.HTTP_404_NOT_FOUND,
        )
    user.allow_concurrent_sessions = bool(ser.validated_data['allow_concurrent_sessions'])
    user.save(update_fields=['allow_concurrent_sessions', 'updated_at'])
    return Response(
        {
            'success': True,
            'data': {'user': _user_brief(user)},
            'message': 'Concurrent session exception updated',
            'errors': [],
        }
    )


@api_view(['GET'])
@permission_classes([IsAuthenticated, IsAdmin])
def search_users_for_exception_view(request):
    """GET /api/admin/session-security/users/search/?q="""
    q = (request.query_params.get('q') or '').strip()
    if len(q) < 2:
        return Response(
            {
                'success': True,
                'data': {'users': []},
                'message': 'OK',
                'errors': [],
            }
        )
    qs = User.objects.filter(
        Q(phone__icontains=q)
        | Q(email__icontains=q)
        | Q(display_code__icontains=q)
        | Q(member_id__icontains=q)
        | Q(user_id__icontains=q)
        | Q(first_name__icontains=q)
        | Q(last_name__icontains=q)
    ).order_by('id')[:20]
    return Response(
        {
            'success': True,
            'data': {'users': [_user_brief(u) for u in qs]},
            'message': 'OK',
            'errors': [],
        }
    )


@api_view(['POST'])
@permission_classes([IsAuthenticated, IsAdmin])
def terminate_session_view(request, session_id: int):
    """POST /api/admin/session-security/sessions/<id>/terminate/"""
    try:
        session = UserSession.objects.select_related('user').get(pk=session_id)
    except UserSession.DoesNotExist:
        return Response(
            {
                'success': False,
                'data': None,
                'message': 'Session not found',
                'errors': ['not_found'],
            },
            status=status.HTTP_404_NOT_FOUND,
        )
    get_session_lifecycle().admin_terminate(session, admin_user=request.user)
    return Response(
        {
            'success': True,
            'data': {'session_id': session.id, 'is_active': False},
            'message': 'Session terminated',
            'errors': [],
        }
    )


@api_view(['GET'])
@permission_classes([IsAuthenticated, IsAdmin])
def public_idle_policy_view(request):
    s = get_settings()
    return Response(
        {
            'success': True,
            'data': {
                'idle_timeout_minutes': int(s.idle_timeout_minutes),
            },
            'message': 'OK',
            'errors': [],
        }
    )
