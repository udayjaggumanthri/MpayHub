# Generated manually for BBPS wallet service charge settings

from decimal import Decimal

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('integrations', '0004_alter_billavenueconfig_crypto_defaults'),
    ]

    operations = [
        migrations.AddField(
            model_name='billavenueconfig',
            name='bbps_wallet_service_charge_mode',
            field=models.CharField(
                max_length=10,
                choices=[('FLAT', 'Flat amount'), ('PERCENT', 'Percent of bill amount')],
                default='FLAT',
                help_text='How BBPS wallet service charge is computed for quote and payment.',
            ),
        ),
        migrations.AddField(
            model_name='billavenueconfig',
            name='bbps_wallet_service_charge_flat',
            field=models.DecimalField(
                max_digits=18,
                decimal_places=4,
                default=Decimal('5.0000'),
                help_text='Flat charge (INR) when mode is FLAT.',
            ),
        ),
        migrations.AddField(
            model_name='billavenueconfig',
            name='bbps_wallet_service_charge_percent',
            field=models.DecimalField(
                max_digits=9,
                decimal_places=4,
                default=Decimal('0.0000'),
                help_text='Percent of bill amount when mode is PERCENT (e.g. 1.25 = 1.25%).',
            ),
        ),
    ]
