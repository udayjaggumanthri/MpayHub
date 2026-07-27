from django.apps import AppConfig


class SessionSecurityConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.session_security'
    verbose_name = 'Session Security'

    def ready(self):
        from apps.session_security import signals  # noqa: F401
