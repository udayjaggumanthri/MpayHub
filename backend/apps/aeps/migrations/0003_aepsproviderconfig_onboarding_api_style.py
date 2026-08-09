from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('aeps', '0002_alter_aepsproviderconfig_environment'),
    ]

    operations = [
        migrations.AddField(
            model_name='aepsproviderconfig',
            name='onboarding_api_style',
            field=models.CharField(
                choices=[('java', 'Java / .NET'), ('php', 'PHP')],
                db_index=True,
                default='java',
                help_text='java → …/merchant/creation/v2 (AES-ECB); php → …/merchant/php/creation/v2 (AES-CBC)',
                max_length=8,
            ),
        ),
    ]
