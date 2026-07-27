# Generated manually for UserRoleHistory

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('users', '0009_kyc_awaiting_admin_approval'),
        ('authentication', '0009_backfill_member_identity'),
    ]

    operations = [
        migrations.CreateModel(
            name='UserRoleHistory',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('user_pk_snapshot', models.PositiveBigIntegerField(blank=True, db_index=True, null=True)),
                ('member_number', models.PositiveBigIntegerField(blank=True, db_index=True, null=True)),
                ('member_id', models.CharField(blank=True, default='', max_length=24)),
                ('legacy_user_id', models.CharField(blank=True, default='', max_length=20)),
                ('old_role', models.CharField(blank=True, default='', max_length=40)),
                ('new_role', models.CharField(blank=True, default='', max_length=40)),
                ('old_display_code', models.CharField(blank=True, default='', max_length=24)),
                ('new_display_code', models.CharField(blank=True, default='', max_length=24)),
                ('reason', models.TextField(blank=True, default='')),
                ('created_at', models.DateTimeField(auto_now_add=True, db_index=True)),
                (
                    'actor',
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name='role_change_actions',
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    'user',
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name='role_history',
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                'db_table': 'user_role_history',
                'ordering': ['-created_at'],
            },
        ),
        migrations.AddIndex(
            model_name='userrolehistory',
            index=models.Index(fields=['user', 'created_at'], name='user_role_hist_user_created'),
        ),
        migrations.AddIndex(
            model_name='userrolehistory',
            index=models.Index(fields=['member_id', 'created_at'], name='user_role_hist_member_created'),
        ),
    ]
