# Generated manually for contact_role and required email

from django.db import migrations, models


def backfill_email_and_role(apps, schema_editor):
    Contact = apps.get_model('contacts', 'Contact')
    for c in Contact.objects.all():
        if not c.email or not str(c.email).strip():
            c.email = f'legacy-{c.pk}@contact.placeholder'
            c.save(update_fields=['email'])


class Migration(migrations.Migration):

    dependencies = [
        ('contacts', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='contact',
            name='contact_role',
            field=models.CharField(
                choices=[
                    ('end_user', 'End-user'),
                    ('merchant', 'Merchant'),
                    ('dealer', 'Dealer'),
                ],
                db_index=True,
                default='end_user',
                max_length=20,
            ),
        ),
        migrations.RunPython(backfill_email_and_role, migrations.RunPython.noop),
        migrations.AlterField(
            model_name='contact',
            name='email',
            field=models.EmailField(max_length=254),
        ),
    ]
