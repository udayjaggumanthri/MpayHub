"""
Read-only network wallet portfolio for Admin display.

Sums channel users' main wallet balances (Distributed Balance).
Excludes Admin / Super Admin login accounts — they are not agent wallets.
Never writes or creates wallet rows.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Iterable

from django.db.models import Count, Sum
from django.db.models.functions import Coalesce

from apps.core.roles import OPERATOR_ROLES
from apps.wallets.models import Wallet

# Post-consolidation: only main holds live money.
NETWORK_WALLET_TYPES = ('main',)


def sum_network_wallet_balances(
    *,
    wallet_types: Iterable[str] = NETWORK_WALLET_TYPES,
) -> dict[str, Decimal]:
    """
    Return {wallet_type: total_balance} for all non-operator (channel) users.

    Missing types are returned as Decimal('0').
    """
    types = tuple(dict.fromkeys(str(t).strip().lower() for t in wallet_types if t))
    if not types:
        return {}

    zeros = {t: Decimal('0') for t in types}
    rows = (
        Wallet.objects.filter(wallet_type__in=types, is_archived=False)
        .exclude(user__role__in=list(OPERATOR_ROLES))
        .values('wallet_type')
        .annotate(total=Coalesce(Sum('balance'), Decimal('0')))
    )
    for row in rows:
        wt = row['wallet_type']
        if wt in zeros:
            zeros[wt] = Decimal(str(row['total'] or 0))
    return zeros


def network_wallet_user_counts(
    *,
    wallet_types: Iterable[str] = NETWORK_WALLET_TYPES,
) -> dict[str, int]:
    """Distinct channel users that have a wallet row per type."""
    types = tuple(dict.fromkeys(str(t).strip().lower() for t in wallet_types if t))
    if not types:
        return {}
    counts = {t: 0 for t in types}
    rows = (
        Wallet.objects.filter(wallet_type__in=types, is_archived=False)
        .exclude(user__role__in=list(OPERATOR_ROLES))
        .values('wallet_type')
        .annotate(n=Count('user_id', distinct=True))
    )
    for row in rows:
        wt = row['wallet_type']
        if wt in counts:
            counts[wt] = int(row['n'] or 0)
    return counts


def distributed_balance_snapshot() -> dict:
    """Admin Distributed Balance card payload."""
    totals = sum_network_wallet_balances(wallet_types=('main',))
    counts = network_wallet_user_counts(wallet_types=('main',))
    return {
        'balance': totals.get('main', Decimal('0')),
        'network_user_count': int(counts.get('main', 0)),
        'source': 'network_total',
        'wallet_type': 'distributed',
    }


CHANNEL_FILTER_ROLES: tuple[str, ...] = (
    'Super Distributor',
    'Master Distributor',
    'Distributor',
    'Retailer',
)

# Platform login roles — share one treasury Main wallet (not part of Distributed sum).
OPERATOR_FILTER_ROLES: tuple[str, ...] = (
    'Super Admin',
    'Admin',
)

# Roles that may manage a channel downline (Network button). Never Admin / Super Admin.
NETWORK_CAPABLE_ROLES: frozenset[str] = frozenset(
    {
        'Super Distributor',
        'Master Distributor',
        'Distributor',
    }
)


def _money_str(value) -> str:
    try:
        return f'{Decimal(str(value or 0)):.4f}'
    except Exception:
        return '0.0000'


def _display_name(user) -> str:
    name = (getattr(user, 'get_full_name', lambda: '')() or '').strip()
    if name:
        return name
    profile = getattr(user, 'profile', None)
    if profile:
        first = (getattr(profile, 'first_name', None) or '').strip()
        last = (getattr(profile, 'last_name', None) or '').strip()
        combined = f'{first} {last}'.strip()
        if combined:
            return combined
    return (getattr(user, 'email', None) or getattr(user, 'phone', None) or str(user.pk))


def _filter_roles_for_viewer(viewer=None, *, network_view: bool = False) -> list[str]:
    """Role chips: channel roles always; Super Admin only for Super Admin viewers; never in network view."""
    from apps.core.roles import is_super_admin

    if network_view:
        return list(CHANNEL_FILTER_ROLES)
    roles = list(CHANNEL_FILTER_ROLES)
    # Platform logins: Admin chip for all operators; Super Admin only for Super Admin.
    if is_super_admin(viewer):
        roles = list(OPERATOR_FILTER_ROLES) + roles
    else:
        roles = ['Admin'] + roles
    return roles


def _treasury_balance() -> Decimal:
    from apps.fund_management.platform_settlement import get_platform_treasury_user

    treasury = get_platform_treasury_user()
    if not treasury:
        return Decimal('0')
    w = Wallet.objects.filter(user=treasury, wallet_type='main', is_archived=False).first()
    return Decimal(str(w.balance or 0)) if w else Decimal('0')


def _user_ledger_row(
    user,
    *,
    balance: Decimal,
    has_network: bool = False,
    shared_wallet: bool = False,
) -> dict:
    from apps.users.identity import public_display_code

    return {
        'id': user.pk,
        'user_id': public_display_code(user),
        'member_id': getattr(user, 'member_id', None) or '',
        'name': _display_name(user),
        'role': getattr(user, 'role', '') or '',
        'phone': getattr(user, 'phone', None) or '',
        'email': getattr(user, 'email', None) or '',
        'is_active': bool(getattr(user, 'is_active', True)),
        'main_balance': _money_str(balance),
        'has_network': bool(has_network) and not shared_wallet,
        'shared_wallet': bool(shared_wallet),
        'profile_path': f'/user-management/users/{user.pk}',
    }


def list_distributed_ledger(
    *,
    viewer=None,
    role: str | None = None,
    search: str | None = None,
    page: int = 1,
    page_size: int = 25,
    include_operators: bool = False,
) -> dict:
    """
    Paginated Main balances for Distributed Balance.

    Channel roles use each user's Main wallet.
    Admin / Super Admin logins share the platform treasury balance (never Network).
    Admin viewers never see Super Admin rows.
    """
    from django.db.models import Q, OuterRef, Subquery, DecimalField, Value
    from django.db.models.functions import Coalesce
    from apps.authentication.models import User
    from apps.core.roles import OPERATOR_ROLES, is_admin, is_super_admin
    from apps.users.models import UserHierarchy

    page = max(1, int(page or 1))
    page_size = max(1, min(100, int(page_size or 25)))

    role_filter = (role or '').strip()
    role_norm = role_filter.lower()
    operator_role_requested = role_norm in ('admin', 'super admin')
    hide_super_admin = bool(viewer) and is_admin(viewer) and not is_super_admin(viewer)

    # Admin viewers cannot open Super Admin filter.
    if hide_super_admin and role_norm == 'super admin':
        snap = distributed_balance_snapshot()
        return {
            'users': [],
            'total': 0,
            'page': page,
            'page_size': page_size,
            'summary': {
                'filtered_balance': '0.0000',
                'filtered_count': 0,
                'network_balance': _money_str(snap['balance']),
                'network_user_count': snap['network_user_count'],
                'by_role': {},
                'shared_wallet': False,
                'empty_reason': 'Super Admin accounts are not visible to Admin logins.',
            },
            'roles': _filter_roles_for_viewer(viewer, network_view=False),
            'network_capable_roles': sorted(NETWORK_CAPABLE_ROLES),
        }

    qs = User.objects.all().select_related('profile')

    if operator_role_requested:
        qs = qs.filter(role__iexact=role_filter)
        if hide_super_admin:
            qs = qs.exclude(role__iexact='Super Admin')
    elif role_filter:
        qs = qs.filter(role__iexact=role_filter)
    elif include_operators:
        if hide_super_admin:
            qs = qs.exclude(role__iexact='Super Admin')
    else:
        qs = qs.exclude(role__in=list(OPERATOR_ROLES))

    q = (search or '').strip()
    if q:
        qs = qs.filter(
            Q(phone__icontains=q)
            | Q(email__icontains=q)
            | Q(user_id__icontains=q)
            | Q(display_code__icontains=q)
            | Q(member_id__icontains=q)
            | Q(first_name__icontains=q)
            | Q(last_name__icontains=q)
            | Q(profile__first_name__icontains=q)
            | Q(profile__last_name__icontains=q)
        )

    treasury_bal = _treasury_balance()
    shared_mode = operator_role_requested

    if shared_mode:
        # Operator logins: list accounts but always show shared treasury balance.
        qs = qs.order_by('id')
        total = qs.count()
        start = (page - 1) * page_size
        page_rows = list(qs[start:start + page_size])
        users = [
            _user_ledger_row(u, balance=treasury_bal, has_network=False, shared_wallet=True)
            for u in page_rows
        ]
        by_role = {
            role_filter: {
                'count': total,
                'balance': _money_str(treasury_bal),
            }
        }
        filtered_balance = treasury_bal
    else:
        bal_sq = (
            Wallet.objects.filter(
                user_id=OuterRef('pk'),
                wallet_type='main',
                is_archived=False,
            )
            .values('balance')[:1]
        )
        qs = qs.annotate(
            main_balance=Coalesce(
                Subquery(bal_sq, output_field=DecimalField(max_digits=18, decimal_places=4)),
                Value(Decimal('0'), output_field=DecimalField(max_digits=18, decimal_places=4)),
            )
        ).order_by('-main_balance', 'id')

        total = qs.count()
        filtered_balance = qs.aggregate(s=Coalesce(Sum('main_balance'), Decimal('0')))['s'] or Decimal('0')

        by_role = {}
        for row in qs.values('role').annotate(
            count=Count('id'),
            balance=Coalesce(Sum('main_balance'), Decimal('0')),
        ):
            key = row['role'] or 'Unknown'
            by_role[key] = {
                'count': int(row['count'] or 0),
                'balance': _money_str(row['balance']),
            }

        start = (page - 1) * page_size
        page_rows = list(qs[start:start + page_size])
        page_ids = [u.pk for u in page_rows]

        parent_ids_with_kids = set()
        if page_ids:
            parent_ids_with_kids = set(
                UserHierarchy.objects.filter(parent_user_id__in=page_ids)
                .values_list('parent_user_id', flat=True)
                .distinct()
            )

        users = [
            _user_ledger_row(
                u,
                balance=getattr(u, 'main_balance', Decimal('0')) or Decimal('0'),
                has_network=(u.pk in parent_ids_with_kids) and (u.role in NETWORK_CAPABLE_ROLES),
                shared_wallet=False,
            )
            for u in page_rows
        ]

    snap = distributed_balance_snapshot()
    empty_reason = ''
    if total == 0 and role_filter:
        empty_reason = f'No {role_filter} users match this filter.'

    return {
        'users': users,
        'total': total,
        'page': page,
        'page_size': page_size,
        'summary': {
            'filtered_balance': _money_str(filtered_balance),
            'filtered_count': total,
            'network_balance': _money_str(snap['balance']),
            'network_user_count': snap['network_user_count'],
            'by_role': by_role,
            'shared_wallet': shared_mode,
            'treasury_balance': _money_str(treasury_bal) if shared_mode else None,
            'empty_reason': empty_reason,
        },
        'roles': _filter_roles_for_viewer(viewer, network_view=False),
        'network_capable_roles': sorted(NETWORK_CAPABLE_ROLES),
    }


def list_user_network_ledger(
    *,
    manager_id: int,
    viewer=None,
    role: str | None = None,
    search: str | None = None,
    page: int = 1,
    page_size: int = 25,
    direct_only: bool = False,
) -> dict | None:
    """
    Main balances for channel users under ``manager_id``.

    Operator roles are never listed in a downline network. Role chips are only
    channel roles that exist under this manager (plus All).
    """
    from django.db.models import Q, OuterRef, Subquery, DecimalField, Value
    from django.db.models.functions import Coalesce
    from apps.authentication.models import User
    from apps.core.roles import OPERATOR_ROLES
    from apps.users.models import UserHierarchy

    manager = (
        User.objects.filter(pk=manager_id)
        .select_related('profile')
        .first()
    )
    if not manager:
        return None

    # Operators do not have a channel "network" in this ledger UI.
    mgr_role = (getattr(manager, 'role', None) or '').strip()
    if mgr_role in OPERATOR_ROLES or mgr_role not in NETWORK_CAPABLE_ROLES:
        # Still allow viewing if they somehow have hierarchy children that are channel users,
        # but never advertise Network for operators from list. If opened directly, show only channel kids.
        pass

    page = max(1, int(page or 1))
    page_size = max(1, min(100, int(page_size or 25)))

    if direct_only:
        child_ids = list(
            UserHierarchy.objects.filter(parent_user=manager).values_list('child_user_id', flat=True)
        )
    else:
        child_ids = [u.pk for u in UserHierarchy.get_subordinates(manager)]

    # Base network (no role filter) — used for chips + empty-state messaging.
    base_qs = (
        User.objects.filter(pk__in=child_ids)
        .exclude(role__in=list(OPERATOR_ROLES))
        .select_related('profile')
    )

    available_roles = list(
        base_qs.order_by().values_list('role', flat=True).distinct()
    )
    # Stable order matching CHANNEL_FILTER_ROLES
    available_roles = [r for r in CHANNEL_FILTER_ROLES if r in available_roles]

    role_filter = (role or '').strip()
    role_norm = role_filter.lower()

    # Operator role chips are invalid inside a distributor network — treat as empty with reason.
    if role_norm in ('admin', 'super admin'):
        mgr_balance = Decimal('0')
        mw = Wallet.objects.filter(user=manager, wallet_type='main', is_archived=False).first()
        if mw:
            mgr_balance = Decimal(str(mw.balance or 0))
        return {
            'manager': _user_ledger_row(
                manager,
                balance=mgr_balance,
                has_network=mgr_role in NETWORK_CAPABLE_ROLES,
            ),
            'users': [],
            'total': 0,
            'page': page,
            'page_size': page_size,
            'direct_only': bool(direct_only),
            'summary': {
                'network_balance': '0.0000',
                'network_user_count': 0,
                'by_role': {},
                'empty_reason': (
                    f'No {role_filter} accounts exist under this network. '
                    f'Try All roles or one of: {", ".join(available_roles) or "channel roles"}.'
                ),
                'available_roles': available_roles,
            },
            'roles': available_roles or list(CHANNEL_FILTER_ROLES),
            'network_capable_roles': sorted(NETWORK_CAPABLE_ROLES),
        }

    qs = base_qs
    if role_filter:
        qs = qs.filter(role__iexact=role_filter)

    q = (search or '').strip()
    if q:
        qs = qs.filter(
            Q(phone__icontains=q)
            | Q(email__icontains=q)
            | Q(user_id__icontains=q)
            | Q(display_code__icontains=q)
            | Q(member_id__icontains=q)
            | Q(first_name__icontains=q)
            | Q(last_name__icontains=q)
            | Q(profile__first_name__icontains=q)
            | Q(profile__last_name__icontains=q)
        )

    bal_sq = (
        Wallet.objects.filter(
            user_id=OuterRef('pk'),
            wallet_type='main',
            is_archived=False,
        )
        .values('balance')[:1]
    )
    qs = qs.annotate(
        main_balance=Coalesce(
            Subquery(bal_sq, output_field=DecimalField(max_digits=18, decimal_places=4)),
            Value(Decimal('0'), output_field=DecimalField(max_digits=18, decimal_places=4)),
        )
    ).order_by('-main_balance', 'id')

    total = qs.count()
    total_balance = qs.aggregate(s=Coalesce(Sum('main_balance'), Decimal('0')))['s'] or Decimal('0')

    by_role = {}
    for row in qs.values('role').annotate(
        count=Count('id'),
        balance=Coalesce(Sum('main_balance'), Decimal('0')),
    ):
        key = row['role'] or 'Unknown'
        by_role[key] = {
            'count': int(row['count'] or 0),
            'balance': _money_str(row['balance']),
        }

    start = (page - 1) * page_size
    page_rows = list(qs[start:start + page_size])
    page_ids = [u.pk for u in page_rows]
    parent_ids_with_kids = set()
    if page_ids:
        parent_ids_with_kids = set(
            UserHierarchy.objects.filter(parent_user_id__in=page_ids)
            .values_list('parent_user_id', flat=True)
            .distinct()
        )

    mgr_balance = Decimal('0')
    mw = Wallet.objects.filter(user=manager, wallet_type='main', is_archived=False).first()
    if mw:
        mgr_balance = Decimal(str(mw.balance or 0))

    empty_reason = ''
    if total == 0 and role_filter:
        empty_reason = (
            f'No {role_filter} users under this network. '
            f'Available: {", ".join(available_roles) or "none"}.'
        )

    return {
        'manager': _user_ledger_row(
            manager,
            balance=mgr_balance,
            has_network=mgr_role in NETWORK_CAPABLE_ROLES,
        ),
        'users': [
            _user_ledger_row(
                u,
                balance=getattr(u, 'main_balance', Decimal('0')) or Decimal('0'),
                has_network=(u.pk in parent_ids_with_kids) and (u.role in NETWORK_CAPABLE_ROLES),
            )
            for u in page_rows
        ],
        'total': total,
        'page': page,
        'page_size': page_size,
        'direct_only': bool(direct_only),
        'summary': {
            'network_balance': _money_str(total_balance),
            'network_user_count': total,
            'by_role': by_role,
            'empty_reason': empty_reason,
            'available_roles': available_roles,
        },
        'roles': available_roles or list(CHANNEL_FILTER_ROLES),
        'network_capable_roles': sorted(NETWORK_CAPABLE_ROLES),
    }
