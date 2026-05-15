from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('authentication', '0003_add_super_distributor_role'),
    ]

    operations = [
        migrations.AddField(
            model_name='user',
            name='is_restricted',
            field=models.BooleanField(
                default=False,
                help_text='Read-only portal: no pay-in or payment outflows.',
            ),
        ),
        migrations.AddField(
            model_name='user',
            name='payments_locked',
            field=models.BooleanField(
                default=False,
                help_text='Block BBPS pay, payout, and wallet transfers; pay-in allowed unless restricted.',
            ),
        ),
        migrations.AddField(
            model_name='user',
            name='pay_in_allowed_when_disabled',
            field=models.BooleanField(
                default=False,
                help_text='When is_active=False, user may still log in for pay-in (load money) only.',
            ),
        ),
    ]
