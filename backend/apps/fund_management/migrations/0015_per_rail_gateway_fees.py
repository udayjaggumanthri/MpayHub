from decimal import Decimal

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('fund_management', '0014_manual_qr_payin'),
    ]

    operations = [
        migrations.AddField(
            model_name='payinpackagegateway',
            name='gateway_fee_pct',
            field=models.DecimalField(
                blank=True,
                decimal_places=4,
                help_text='Per-gateway fee on this package; null uses package.gateway_fee_pct.',
                max_digits=8,
                null=True,
            ),
        ),
        migrations.AddField(
            model_name='payinpackageqrlink',
            name='gateway_fee_pct',
            field=models.DecimalField(
                blank=True,
                decimal_places=4,
                help_text='Per-QR fee on this package; null uses package.gateway_fee_pct.',
                max_digits=8,
                null=True,
            ),
        ),
        migrations.AddField(
            model_name='payinqraccount',
            name='charge_rate',
            field=models.DecimalField(
                decimal_places=4,
                default=Decimal('0'),
                help_text='Minimum allowed gateway fee % when this QR is linked on a package.',
                max_digits=8,
            ),
        ),
    ]
