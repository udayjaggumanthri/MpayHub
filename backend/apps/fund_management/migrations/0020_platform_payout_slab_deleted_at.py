"""Ensure deleted_at on platform_payout_slab_tiers; fix charge seed to 7/15.

0019 already creates deleted_at via BaseModel fields. This migration remains for
envs that applied an older 0019 without the column, and for the charge reseed.
"""

from decimal import Decimal

from django.conf import settings
from django.db import migrations, models


def ensure_deleted_at_column(apps, schema_editor):
    connection = schema_editor.connection
    table = "platform_payout_slab_tiers"
    with connection.cursor() as cursor:
        columns = {
            col.name for col in connection.introspection.get_table_description(cursor, table)
        }
    if "deleted_at" in columns:
        return

    PlatformPayoutSlabTier = apps.get_model("fund_management", "PlatformPayoutSlabTier")
    field = models.DateTimeField(blank=True, db_index=True, null=True)
    field.set_attributes_from_name("deleted_at")
    schema_editor.add_field(PlatformPayoutSlabTier, field)


def fix_platform_slab_charges(apps, schema_editor):
    PlatformPayoutSlabTier = apps.get_model("fund_management", "PlatformPayoutSlabTier")
    low_max = Decimal(str(getattr(settings, "PAYOUT_SLAB_LOW_MAX", "24999")))
    low_c = Decimal(str(getattr(settings, "PAYOUT_CHARGE_LOW", "7")))
    high_c = Decimal(str(getattr(settings, "PAYOUT_CHARGE_HIGH", "15")))
    PlatformPayoutSlabTier.objects.filter(is_deleted=False).update(is_deleted=True)
    PlatformPayoutSlabTier.objects.create(
        sort_order=0,
        min_amount=Decimal("0"),
        max_amount=low_max,
        charge=low_c,
        commission=Decimal("0"),
        is_deleted=False,
    )
    PlatformPayoutSlabTier.objects.create(
        sort_order=1,
        min_amount=low_max + Decimal("1"),
        max_amount=None,
        charge=high_c,
        commission=Decimal("0"),
        is_deleted=False,
    )


class Migration(migrations.Migration):

    dependencies = [
        ("fund_management", "0019_platform_payout_slab_tiers"),
    ]

    operations = [
        # State already has deleted_at from 0019; only touch DB when missing.
        migrations.SeparateDatabaseAndState(
            state_operations=[],
            database_operations=[
                migrations.RunPython(ensure_deleted_at_column, migrations.RunPython.noop),
            ],
        ),
        migrations.RunPython(fix_platform_slab_charges, migrations.RunPython.noop),
    ]
