# Generated manually — new packages should not inherit hidden 0.06% retailer slice.

from decimal import Decimal

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('fund_management', '0011_rename_pay_pkg_gw_pkg_active_idx_pay_in_pack_package_3d64f3_idx'),
    ]

    operations = [
        migrations.AlterField(
            model_name='payinpackage',
            name='retailer_commission_pct',
            field=models.DecimalField(decimal_places=4, default=Decimal('0'), max_digits=8),
        ),
    ]
