from __future__ import annotations

from decimal import Decimal

from django.conf import settings
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils.text import slugify

from apps.bbps.models import (
    BbpsBillerMaster,
    BbpsCategoryCommissionRule,
    BbpsProviderBillerMap,
    BbpsServiceCategory,
    BbpsServiceProvider,
)


DEFAULT_CATEGORIES = [
    ('credit-card', 'Credit Card'),
    ('mobile-recharge', 'Mobile Recharge'),
    ('electricity', 'Electricity'),
    ('water', 'Water'),
    ('gas', 'Piped Gas'),
    ('dth', 'DTH'),
    ('broadband', 'Broadband'),
    ('landline', 'Landline Postpaid'),
    ('insurance', 'Insurance'),
    ('fasttag', 'FASTag'),
    ('education', 'Education'),
    ('loan-emi', 'Loan EMI'),
    ('housing', 'Housing'),
    ('municipal-tax', 'Municipal Tax'),
    ('subscriptions', 'Subscriptions'),
]


def _norm_category(raw: str) -> str:
    out = (raw or '').strip().lower().replace('_', '-')
    aliases = {
        'mobile': 'mobile-recharge',
        'creditcard': 'credit-card',
        'credit-card-bill': 'credit-card',
        'cc': 'credit-card',
        'broad-band': 'broadband',
        'landline-postpaid': 'landline',
    }
    return aliases.get(out, out)


class Command(BaseCommand):
    help = 'Seed BBPS governance catalog (categories/providers/maps/commission rules) from biller master.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Preview without writing DB rows.',
        )
        parser.add_argument(
            '--default-rule-active',
            action='store_true',
            help='Create default commission rules as active (default is inactive).',
        )
        parser.add_argument(
            '--remap-existing',
            action='store_true',
            help='Rebind provider->biller map metadata for existing records deterministically.',
        )

    @transaction.atomic
    def handle(self, *args, **options):
        dry_run = bool(options.get('dry_run'))
        default_rule_active = bool(options.get('default_rule_active'))
        remap_existing = bool(options.get('remap_existing'))

        cat_created = 0
        provider_created = 0
        map_created = 0
        rule_created = 0
        skipped = []

        # 1) Seed baseline categories.
        category_map = {}
        for idx, (code, name) in enumerate(DEFAULT_CATEGORIES):
            obj, created = BbpsServiceCategory.objects.get_or_create(
                code=code,
                defaults={'name': name, 'is_active': True, 'display_order': idx},
            )
            category_map[code] = obj
            if created:
                cat_created += 1

        # 2) Extend categories from biller master labels (if unseen).
        distinct_cats = (
            BbpsBillerMaster.objects.filter(is_deleted=False)
            .values_list('biller_category', flat=True)
            .distinct()
        )
        for raw in distinct_cats:
            code = _norm_category(raw)
            if not code:
                skipped.append({'type': 'category', 'reason': 'blank_category'})
                continue
            if code not in category_map:
                obj, created = BbpsServiceCategory.objects.get_or_create(
                    code=code,
                    defaults={'name': str(raw).strip() or code.replace('-', ' ').title(), 'is_active': True, 'display_order': 1000},
                )
                category_map[code] = obj
                if created:
                    cat_created += 1

        # 3) Create provider + map rows from biller master (1:1 bootstrap).
        billers = BbpsBillerMaster.objects.filter(is_deleted=False).order_by('biller_name')
        for biller in billers:
            ccode = _norm_category(biller.biller_category)
            if not ccode:
                skipped.append({'type': 'biller', 'biller_id': biller.biller_id, 'reason': 'blank_category'})
                continue
            cat = category_map.get(ccode)
            if not cat:
                skipped.append({'type': 'biller', 'biller_id': biller.biller_id, 'reason': 'category_not_seeded', 'category': ccode})
                continue
            p_code = slugify(f"{ccode}-{biller.biller_id}")[:80] or slugify(biller.biller_id)[:80]
            provider, p_created = BbpsServiceProvider.objects.get_or_create(
                category=cat,
                code=p_code,
                defaults={
                    'name': (biller.biller_name or biller.biller_id)[:150],
                    'provider_type': 'bank' if 'credit' in ccode or 'card' in ccode else 'operator',
                    'is_active': True,
                    'priority': 0,
                    'metadata': {'seed_source': 'biller_master', 'biller_id': biller.biller_id},
                },
            )
            if p_created:
                provider_created += 1
            _, m_created = BbpsProviderBillerMap.objects.get_or_create(
                provider=provider,
                biller_master=biller,
                defaults={'is_active': True, 'priority': 0, 'metadata': {'seed_source': 'biller_master'}},
            )
            if m_created:
                map_created += 1
            elif remap_existing:
                row = BbpsProviderBillerMap.objects.filter(provider=provider, biller_master=biller, is_deleted=False).first()
                if row:
                    row.priority = 0
                    row.is_active = True
                    row.metadata = {'seed_source': 'biller_master', 'remapped': True}
                    row.save(update_fields=['priority', 'is_active', 'metadata', 'updated_at'])

        # 4) Ensure one default category-level rule per category.
        for code, cat in category_map.items():
            rule_code = f"DEFAULT-{code}".upper().replace('_', '-')[:80]
            _, r_created = BbpsCategoryCommissionRule.objects.get_or_create(
                category=cat,
                rule_code=rule_code,
                defaults={
                    'commission_type': 'flat',
                    'value': Decimal(str(getattr(settings, 'BBPS_SERVICE_CHARGE', 5))),
                    'min_commission': Decimal('0'),
                    'max_commission': Decimal('0'),
                    'is_active': default_rule_active,
                    'notes': 'Seeded default rule',
                },
            )
            if r_created:
                rule_created += 1

        if dry_run:
            transaction.set_rollback(True)
            self.stdout.write(self.style.WARNING('Dry-run mode: rolled back all changes.'))

        self.stdout.write(
            self.style.SUCCESS(
                f"BBPS governance seed complete: categories_created={cat_created}, "
                f"providers_created={provider_created}, maps_created={map_created}, "
                f"rules_created={rule_created}, skipped={len(skipped)}, dry_run={dry_run}"
            )
        )
        if skipped:
            self.stdout.write(self.style.WARNING(f"Skipped sample: {skipped[:20]}"))
