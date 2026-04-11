# Generated manually — seed default pay-in packages.

from decimal import Decimal

from django.db import migrations


def seed_packages(apps, schema_editor):
    PayInPackage = apps.get_model('fund_management', 'PayInPackage')
    rows = [
        ('slpe_gold_travel_lite', 'Slpe Gold Travel — Lite', 10),
        ('slpe_gold_travel_prime', 'Slpe Gold Travel — Prime', 20),
        ('slpe_gold_travel_pure', 'Slpe Gold Travel — Pure', 30),
        ('slpe_silver_prime_edu', 'Slpe Silver Prime Edu', 40),
        ('slpe_silver_edu_lite', 'Slpe Silver Edu Lite', 50),
        ('slpe_standard_package', 'Slpe Standard Package', 60),
    ]
    defaults = {
        'min_amount': Decimal('1'),
        'max_amount_per_txn': Decimal('200000'),
        'gateway_fee_pct': Decimal('1'),
        'admin_pct': Decimal('0.24'),
        'super_distributor_pct': Decimal('0.01'),
        'master_distributor_pct': Decimal('0.02'),
        'distributor_pct': Decimal('0.03'),
        'retailer_commission_pct': Decimal('0.06'),
        'provider': 'mock',
        'is_active': True,
    }
    for code, name, sort_order in rows:
        PayInPackage.objects.update_or_create(
            code=code,
            defaults={**defaults, 'display_name': name, 'sort_order': sort_order},
        )


def unseed_packages(apps, schema_editor):
    PayInPackage = apps.get_model('fund_management', 'PayInPackage')
    PayInPackage.objects.filter(
        code__in=[
            'slpe_gold_travel_lite',
            'slpe_gold_travel_prime',
            'slpe_gold_travel_pure',
            'slpe_silver_prime_edu',
            'slpe_silver_edu_lite',
            'slpe_standard_package',
        ]
    ).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('fund_management', '0002_enterprise_payin_payout'),
    ]

    operations = [
        migrations.RunPython(seed_packages, unseed_packages),
    ]
