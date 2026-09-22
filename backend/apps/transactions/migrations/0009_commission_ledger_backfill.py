"""Backfill CommissionLedger.slice_key / module / entry_kind from historical rows."""
from django.db import migrations


def forwards_backfill(apps, schema_editor):
    CommissionLedger = apps.get_model('transactions', 'CommissionLedger')
    batch = []
    for row in CommissionLedger.objects.all().iterator(chunk_size=500):
        meta = row.meta if isinstance(row.meta, dict) else {}
        changed = False
        slice_key = (row.slice_key or '').strip() or str(meta.get('slice') or '').strip()
        if slice_key and row.slice_key != slice_key:
            row.slice_key = slice_key[:64]
            changed = True
        module = (row.module or '').strip()
        if not module:
            if row.source == 'profit':
                row.module = 'payin'
                row.entry_kind = 'service_fee'
            elif row.source == 'payin':
                row.module = 'payin'
                row.entry_kind = 'commission'
            else:
                row.module = row.source or 'payin'
            changed = True
        if row.wallet_type in ('commission', 'profit') and not meta.get('_legacy_wallet_type'):
            # Keep historical wallet_type for audit; new rows use main.
            pass
        if changed:
            batch.append(row)
        if len(batch) >= 200:
            CommissionLedger.objects.bulk_update(
                batch, ['slice_key', 'module', 'entry_kind']
            )
            batch = []
    if batch:
        CommissionLedger.objects.bulk_update(batch, ['slice_key', 'module', 'entry_kind'])


def backwards_noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('transactions', '0008_commission_ledger_revenue_fields'),
    ]

    operations = [
        migrations.RunPython(forwards_backfill, backwards_noop),
    ]
