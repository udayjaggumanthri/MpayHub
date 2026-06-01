# Zero hidden 0.06% retailer slice accidentally applied via old model default.

from decimal import Decimal

from django.db import migrations


def zero_legacy_retailer_default(apps, schema_editor):
    PayInPackage = apps.get_model('fund_management', 'PayInPackage')
    PayInPackage.objects.filter(retailer_commission_pct=Decimal('0.06')).update(
        retailer_commission_pct=Decimal('0')
    )


class Migration(migrations.Migration):

    dependencies = [
        ('fund_management', '0012_payinpackage_retailer_default_zero'),
    ]

    operations = [
        migrations.RunPython(zero_legacy_retailer_default, migrations.RunPython.noop),
    ]
