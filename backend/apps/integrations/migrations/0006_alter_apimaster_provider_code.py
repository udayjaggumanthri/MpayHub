from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('integrations', '0005_billavenueconfig_bbps_wallet_service_charge'),
    ]

    operations = [
        migrations.AlterField(
            model_name='apimaster',
            name='provider_code',
            field=models.SlugField(db_index=True, max_length=80),
        ),
    ]

