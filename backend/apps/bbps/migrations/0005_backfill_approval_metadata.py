from django.db import migrations


def backfill_approval_metadata(apps, schema_editor):
    ServiceProvider = apps.get_model('bbps', 'BbpsServiceProvider')
    ProviderMap = apps.get_model('bbps', 'BbpsProviderBillerMap')

    for row in ServiceProvider.objects.all():
        md = dict(row.metadata or {})
        if 'approval_status' not in md:
            md['approval_status'] = 'approved' if row.is_active else 'pending'
        if 'auto_synced' not in md:
            md['auto_synced'] = False
        row.metadata = md
        row.save(update_fields=['metadata', 'updated_at'])

    for row in ProviderMap.objects.all():
        md = dict(row.metadata or {})
        if 'approval_status' not in md:
            md['approval_status'] = 'approved' if row.is_active else 'pending'
        if 'auto_synced' not in md:
            md['auto_synced'] = False
        row.metadata = md
        row.save(update_fields=['metadata', 'updated_at'])


def noop(apps, schema_editor):
    return


class Migration(migrations.Migration):
    dependencies = [
        ('bbps', '0004_bbpscategorycommissionrule_bbpsservicecategory_and_more'),
    ]

    operations = [
        migrations.RunPython(backfill_approval_metadata, noop),
    ]
