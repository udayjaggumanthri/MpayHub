from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


def backfill_contact_links(apps, schema_editor):
    """Copy BankAccount.contact_id into the link table. Idempotent. Does not alter bank rows."""
    BankAccount = apps.get_model('bank_accounts', 'BankAccount')
    Link = apps.get_model('bank_accounts', 'BankAccountContactLink')
    existing = set(
        Link.objects.values_list('bank_account_id', 'contact_id')
    )
    pending = []
    for row in (
        BankAccount.objects.exclude(contact_id=None)
        .values_list('id', 'user_id', 'contact_id')
        .iterator()
    ):
        account_id, user_id, contact_id = row
        key = (account_id, contact_id)
        if key in existing:
            continue
        existing.add(key)
        pending.append(
            Link(
                bank_account_id=account_id,
                user_id=user_id,
                contact_id=contact_id,
                is_deleted=False,
            )
        )
        if len(pending) >= 500:
            Link.objects.bulk_create(pending, ignore_conflicts=True)
            pending = []
    if pending:
        Link.objects.bulk_create(pending, ignore_conflicts=True)


class Migration(migrations.Migration):

    dependencies = [
        ('contacts', '0003_remove_contact_contact_role'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('bank_accounts', '0005_bankaccount_mobile_number'),
    ]

    operations = [
        migrations.CreateModel(
            name='BankAccountContactLink',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True, db_index=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('deleted_at', models.DateTimeField(blank=True, db_index=True, null=True)),
                ('is_deleted', models.BooleanField(db_index=True, default=False)),
                (
                    'bank_account',
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name='contact_links',
                        to='bank_accounts.bankaccount',
                    ),
                ),
                (
                    'contact',
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name='bank_account_links',
                        to='contacts.contact',
                    ),
                ),
                (
                    'user',
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name='bank_account_contact_links',
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                'db_table': 'bank_account_contact_links',
                'unique_together': {('bank_account', 'contact')},
                'indexes': [models.Index(fields=['user', 'contact'], name='bank_link_user_contact_idx')],
            },
        ),
        migrations.RunPython(backfill_contact_links, migrations.RunPython.noop),
    ]
