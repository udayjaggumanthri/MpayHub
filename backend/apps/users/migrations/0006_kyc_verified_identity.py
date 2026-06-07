from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0005_userprofile_date_of_birth'),
    ]

    operations = [
        migrations.AddField(
            model_name='kyc',
            name='verified_identity',
            field=models.JSONField(blank=True, default=dict),
        ),
    ]
