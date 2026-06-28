from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('contacts', '0002_contact_role_required_email'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='contact',
            name='contact_role',
        ),
    ]
