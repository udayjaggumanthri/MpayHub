# Generated manually for system maintenance mode

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='SystemMaintenanceConfig',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('pay_in_enabled', models.BooleanField(db_index=True, default=True)),
                ('payout_enabled', models.BooleanField(db_index=True, default=True)),
                ('bbps_enabled', models.BooleanField(db_index=True, default=True)),
                ('pay_in_message', models.TextField(blank=True, default='')),
                ('payout_message', models.TextField(blank=True, default='')),
                ('bbps_message', models.TextField(blank=True, default='')),
                ('reason_internal', models.TextField(blank=True, default='')),
                ('updated_at', models.DateTimeField(auto_now=True)),
                (
                    'updated_by',
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name='maintenance_config_updates',
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                'verbose_name': 'System maintenance config',
                'verbose_name_plural': 'System maintenance config',
                'db_table': 'system_maintenance_config',
            },
        ),
        migrations.CreateModel(
            name='SystemMaintenanceAuditLog',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True, db_index=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                (
                    'module',
                    models.CharField(
                        choices=[
                            ('pay_in', 'Pay-in'),
                            ('payout', 'Payout'),
                            ('bbps', 'BBPS'),
                            ('all', 'All modules'),
                        ],
                        db_index=True,
                        max_length=20,
                    ),
                ),
                ('enabled', models.BooleanField()),
                ('user_message', models.TextField(blank=True, default='')),
                ('reason_internal', models.TextField(blank=True, default='')),
                (
                    'changed_by',
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name='maintenance_audit_entries',
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                'db_table': 'system_maintenance_audit_logs',
                'ordering': ['-created_at'],
            },
        ),
    ]
