# Dark-theme logo field for platform appearance

import apps.core.models
import django.core.validators
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0005_cms_module'),
    ]

    operations = [
        migrations.AddField(
            model_name='platformappearanceconfig',
            name='logo_dark',
            field=models.ImageField(
                blank=True,
                help_text='Optional logo optimized for dark theme backgrounds.',
                max_length=500,
                null=True,
                upload_to=apps.core.models.platform_logo_dark_upload_to,
                validators=[
                    django.core.validators.FileExtensionValidator(
                        allowed_extensions=['jpg', 'jpeg', 'png', 'webp', 'gif']
                    )
                ],
            ),
        ),
    ]
