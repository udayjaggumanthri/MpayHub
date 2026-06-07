# Generated manually for Cashfree KYC integration

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('integrations', '0006_alter_apimaster_provider_code'),
    ]

    operations = [
        migrations.RemoveConstraint(
            model_name='apimaster',
            name='uniq_active_default_per_provider_type',
        ),
        migrations.AddField(
            model_name='apimaster',
            name='kyc_service',
            field=models.CharField(
                blank=True,
                choices=[('', 'N/A'), ('pan', 'PAN'), ('aadhaar', 'Aadhaar')],
                db_index=True,
                default='',
                max_length=20,
            ),
        ),
        migrations.AddConstraint(
            model_name='apimaster',
            constraint=models.UniqueConstraint(
                condition=models.Q(('is_default', True), ('is_deleted', False), ('provider_type', 'kyc')),
                fields=('provider_type', 'kyc_service'),
                name='uniq_active_default_per_kyc_service',
            ),
        ),
        migrations.AddConstraint(
            model_name='apimaster',
            constraint=models.UniqueConstraint(
                condition=models.Q(
                    ('is_default', True),
                    ('is_deleted', False),
                )
                & ~models.Q(provider_type='kyc'),
                fields=('provider_type',),
                name='uniq_active_default_per_non_kyc_provider_type',
            ),
        ),
    ]
