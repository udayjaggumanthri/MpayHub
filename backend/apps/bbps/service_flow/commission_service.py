from __future__ import annotations

from decimal import Decimal

from django.conf import settings
from django.db.models import Q
from django.utils import timezone

from apps.bbps.models import BbpsCategoryCommissionRule, BbpsProviderBillerMap, BbpsServiceCategory
from apps.bbps.services import normalize_category_code
from apps.fund_management.money_utils import money_q


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


def _compute_rule_charge(rule, amount: Decimal) -> Decimal:
    """Compute charge from a BbpsCategoryCommissionRule."""
    amount = money_q(amount)
    if not rule:
        return Decimal('0')
    mode = str(getattr(rule, 'commission_type', '') or 'flat').lower()
    value = Decimal(str(getattr(rule, 'value', 0) or 0))
    if mode in ('percentage', 'percent', 'pct'):
        charge = money_q(amount * value / Decimal('100'))
    else:
        charge = money_q(value)
    min_c = money_q(getattr(rule, 'min_commission', 0) or 0)
    max_c = money_q(getattr(rule, 'max_commission', 0) or 0)
    if min_c > 0 and charge < min_c:
        charge = min_c
    if max_c > 0 and charge > max_c:
        charge = max_c
    return charge


def resolve_commission_for_payment(*, amount: Decimal, bill_data: dict) -> dict:
    """
    Resolve BBPS category commission rule.

    When ``BBPS_COMMISSION_FINANCIAL_IMPACT_ENABLED`` is True, the rule charge
    is applied. Otherwise the charge is returned as a shadow value (0 applied
    by the payment path which uses wallet service charge instead).
    """
    category = resolve_category_from_payload(bill_data)
    rule = _pick_rule_for_category(category)
    computed = _compute_rule_charge(rule, amount) if rule else Decimal('0')
    financial = bool(getattr(settings, 'BBPS_COMMISSION_FINANCIAL_IMPACT_ENABLED', False))
    applied = computed if financial else Decimal('0')

    snapshot = {}
    rule_code = ''
    if rule:
        rule_code = str(getattr(rule, 'rule_code', '') or rule.pk or '')
        snapshot = {
            'rule_id': rule.pk,
            'rule_code': rule_code,
            'commission_type': str(getattr(rule, 'commission_type', '') or ''),
            'value': str(getattr(rule, 'value', 0) or 0),
            'computed_charge': str(computed),
            'financial_impact': financial,
        }

    return {
        'category_code': category.code if category else '',
        'charge': applied,
        'computed_charge': computed,
        'total_deducted': amount + applied,
        'commission_rule_code': rule_code,
        'commission_rule_snapshot': snapshot,
    }
