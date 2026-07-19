# Generated manually for MSG91 template sync metadata

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('notifications', '0003_sms_template_variable_map'),
    ]

    operations = [
        migrations.AddField(
            model_name='smsnotificationtemplate',
            name='mapping_source',
            field=models.CharField(blank=True, db_index=True, default='', max_length=16),
        ),
        migrations.AddField(
            model_name='smsnotificationtemplate',
            name='msg91_detected_vars',
            field=models.JSONField(blank=True, default=list),
        ),
        migrations.AddField(
            model_name='smsnotificationtemplate',
            name='msg91_dlt_id',
            field=models.CharField(blank=True, default='', max_length=64),
        ),
        migrations.AddField(
            model_name='smsnotificationtemplate',
            name='msg91_sender_id',
            field=models.CharField(blank=True, default='', max_length=32),
        ),
        migrations.AddField(
            model_name='smsnotificationtemplate',
            name='msg91_synced_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='smsnotificationtemplate',
            name='msg91_template_body',
            field=models.TextField(blank=True, default=''),
        ),
        migrations.AddField(
            model_name='smsnotificationtemplate',
            name='msg91_template_name',
            field=models.CharField(blank=True, default='', max_length=200),
        ),
    ]
