# Generated manually for unified per-package payout slabs

from decimal import Decimal

from django.db import migrations, models
import django.db.models.deletion


def seed_payout_slabs_from_global(apps, schema_editor):
    PayInPackage = apps.get_model('fund_management', 'PayInPackage')
    PayoutSlabTier = apps.get_model('fund_management', 'PayoutSlabTier')
    PayoutSlabConfig = apps.get_model('admin_panel', 'PayoutSlabConfig')

    cfg = (
        PayoutSlabConfig.objects.filter(is_active=True).order_by('-updated_at', '-id').first()
        or PayoutSlabConfig.objects.order_by('-id').first()
    )
    if cfg:
        low_max = Decimal(str(cfg.low_max_amount))
        low_c = Decimal(str(cfg.low_charge))
        high_c = Decimal(str(cfg.high_charge))
    else:
        low_max = Decimal('24999')
        low_c = Decimal('7')
        high_c = Decimal('15')

    step = Decimal('0.0001')
    for pkg in PayInPackage.objects.all():
        if PayoutSlabTier.objects.filter(package_id=pkg.pk, is_deleted=False).exists():
            continue
        PayoutSlabTier.objects.create(
            package_id=pkg.pk,
            sort_order=0,
            min_amount=Decimal('0'),
            max_amount=low_max,
            flat_charge=low_c,
            is_deleted=False,
        )
        PayoutSlabTier.objects.create(
            package_id=pkg.pk,
            sort_order=1,
            min_amount=low_max + step,
            max_amount=None,
            flat_charge=high_c,
            is_deleted=False,
        )


class Migration(migrations.Migration):

    dependencies = [
        ('fund_management', '0007_package_assignment'),
        ('admin_panel', '0004_payout_slab_config'),
    ]

    operations = [
        migrations.CreateModel(
            name='PayoutSlabTier',
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
                ('flat_charge', models.DecimalField(decimal_places=4, max_digits=18)),
                (
                    'package',
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name='payout_slabs',
                        to='fund_management.payinpackage',
                    ),
                ),
            ],
            options={
                'db_table': 'payout_slab_tiers',
                'ordering': ['package_id', 'sort_order', 'min_amount'],
            },
        ),
        migrations.AddIndex(
            model_name='payoutslabtier',
            index=models.Index(fields=['package', 'sort_order'], name='payout_slab_package_sort_idx'),
        ),
        migrations.RunPython(seed_payout_slabs_from_global, migrations.RunPython.noop),
    ]
