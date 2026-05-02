from __future__ import annotations

from decimal import Decimal

from django.conf import settings
from django.db.models import Q
from django.utils import timezone

from apps.bbps.models import BbpsCategoryCommissionRule, BbpsProviderBillerMap, BbpsServiceCategory
from apps.bbps.services import normalize_category_code


def _pick_rule_for_category(category: BbpsServiceCategory | None):
    if not category:
        return None
    now = timezone.now()
    return (
        BbpsCategoryCommissionRule.objects.filter(
            is_deleted=False,
            is_active=True,
            category=category,
        )
        .filter(Q(effective_from__isnull=True) | Q(effective_from__lte=now))
        .filter(Q(effective_to__isnull=True) | Q(effective_to__gte=now))
        .order_by('-effective_from', '-updated_at')
        .first()
    )


def resolve_category_from_payload(bill_data: dict) -> BbpsServiceCategory | None:
    provider_id = bill_data.get('provider_id')
    if provider_id:
        row = (
            BbpsProviderBillerMap.objects.filter(
                is_deleted=False,
                is_active=True,
                provider_id=provider_id,
                provider__is_deleted=False,
                provider__is_active=True,
                provider__category__is_deleted=False,
                provider__category__is_active=True,
            )
            .select_related('provider__category')
            .first()
        )
        if row and row.provider and row.provider.category:
            return row.provider.category

    bill_type = normalize_category_code(str(bill_data.get('bill_type') or ''))
    if bill_type:
        return BbpsServiceCategory.objects.filter(
            is_deleted=False, is_active=True, code__iexact=bill_type
        ).first()
    return None


def resolve_commission_for_payment(*, amount: Decimal, bill_data: dict) -> dict:
    category = resolve_category_from_payload(bill_data)
    charge = Decimal('0')
    return {
        'category_code': category.code if category else '',
        'charge': charge,
        'computed_charge': charge,
        'total_deducted': amount + charge,
        'commission_rule_code': '',
        'commission_rule_snapshot': {},
    }
