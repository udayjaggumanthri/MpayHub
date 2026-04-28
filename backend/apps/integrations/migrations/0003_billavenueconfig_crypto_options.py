from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('integrations', '0002_billavenueconfig_billavenueagentprofile_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='billavenueconfig',
            name='crypto_key_derivation',
            field=models.CharField(
                choices=[('rawhex', 'Raw hex (AES key bytes)'), ('md5', 'MD5 (legacy PHP samples)')],
                default='rawhex',
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name='billavenueconfig',
            name='enc_request_encoding',
            field=models.CharField(
                choices=[('base64', 'Base64'), ('hex', 'Hex')],
                default='base64',
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name='billavenueconfig',
            name='allow_variant_fallback',
            field=models.BooleanField(default=True),
        ),
        migrations.AddField(
            model_name='billavenueconfig',
            name='allow_txn_status_path_fallback',
            field=models.BooleanField(default=True),
        ),
    ]

