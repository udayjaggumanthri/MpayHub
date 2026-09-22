"""
Data migration: fold bbps / commission / profit balances into main.

Uses apps.wallets.consolidation.merge_all for paisa-level conservation.
Historical PassbookEntry rows are never rewritten.
"""
from django.db import migrations


def forwards_merge(apps, schema_editor):
    # Import live consolidation helpers (same code path as management commands).
    from apps.wallets.consolidation import merge_all

    merge_all()


def backwards_rollback(apps, schema_editor):
    from apps.wallets.consolidation import rollback_user
    from apps.wallets.models import WalletMergeAudit

    for audit in WalletMergeAudit.objects.filter(status='merged').select_related('user').order_by('-id'):
        rollback_user(audit)


class Migration(migrations.Migration):

    dependencies = [
        ('wallets', '0004_wallet_held_balance_and_merge_audit'),
        ('transactions', '0006_profit_wallet_enterprise'),
    ]

    operations = [
        migrations.RunPython(forwards_merge, backwards_rollback),
    ]
