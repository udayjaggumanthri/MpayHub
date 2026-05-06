from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('bbps', '0006_bbpsbillermaster_is_active_local_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='bbpsbillerinputparam',
            name='mdm_extras',
            field=models.JSONField(blank=True, default=dict),
        ),
    ]
