from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('admin_panel', '0007_payout_vimopay_provider'),
    ]

    operations = [
        migrations.CreateModel(
            name='TransactionIdSettings',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('key', models.CharField(default='global', max_length=32, unique=True)),
                ('load_money', models.CharField(default='PMLM', max_length=12)),
                ('payin', models.CharField(default='PMPI', max_length=12)),
                ('payout', models.CharField(default='PMPO', max_length=12)),
                ('wallet_transfer', models.CharField(default='PMWT', max_length=12)),
                ('bbps', models.CharField(default='PMBBPS', max_length=12)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={'db_table': 'transaction_id_settings'},
        ),
    ]
