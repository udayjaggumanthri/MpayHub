from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('bbps', '0007_bbpsbillerinputparam_mdm_extras'),
    ]

    operations = [
        migrations.AddField(
            model_name='bbpscomplaint',
            name='billavenue_request_id',
            field=models.CharField(
                blank=True,
                db_index=True,
                default='',
                help_text='35-char requestId sent to BillAvenue on complaint registration (support trace).',
                max_length=50,
            ),
        ),
    ]
