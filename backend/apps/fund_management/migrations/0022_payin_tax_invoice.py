import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('fund_management', '0021_rename_platform_pa_sort_or_7d1a2c_idx_platform_pa_sort_or_5bae0c_idx'),
    ]

    operations = [
        migrations.CreateModel(
            name='PayinTaxInvoice',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True, db_index=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('is_deleted', models.BooleanField(db_index=True, default=False)),
                ('deleted_at', models.DateTimeField(blank=True, null=True)),
                ('invoice_number', models.CharField(db_index=True, max_length=40, unique=True)),
                ('payload', models.JSONField(blank=True, default=dict)),
                (
                    'created_by',
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name='payin_tax_invoices',
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    'load_money',
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name='tax_invoice',
                        to='fund_management.loadmoney',
                    ),
                ),
            ],
            options={
                'db_table': 'payin_tax_invoices',
                'ordering': ['-created_at'],
            },
        ),
    ]
