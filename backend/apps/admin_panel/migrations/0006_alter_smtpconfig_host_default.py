from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('admin_panel', '0005_smtpconfig'),
    ]

    operations = [
        migrations.AlterField(
            model_name='smtpconfig',
            name='host',
            field=models.CharField(blank=True, default='', max_length=255),
        ),
    ]
