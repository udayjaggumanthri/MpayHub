import django.core.validators
from django.db import migrations, models
import apps.admin_panel.models


class Migration(migrations.Migration):

    dependencies = [
        ('admin_panel', '0008_transaction_id_settings'),
    ]

    operations = [
        migrations.CreateModel(
            name='InvoiceSettings',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('key', models.CharField(default='global', max_length=32, unique=True)),
                ('legal_name', models.CharField(default='Prajnadhara', max_length=150)),
                ('company_line', models.CharField(default='Infotech Pvt Ltd', max_length=150)),
                (
                    'address',
                    models.TextField(
                        default=(
                            '1st Floor, 7-28-6, Tanvi Castle, Tyaga Raja Nagar, '
                            'Rajamahendravaram, East Godavari, Andhra Pradesh, 533101.'
                        ),
                    ),
                ),
                ('phone', models.CharField(default='+91 9052513666', max_length=40)),
                ('email', models.EmailField(default='info@prajnadharainfotech.com', max_length=254)),
                ('gst_number', models.CharField(default='37AAQCP8786M1Z4', max_length=20)),
                ('gst_rate_percent', models.DecimalField(decimal_places=2, default=18, max_digits=5)),
                (
                    'declaration',
                    models.TextField(
                        default=(
                            'We declare that this invoice reflects the actual price of the services '
                            'described and that all particulars are true and correct.'
                        ),
                    ),
                ),
                (
                    'signature',
                    models.ImageField(
                        blank=True,
                        max_length=500,
                        null=True,
                        upload_to=apps.admin_panel.models.invoice_signature_upload_to,
                        validators=[
                            django.core.validators.FileExtensionValidator(
                                allowed_extensions=['jpg', 'jpeg', 'png', 'webp', 'gif']
                            )
                        ],
                    ),
                ),
                (
                    'stamp',
                    models.ImageField(
                        blank=True,
                        max_length=500,
                        null=True,
                        upload_to=apps.admin_panel.models.invoice_stamp_upload_to,
                        validators=[
                            django.core.validators.FileExtensionValidator(
                                allowed_extensions=['jpg', 'jpeg', 'png', 'webp', 'gif']
                            )
                        ],
                    ),
                ),
                ('invoice_next_number', models.PositiveIntegerField(default=1)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={
                'db_table': 'invoice_settings',
            },
        ),
    ]
