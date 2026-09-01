from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('bbps', '0017_performance_report_indexes'),
    ]

    operations = [
        migrations.AddField(
            model_name='bbpsbillermaster',
            name='local_visibility_hold',
            field=models.CharField(
                blank=True,
                choices=[
                    ('', 'None'),
                    ('admin', 'Admin disabled'),
                    ('cash_only', 'Cash-only policy'),
                ],
                db_index=True,
                default='',
                help_text='Why local visibility was suppressed (admin vs cash-only policy).',
                max_length=20,
            ),
        ),
    ]
