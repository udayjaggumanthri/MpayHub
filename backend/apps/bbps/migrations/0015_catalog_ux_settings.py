# Generated manually for BBPS catalog UX settings

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('bbps', '0014_deposit_enquiry_reporting'),
    ]

    operations = [
        migrations.CreateModel(
            name='BbpsCatalogUxSettings',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('is_deleted', models.BooleanField(db_index=True, default=False)),
                ('deleted_at', models.DateTimeField(blank=True, null=True)),
                (
                    'environment',
                    models.CharField(
                        choices=[('uat', 'UAT'), ('prod', 'Production')],
                        db_index=True,
                        max_length=10,
                        unique=True,
                    ),
                ),
                (
                    'cash_only_for_users',
                    models.BooleanField(
                        db_index=True,
                        default=False,
                        help_text='When True, end users see only AGT+Cash-capable billers and payment method is hidden.',
                    ),
                ),
                (
                    'updated_by',
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name='bbps_catalog_ux_updates',
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                'db_table': 'bbps_catalog_ux_settings',
                'ordering': ['environment'],
            },
        ),
    ]
