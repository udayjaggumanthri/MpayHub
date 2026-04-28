from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('integrations', '0003_billavenueconfig_crypto_options'),
    ]

    operations = [
        migrations.AlterField(
            model_name='billavenueconfig',
            name='crypto_key_derivation',
            field=models.CharField(
                choices=[('rawhex', 'Raw hex (AES key bytes)'), ('md5', 'MD5 (legacy PHP samples)')],
                default='md5',
                max_length=20,
            ),
        ),
        migrations.AlterField(
            model_name='billavenueconfig',
            name='enc_request_encoding',
            field=models.CharField(
                choices=[('base64', 'Base64'), ('hex', 'Hex')],
                default='hex',
                max_length=20,
            ),
        ),
    ]

