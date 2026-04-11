# Generated manually for pay-in reporting (mode of payment + gateway context).

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('fund_management', '0003_seed_pay_in_packages'),
    ]

    operations = [
        migrations.AddField(
            model_name='loadmoney',
            name='payment_method',
            field=models.CharField(
                blank=True,
                default='',
                help_text='Provider payment channel, e.g. upi, card, netbanking (from Razorpay etc.).',
                max_length=32,
            ),
        ),
        migrations.AddField(
            model_name='loadmoney',
            name='payment_meta',
            field=models.JSONField(
                blank=True,
                default=dict,
                help_text='Optional capture details (e.g. card_type, network) for display.',
            ),
        ),
    ]
