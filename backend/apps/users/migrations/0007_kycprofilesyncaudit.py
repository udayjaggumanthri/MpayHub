import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0006_kyc_verified_identity'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='KycProfileSyncAudit',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True, db_index=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('deleted_at', models.DateTimeField(blank=True, db_index=True, null=True)),
                ('is_deleted', models.BooleanField(db_index=True, default=False)),
                ('source', models.CharField(blank=True, default='', max_length=20)),
                ('trigger', models.CharField(blank=True, default='', max_length=40)),
                ('status', models.CharField(choices=[('pending', 'Pending confirmation'), ('applied', 'Applied after confirmation'), ('auto_applied', 'Auto-applied'), ('declined', 'Declined by user')], db_index=True, default='pending', max_length=20)),
                ('before_first_name', models.CharField(blank=True, default='', max_length=150)),
                ('before_last_name', models.CharField(blank=True, default='', max_length=150)),
                ('before_date_of_birth', models.DateField(blank=True, null=True)),
                ('verified_full_name', models.CharField(blank=True, default='', max_length=300)),
                ('verified_date_of_birth', models.DateField(blank=True, null=True)),
                ('after_first_name', models.CharField(blank=True, default='', max_length=150)),
                ('after_last_name', models.CharField(blank=True, default='', max_length=150)),
                ('after_date_of_birth', models.DateField(blank=True, null=True)),
                ('sync_token', models.CharField(blank=True, db_index=True, max_length=64, null=True, unique=True)),
                ('sync_token_expires_at', models.DateTimeField(blank=True, null=True)),
                ('confirmed_at', models.DateTimeField(blank=True, null=True)),
                ('declined_at', models.DateTimeField(blank=True, null=True)),
                ('metadata', models.JSONField(blank=True, default=dict)),
                ('actor_user', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='kyc_profile_sync_actions', to=settings.AUTH_USER_MODEL)),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='kyc_profile_sync_audits', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'db_table': 'kyc_profile_sync_audits',
                'ordering': ['-created_at'],
                'indexes': [models.Index(fields=['user', 'status', '-created_at'], name='kyc_prof_sync_user_st_idx')],
            },
        ),
    ]
