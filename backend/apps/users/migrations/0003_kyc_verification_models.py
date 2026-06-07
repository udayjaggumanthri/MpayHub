# Generated manually for Cashfree KYC integration

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('users', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='KycVerificationAttempt',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('is_deleted', models.BooleanField(db_index=True, default=False)),
                ('deleted_at', models.DateTimeField(blank=True, null=True)),
                ('provider_code', models.CharField(blank=True, default='', max_length=80)),
                ('verification_id', models.CharField(blank=True, db_index=True, default='', max_length=100)),
                ('reference_id', models.CharField(blank=True, default='', max_length=50)),
                ('status', models.CharField(blank=True, default='', max_length=40)),
                ('request_meta', models.JSONField(blank=True, default=dict)),
                ('response_meta', models.JSONField(blank=True, default=dict)),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='kyc_pan_attempts', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'db_table': 'kyc_verification_attempts',
                'ordering': ['-created_at'],
            },
        ),
        migrations.CreateModel(
            name='KycDigilockerSession',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('is_deleted', models.BooleanField(db_index=True, default=False)),
                ('deleted_at', models.DateTimeField(blank=True, null=True)),
                ('verification_id', models.CharField(db_index=True, max_length=50, unique=True)),
                ('reference_id', models.CharField(blank=True, default='', max_length=50)),
                ('status', models.CharField(blank=True, db_index=True, default='PENDING', max_length=30)),
                ('user_flow', models.CharField(blank=True, default='', max_length=20)),
                ('document_requested', models.JSONField(blank=True, default=list)),
                ('provider_code', models.CharField(blank=True, default='', max_length=80)),
                ('raw_status', models.JSONField(blank=True, default=dict)),
                ('completed_at', models.DateTimeField(blank=True, null=True)),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='kyc_digilocker_sessions', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'db_table': 'kyc_digilocker_sessions',
                'ordering': ['-created_at'],
            },
        ),
    ]
