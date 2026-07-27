"""Django signals for session_security activity capture."""
from django.db.models.signals import post_save
from django.dispatch import receiver


@receiver(post_save, sender='transactions.PassbookEntry')
def passbook_entry_activity(sender, instance, created, **kwargs):
    if not created:
        return
    from apps.session_security.services.activity import record_passbook_activity

    record_passbook_activity(instance)
