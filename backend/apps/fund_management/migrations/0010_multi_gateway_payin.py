from django.db import migrations, models
import django.db.models.deletion


def migrate_legacy_package_gateway_links(apps, schema_editor):
    PayInPackage = apps.get_model('fund_management', 'PayInPackage')
    PayInPackageGateway = apps.get_model('fund_management', 'PayInPackageGateway')
    for pkg in PayInPackage.objects.exclude(payment_gateway_id=None):
        PayInPackageGateway.objects.get_or_create(
            package_id=pkg.pk,
            payment_gateway_id=pkg.payment_gateway_id,
            defaults={
                'is_active': True,
                'is_default': True,
                'sort_order': 0,
                'is_deleted': False,
            },
        )


class Migration(migrations.Migration):

    dependencies = [
        ('admin_panel', '0001_initial'),
        ('fund_management', '0009_rename_payout_slab_package_sort_idx_payout_slab_package_5f6782_idx'),
    ]

    operations = [
        migrations.CreateModel(
            name='PayInPackageGateway',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True, db_index=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('deleted_at', models.DateTimeField(blank=True, db_index=True, null=True)),
                ('is_deleted', models.BooleanField(db_index=True, default=False)),
                ('is_active', models.BooleanField(db_index=True, default=True)),
                ('is_default', models.BooleanField(db_index=True, default=False, help_text='Suggested gateway when user does not choose one explicitly.')),
                ('sort_order', models.PositiveIntegerField(default=0)),
                ('package', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='package_gateways', to='fund_management.payinpackage')),
                ('payment_gateway', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='package_links', to='admin_panel.paymentgateway')),
            ],
            options={
                'db_table': 'pay_in_package_gateways',
                'ordering': ['package_id', 'sort_order', 'id'],
            },
        ),
        migrations.AddIndex(
            model_name='payinpackagegateway',
            index=models.Index(fields=['package', 'is_active', 'sort_order'], name='pay_pkg_gw_pkg_active_idx'),
        ),
        migrations.AlterUniqueTogether(
            name='payinpackagegateway',
            unique_together={('package', 'payment_gateway')},
        ),
        migrations.AddField(
            model_name='loadmoney',
            name='payment_gateway',
            field=models.ForeignKey(
                blank=True,
                help_text='Gateway rail used for this pay-in attempt (credentials for verify).',
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='load_money_transactions',
                to='admin_panel.paymentgateway',
            ),
        ),
        migrations.RunPython(migrate_legacy_package_gateway_links, migrations.RunPython.noop),
    ]
