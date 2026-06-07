# Data fix: ensure KYC ApiMaster rows have kyc_service and is_default set.

from django.db import migrations

KYC_PROVIDER_CODES = {
    'cashfree_pan': 'pan',
    'cashfree_digilocker': 'aadhaar',
}


def fix_kyc_apimaster_rows(apps, schema_editor):
    ApiMaster = apps.get_model('integrations', 'ApiMaster')
    rows = ApiMaster.objects.filter(provider_type='kyc', is_deleted=False)
    for row in rows:
        inferred = KYC_PROVIDER_CODES.get(str(row.provider_code or '').strip().lower(), '')
        updates = []
        if inferred and not (row.kyc_service or '').strip():
            row.kyc_service = inferred
            updates.append('kyc_service')
        if updates:
            row.save(update_fields=updates)

    for service in ('pan', 'aadhaar'):
        active = ApiMaster.objects.filter(
            provider_type='kyc',
            kyc_service=service,
            is_deleted=False,
            status__in=('active', 'sandbox'),
        )
        if not active.exists():
            continue
        if not active.filter(is_default=True).exists():
            first = active.order_by('-priority', 'pk').first()
            if first:
                first.is_default = True
                first.save(update_fields=['is_default', 'updated_at'])


class Migration(migrations.Migration):

    dependencies = [
        ('integrations', '0007_apimaster_kyc_service_kyc_models'),
    ]

    operations = [
        migrations.RunPython(fix_kyc_apimaster_rows, migrations.RunPython.noop),
    ]
