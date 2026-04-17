# Generated manually for passbook SBI-style charge/principal columns

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('transactions', '0003_alter_passbookentry_wallet_type'),
    ]

    operations = [
        migrations.AddField(
            model_name='passbookentry',
            name='service_charge',
            field=models.DecimalField(
                decimal_places=2,
                default=0,
                help_text='Fees/charges for this line (e.g. payout slab); 0 when N/A.',
                max_digits=12,
            ),
        ),
        migrations.AddField(
            model_name='passbookentry',
            name='principal_amount',
            field=models.DecimalField(
                blank=True,
                decimal_places=2,
                help_text='Underlying transaction amount excluding charge when applicable.',
                max_digits=12,
                null=True,
            ),
        ),
    ]
