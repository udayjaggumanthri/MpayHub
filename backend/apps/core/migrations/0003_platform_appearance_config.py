# Generated manually for platform appearance config

import apps.core.models
import django.core.validators
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0002_aeps_module'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='PlatformAppearanceConfig',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('site_title', models.CharField(default='mPayHub', max_length=120)),
                (
                    'logo',
                    models.ImageField(
                        blank=True,
                        max_length=500,
                        null=True,
                        upload_to=apps.core.models.platform_logo_upload_to,
                        validators=[
                            django.core.validators.FileExtensionValidator(
                                allowed_extensions=['jpg', 'jpeg', 'png', 'webp', 'gif']
                            )
                        ],
                    ),
                ),
                ('login_welcome_heading', models.CharField(default='WELCOME TO', max_length=200)),
                (
                    'login_tagline',
                    models.CharField(default='Driven by trust, Built for Scale', max_length=300),
                ),
                ('login_footer_note', models.TextField(blank=True, default='')),
                ('login_footer_privacy_url', models.URLField(blank=True, default='')),
                ('login_footer_terms_url', models.URLField(blank=True, default='')),
                ('login_footer_refund_url', models.URLField(blank=True, default='')),
                (
                    'default_theme',
                    models.CharField(
                        choices=[('light', 'Light'), ('dark', 'Dark')],
                        db_index=True,
                        default='light',
                        max_length=10,
                    ),
                ),
                ('user_theme_toggle_enabled', models.BooleanField(db_index=True, default=False)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                (
                    'updated_by',
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name='appearance_config_updates',
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                'verbose_name': 'Platform appearance config',
                'verbose_name_plural': 'Platform appearance config',
                'db_table': 'platform_appearance_config',
            },
        ),
    ]
