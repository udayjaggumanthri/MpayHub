"""Add platform-wide payout slabs (charge + commission) and Payout split fields."""

from decimal import Decimal

from django.conf import settings
from django.db import migrations, models


def seed_platform_payout_slabs(apps, schema_editor):
    PlatformPayoutSlabTier = apps.get_model('fund_management', 'PlatformPayoutSlabTier')
    if PlatformPayoutSlabTier.objects.filter(is_deleted=False).exists():
        return

    # Prefer Django settings (authoritative defaults). PayoutSlabConfig may be stale.
    low_max = Decimal(str(getattr(settings, 'PAYOUT_SLAB_LOW_MAX', '24999')))
    low_c = Decimal(str(getattr(settings, 'PAYOUT_CHARGE_LOW', '7')))
    high_c = Decimal(str(getattr(settings, 'PAYOUT_CHARGE_HIGH', '15')))

    # If package tiers exist and majority low charge differs, prefer package pattern
    # matching settings low/high (charge only; commission=0).
    PayoutSlabTier = apps.get_model('fund_management', 'PayoutSlabTier')
    sample = (
        PayoutSlabTier.objects.filter(is_deleted=False)
        .order_by('package_id', 'sort_order')
        .first()
    )
    if sample is not None:
        # Use settings bands; package flat amounts commonly match 7 / 15.
        pass

    PlatformPayoutSlabTier.objects.create(
        sort_order=0,
        min_amount=Decimal('0'),
        max_amount=low_max,
        charge=low_c,
        commission=Decimal('0'),
    )
    PlatformPayoutSlabTier.objects.create(
        sort_order=1,
        min_amount=low_max + Decimal('1'),
        max_amount=None,
        charge=high_c,
        commission=Decimal('0'),
    )


def unseed_platform_payout_slabs(apps, schema_editor):
    PlatformPayoutSlabTier = apps.get_model('fund_management', 'PlatformPayoutSlabTier')
    PlatformPayoutSlabTier.objects.all().delete()


class Migration(migrations.Migration):

    dependencies = [
        ('fund_management', '0018_payout_vimopay_provider'),
        ('admin_panel', '0007_payout_vimopay_provider'),
    ]

    operations = [
        migrations.CreateModel(
            name='PlatformPayoutSlabTier',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True, db_index=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('deleted_at', models.DateTimeField(blank=True, db_index=True, null=True)),
                ('is_deleted', models.BooleanField(db_index=True, default=False)),
                ('sort_order', models.PositiveIntegerField(db_index=True, default=0)),
                ('min_amount', models.DecimalField(decimal_places=4, max_digits=18)),
                (
                    'max_amount',
                    models.DecimalField(
                        blank=True,
                        decimal_places=4,
                        help_text='Inclusive upper bound; null = no upper limit.',
                        max_digits=18,
                        null=True,
                    ),
                ),
                (
                    'charge',
                    models.DecimalField(
                        decimal_places=4,
                        default=Decimal('0'),
                        help_text='Gateway / service fee portion → Service Fee Tracker.',
                        max_digits=18,
                    ),
                ),
                (
                    'commission',
                    models.DecimalField(
                        decimal_places=4,
                        default=Decimal('0'),
                        help_text='Platform profit portion → treasury Main as commission.',
                        max_digits=18,
                    ),
                ),
            ],
            options={
                'db_table': 'platform_payout_slab_tiers',
                'ordering': ['sort_order', 'min_amount'],
            },
        ),
        migrations.AddIndex(
            model_name='platformpayoutslabtier',
            index=models.Index(fields=['sort_order', 'min_amount'], name='platform_pa_sort_or_7d1a2c_idx'),
        ),
        migrations.AddField(
            model_name='payout',
            name='service_charge',
            field=models.DecimalField(
                decimal_places=4,
                default=Decimal('0'),
                help_text='Gateway/service fee portion → Service Fee Tracker.',
                max_digits=18,
            ),
        ),
        migrations.AddField(
            model_name='payout',
            name='commission_amount',
            field=models.DecimalField(
                decimal_places=4,
                default=Decimal('0'),
                help_text='Platform commission portion → treasury Main.',
                max_digits=18,
            ),
        ),
        migrations.AlterField(
            model_name='payout',
            name='charge',
            field=models.DecimalField(
                decimal_places=4,
                default=Decimal('0'),
                help_text='Total fee debited from agent (service_charge + commission_amount).',
                max_digits=18,
            ),
        ),
        migrations.RunPython(seed_platform_payout_slabs, unseed_platform_payout_slabs),
    ]
