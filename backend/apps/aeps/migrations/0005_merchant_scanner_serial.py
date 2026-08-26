from django.db import migrations, models


def move_mantra_serial_to_scanner_serial(apps, schema_editor):
    AepsMerchantProfile = apps.get_model('aeps', 'AepsMerchantProfile')
    for merchant in AepsMerchantProfile.objects.exclude(device_imei=''):
        imei = (merchant.device_imei or '').strip()
        # Legacy saves stored Mantra serial (short) as device_imei — not the phone IMEI Fingpay expects.
        if len(imei) < 12 and imei.isdigit():
            merchant.scanner_serial = imei
            merchant.device_imei = ''
            merchant.device_ready = False
            merchant.save(update_fields=['scanner_serial', 'device_imei', 'device_ready'])


class Migration(migrations.Migration):

    dependencies = [
        ('aeps', '0004_provider_simple_debug_endpoints'),
    ]

    operations = [
        migrations.AddField(
            model_name='aepsmerchantprofile',
            name='scanner_serial',
            field=models.CharField(
                blank=True,
                default='',
                help_text='Mantra fingerprint scanner serial (local RD + optional matmSerialNumber)',
                max_length=64,
            ),
        ),
        migrations.AlterField(
            model_name='aepsmerchantprofile',
            name='device_imei',
            field=models.CharField(
                blank=True,
                default='',
                help_text='Phone/tablet IMEI sent as Fingpay deviceIMEI header',
                max_length=64,
            ),
        ),
        migrations.RunPython(move_mantra_serial_to_scanner_serial, migrations.RunPython.noop),
    ]
