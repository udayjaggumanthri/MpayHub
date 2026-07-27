# Generated manually — deterministic non-destructive identity backfill

from django.db import migrations


ROLE_DISPLAY_PREFIX = {
    'Admin': 'A',
    'Super Distributor': 'SD',
    'Master Distributor': 'MD',
    'Distributor': 'D',
    'Retailer': 'R',
}

MEMBER_ID_PREFIX = 'MPH'
MIN_PAD = 6


def _pad(n: int) -> str:
    width = max(MIN_PAD, len(str(n)))
    return f'{n:0{width}d}'


def _member_id(n: int) -> str:
    return f'{MEMBER_ID_PREFIX}{_pad(n)}'


def _display_code(role: str, n: int) -> str:
    prefix = ROLE_DISPLAY_PREFIX.get(role) or 'R'
    return f'{prefix}{_pad(n)}'


def backfill_member_identity(apps, schema_editor):
    User = apps.get_model('authentication', 'User')
    MemberNumberSequence = apps.get_model('authentication', 'MemberNumberSequence')

    # Idempotent: only fill rows still missing member_number.
    pending = list(
        User.objects.filter(member_number__isnull=True).order_by('created_at', 'id')
    )
    if not pending and not User.objects.filter(member_number__isnull=False).exists():
        # Empty DB — still seed sequence at 1
        MemberNumberSequence.objects.update_or_create(
            key='global',
            defaults={'next_value': 1},
        )
        return

    max_existing = (
        User.objects.exclude(member_number__isnull=True)
        .order_by('-member_number')
        .values_list('member_number', flat=True)
        .first()
    ) or 0

    next_n = int(max_existing) + 1
    for user in pending:
        # Leave user_id, password, mpin, FKs untouched.
        user.member_number = next_n
        user.member_id = _member_id(next_n)
        user.display_code = _display_code(user.role, next_n)
        user.save(update_fields=['member_number', 'member_id', 'display_code'])
        next_n += 1

    final_max = (
        User.objects.exclude(member_number__isnull=True)
        .order_by('-member_number')
        .values_list('member_number', flat=True)
        .first()
    ) or 0

    MemberNumberSequence.objects.update_or_create(
        key='global',
        defaults={'next_value': int(final_max) + 1},
    )


def noop_reverse(apps, schema_editor):
    # Do not wipe allocated identity on reverse; operational rollback uses backup.
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('authentication', '0008_user_member_identity_fields'),
    ]

    operations = [
        migrations.RunPython(backfill_member_identity, noop_reverse),
    ]
