"""
Admin API for wallet adjustments: create, list, export, user lookup.
"""
from __future__ import annotations

from datetime import datetime

from django.db.models import Q
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.authentication.models import User
from apps.core.exceptions import InsufficientBalance
from apps.core.permissions import IsAdmin
from apps.transactions.agent_snapshot import display_name_for_user
from apps.wallets.models import Wallet
from apps.wallet_adjustments.exceptions import WalletAdjustmentError
from apps.wallet_adjustments.export import build_adjustments_xlsx
from apps.wallet_adjustments.serializers import WalletAdjustmentCreateSerializer
from apps.wallet_adjustments.services import (
    apply_wallet_adjustment,
    filter_adjustments,
    serialize_adjustment,
)


def _ok(data=None, message='OK', http_status=status.HTTP_200_OK):
    return Response(
        {'success': True, 'data': data, 'message': message, 'errors': []},
        status=http_status,
    )


def _fail(message, errors=None, *, code='WALLET_ADJUSTMENT_ERROR', http_status=status.HTTP_400_BAD_REQUEST):
    return Response(
        {
            'success': False,
            'data': None,
            'message': message,
            'errors': errors or [message],
            'error': {'code': code, 'retryable': False},
        },
        status=http_status,
    )


def _parse_date(raw):
    if not raw:
        return None
    raw = str(raw).strip()
    for fmt in ('%Y-%m-%d', '%d-%m-%Y', '%Y/%m/%d'):
        try:
            return datetime.strptime(raw, fmt).date()
        except ValueError:
            continue
    return None


def _list_filter_kwargs(request):
    user_id = request.query_params.get('user_id')
    try:
        user_id_int = int(user_id) if user_id not in (None, '') else None
    except (TypeError, ValueError):
        user_id_int = None
    return {
        'q': request.query_params.get('q') or '',
        'wallet_type': request.query_params.get('wallet_type') or '',
        'adjustment_type': request.query_params.get('adjustment_type') or '',
        'date_from': _parse_date(request.query_params.get('date_from')),
        'date_to': _parse_date(request.query_params.get('date_to')),
        'status': request.query_params.get('status') or '',
        'reference': request.query_params.get('reference') or '',
        'user_id': user_id_int,
    }


def _user_balances(user: User) -> dict:
    out = {}
    for wt in ('main', 'bbps'):
        w = Wallet.objects.filter(user=user, wallet_type=wt, is_deleted=False).first()
        out[wt] = str(w.balance) if w else '0.0000'
    return out


def _user_lookup_item(user: User) -> dict:
    return {
        'id': user.id,
        'user_id': user.user_id or '',
        'display_code': getattr(user, 'display_code', None) or '',
        'member_id': getattr(user, 'member_id', None) or '',
        'phone': user.phone or '',
        'email': user.email or '',
        'name': display_name_for_user(user),
        'role': user.role or '',
        'balances': _user_balances(user),
    }


@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated, IsAdmin])
def adjustments_collection_view(request):
    """
    GET  /api/admin/wallet-adjustments/ — paginated, filterable list.
    POST /api/admin/wallet-adjustments/ — execute a manual credit/debit.
    """
    if request.method == 'GET':
        qs = filter_adjustments(**_list_filter_kwargs(request))
        try:
            page = max(1, int(request.query_params.get('page') or 1))
        except (TypeError, ValueError):
            page = 1
        try:
            page_size = min(200, max(1, int(request.query_params.get('page_size') or 50)))
        except (TypeError, ValueError):
            page_size = 50

        total = qs.count()
        start = (page - 1) * page_size
        end = start + page_size
        rows = [serialize_adjustment(r) for r in qs[start:end]]
        return _ok(
            {
                'results': rows,
                'pagination': {
                    'page': page,
                    'page_size': page_size,
                    'total': total,
                    'total_pages': (total + page_size - 1) // page_size if page_size else 1,
                },
            }
        )

    ser = WalletAdjustmentCreateSerializer(data=request.data)
    if not ser.is_valid():
        errs = []
        for field, messages in ser.errors.items():
            for msg in messages:
                errs.append(f'{field}: {msg}')
        return _fail(errs[0] if errs else 'Validation failed', errs, code='VALIDATION_ERROR')

    data = ser.validated_data
    try:
        target = User.objects.get(pk=data['user_id'])
    except User.DoesNotExist:
        return _fail('Target user not found.', code='USER_NOT_FOUND', http_status=status.HTTP_404_NOT_FOUND)

    try:
        adj = apply_wallet_adjustment(
            admin_user=request.user,
            target_user=target,
            wallet_type=data['wallet_type'],
            adjustment_type=data['adjustment_type'],
            amount=data['amount'],
            reference_number=data['reference_number'],
            reason_category=data['reason_category'],
            remarks=data['remarks'],
        )
    except WalletAdjustmentError as exc:
        return _fail(str(exc), code=getattr(exc, 'code', 'WALLET_ADJUSTMENT_INVALID'))
    except InsufficientBalance as exc:
        return _fail(str(exc) or 'Insufficient wallet balance', code='INSUFFICIENT_BALANCE')
    except Exception as exc:
        return _fail(
            'Adjustment could not be completed. Please try again or contact support.',
            errors=[str(exc)],
            code='WALLET_ADJUSTMENT_FAILED',
            http_status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )

    return _ok(
        {
            'adjustment': serialize_adjustment(adj),
            'balances': _user_balances(target),
        },
        message=f'{adj.adjustment_type} of ₹{adj.amount} applied successfully ({adj.adjustment_id}).',
        http_status=status.HTTP_201_CREATED,
    )


@api_view(['GET'])
@permission_classes([IsAuthenticated, IsAdmin])
def export_adjustments_view(request):
    """GET /api/admin/wallet-adjustments/export.xlsx — Excel download of filtered report."""
    qs = filter_adjustments(**_list_filter_kwargs(request))
    limit = 5000
    rows = list(qs[:limit])
    stamp = datetime.utcnow().strftime('%Y%m%d')
    return build_adjustments_xlsx(rows, filename=f'wallet-adjustments-{stamp}.xlsx')


@api_view(['GET'])
@permission_classes([IsAuthenticated, IsAdmin])
def user_lookup_view(request):
    """GET /api/admin/wallet-adjustments/user-lookup/?q= — typeahead with balances."""
    q = (request.query_params.get('q') or '').strip()
    if len(q) < 2:
        return _ok({'users': []})

    qs = User.objects.filter(
        Q(phone__icontains=q)
        | Q(email__icontains=q)
        | Q(display_code__icontains=q)
        | Q(member_id__icontains=q)
        | Q(user_id__icontains=q)
        | Q(first_name__icontains=q)
        | Q(last_name__icontains=q)
    ).order_by('id')[:20]

    return _ok({'users': [_user_lookup_item(u) for u in qs]})
