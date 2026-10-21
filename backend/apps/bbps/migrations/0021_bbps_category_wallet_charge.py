from decimal import Decimal

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('bbps', '0020_bbps_status_sync_fields'),
    ]

    operations = [
        migrations.CreateModel(
            name='BbpsCategoryWalletCharge',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True, db_index=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('category_code', models.SlugField(max_length=80, unique=True)),
                ('mode', models.CharField(choices=[('FLAT', 'Flat amount'), ('PERCENT', 'Percent of bill amount')], default='FLAT', max_length=10)),
                ('flat', models.DecimalField(decimal_places=4, default=Decimal('0'), max_digits=18)),
                ('percent', models.DecimalField(decimal_places=4, default=Decimal('0'), max_digits=9)),
                ('is_active', models.BooleanField(db_index=True, default=True)),
                ('updated_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='bbps_category_wallet_charge_updates', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'db_table': 'bbps_category_wallet_charge',
                'ordering': ['category_code'],
            },
        ),
    ]
