"""Add missing deleted_at on platform_payout_slab_tiers; fix charge seed to 7/15."""

from decimal import Decimal

from django.conf import settings
from django.db import migrations, models


def fix_platform_slab_charges(apps, schema_editor):
    PlatformPayoutSlabTier = apps.get_model('fund_management', 'PlatformPayoutSlabTier')
    low_max = Decimal(str(getattr(settings, 'PAYOUT_SLAB_LOW_MAX', '24999')))
    low_c = Decimal(str(getattr(settings, 'PAYOUT_CHARGE_LOW', '7')))
    high_c = Decimal(str(getattr(settings, 'PAYOUT_CHARGE_HIGH', '15')))
    PlatformPayoutSlabTier.objects.filter(is_deleted=False).update(is_deleted=True)
    PlatformPayoutSlabTier.objects.create(
        sort_order=0,
        min_amount=Decimal('0'),
        max_amount=low_max,
        charge=low_c,
        commission=Decimal('0'),
        is_deleted=False,
    )
    PlatformPayoutSlabTier.objects.create(
        sort_order=1,
        min_amount=low_max + Decimal('1'),
        max_amount=None,
        charge=high_c,
        commission=Decimal('0'),
        is_deleted=False,
    )


class Migration(migrations.Migration):

    dependencies = [
        ('fund_management', '0019_platform_payout_slab_tiers'),
    ]

    operations = [
        migrations.AddField(
            model_name='platformpayoutslabtier',
            name='deleted_at',
            field=models.DateTimeField(blank=True, db_index=True, null=True),
        ),
        migrations.RunPython(fix_platform_slab_charges, migrations.RunPython.noop),
    ]
