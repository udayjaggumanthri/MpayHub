from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('authentication', '0004_user_access_controls'),
    ]

    operations = [
        migrations.AddField(
            model_name='otp',
            name='delivery_channel',
            field=models.CharField(
                blank=True,
                choices=[('sms', 'SMS'), ('email', 'Email')],
                default='sms',
                max_length=10,
            ),
        ),
    ]
