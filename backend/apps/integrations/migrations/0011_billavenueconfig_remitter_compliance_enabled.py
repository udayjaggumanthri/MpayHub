from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('integrations', '0010_payout_vimopay_provider'),
    ]

    operations = [
        migrations.AddField(
            model_name='billavenueconfig',
            name='remitter_compliance_enabled',
            field=models.BooleanField(
                default=False,
                help_text=(
                    'When on, use BillAvenue remitter/paymentInfo rules for this environment '
                    '(required for payments above Rs 50,000). When off, keep the current payload.'
                ),
            ),
        ),
    ]
