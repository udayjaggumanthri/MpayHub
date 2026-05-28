from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('authentication', '0006_alter_otp_purpose'),
    ]

    operations = [
        migrations.AddField(
            model_name='user',
            name='must_change_password',
            field=models.BooleanField(
                db_index=True,
                default=False,
                help_text='User must complete OTP password reset before using the portal (onboarding).',
            ),
        ),
    ]
