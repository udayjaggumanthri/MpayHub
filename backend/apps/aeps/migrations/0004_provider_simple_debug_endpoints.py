# Generated manually for AEPS provider config + debug audit expansion

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('aeps', '0003_aepsproviderconfig_onboarding_api_style'),
    ]

    operations = [
        migrations.AlterField(
            model_name='aepsproviderconfig',
            name='environment',
            field=models.CharField(
                choices=[('uat', 'UAT'), ('prod', 'Production'), ('simple', 'Simple API')],
                db_index=True,
                default='prod',
                max_length=10,
            ),
        ),
        migrations.AddField(
            model_name='aepsproviderconfig',
            name='api_mode',
            field=models.CharField(
                choices=[('encrypted', 'Encrypted (AES + RSA eskey)'), ('simple', 'Simple (plain JSON)')],
                db_index=True,
                default='encrypted',
                help_text='encrypted → AES+RSA; simple → plain JSON + secret-key hashes',
                max_length=12,
            ),
        ),
        migrations.AddField(
            model_name='aepsproviderconfig',
            name='debug_mode',
            field=models.BooleanField(
                default=False,
                help_text='When on, store full request/response exchange on every Fingpay call',
            ),
        ),
        migrations.AddField(
            model_name='aepsproviderconfig',
            name='egress_ip',
            field=models.CharField(
                blank=True,
                default='139.99.47.143',
                help_text='Public egress IP sent as ipAddress and used in whitelist diagnosis',
                max_length=64,
            ),
        ),
        migrations.AddField(
            model_name='aepsproviderconfig',
            name='endpoints_json',
            field=models.JSONField(blank=True, default=dict),
        ),
        migrations.AddField(
            model_name='aepsapiauditlog',
            name='debug_enabled',
            field=models.BooleanField(db_index=True, default=False),
        ),
        migrations.AddField(
            model_name='aepsapiauditlog',
            name='request_headers',
            field=models.JSONField(blank=True, default=dict),
        ),
        migrations.AddField(
            model_name='aepsapiauditlog',
            name='request_body',
            field=models.JSONField(blank=True, default=dict),
        ),
        migrations.AddField(
            model_name='aepsapiauditlog',
            name='response_body',
            field=models.JSONField(blank=True, default=dict),
        ),
        migrations.AddField(
            model_name='aepsapiauditlog',
            name='exchange_pack',
            field=models.JSONField(blank=True, default=dict),
        ),
    ]
