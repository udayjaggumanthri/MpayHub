# Generated manually for SmtpConfig

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('admin_panel', '0004_payout_slab_config'),
    ]

    operations = [
        migrations.CreateModel(
            name='SmtpConfig',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True, db_index=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('deleted_at', models.DateTimeField(blank=True, db_index=True, null=True)),
                ('is_deleted', models.BooleanField(db_index=True, default=False)),
                ('name', models.CharField(db_index=True, default='default', max_length=100, unique=True)),
                ('host', models.CharField(default='smtppro.zoho.in', max_length=255)),
                ('port', models.PositiveIntegerField(default=587)),
                ('use_tls', models.BooleanField(default=True, help_text='Use STARTTLS (typical for port 587).')),
                ('use_ssl', models.BooleanField(default=False, help_text='Use SSL (typical for port 465).')),
                ('username', models.CharField(blank=True, default='', max_length=255)),
                ('password_encrypted', models.TextField(blank=True, default='')),
                ('from_email', models.EmailField(blank=True, default='', max_length=254)),
                ('enabled', models.BooleanField(db_index=True, default=False)),
                ('is_active', models.BooleanField(db_index=True, default=False)),
            ],
            options={
                'db_table': 'smtp_configs',
                'ordering': ['-is_active', '-updated_at'],
            },
        ),
        migrations.AddConstraint(
            model_name='smtpconfig',
            constraint=models.UniqueConstraint(
                condition=models.Q(('is_active', True), ('is_deleted', False)),
                fields=('is_active',),
                name='uniq_smtp_active_config',
            ),
        ),
    ]
