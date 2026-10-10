from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('bbps', '0019_bbps_wallet_hold_fields'),
    ]

    operations = [
        migrations.AddField(
            model_name='bbpspaymentattempt',
            name='last_status_checked_at',
            field=models.DateTimeField(
                blank=True,
                db_index=True,
                help_text='Last time transaction-status was called for this attempt.',
                null=True,
            ),
        ),
        migrations.AddField(
            model_name='bbpsstatuspolllog',
            name='requested_by',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=models.deletion.SET_NULL,
                related_name='bbps_status_polls_requested',
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AddField(
            model_name='bbpsstatuspolllog',
            name='source',
            field=models.CharField(
                blank=True,
                db_index=True,
                default='',
                help_text='Who asked: job, user, or admin.',
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name='bbpsstatuspolllog',
            name='status_changed',
            field=models.BooleanField(default=False),
        ),
    ]
