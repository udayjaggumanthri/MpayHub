from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from apps.users.hierarchy_scope_cache import invalidate_hierarchy_scope_cache
from apps.users.models import UserHierarchy


@receiver(post_save, sender=UserHierarchy)
@receiver(post_delete, sender=UserHierarchy)
def invalidate_hierarchy_scope_on_change(sender, instance, **kwargs):
    invalidate_hierarchy_scope_cache(instance.parent_user_id, instance.child_user_id)
