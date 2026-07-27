from django.contrib import admin

from apps.session_security.models import SessionSecuritySettings, UserLoginAuditLog


@admin.register(SessionSecuritySettings)
class SessionSecuritySettingsAdmin(admin.ModelAdmin):
    list_display = (
        'pk',
        'ip_location_enforcement_enabled',
        'audit_logging_enabled',
        'single_session_enforcement_enabled',
        'idle_timeout_minutes',
        'updated_at',
    )


@admin.register(UserLoginAuditLog)
class UserLoginAuditLogAdmin(admin.ModelAdmin):
    list_display = ('event_type', 'user', 'phone_attempted', 'ip_address', 'created_at')
    list_filter = ('event_type',)
    search_fields = ('phone_attempted', 'message', 'user__phone', 'user__display_code')
    readonly_fields = (
        'user',
        'phone_attempted',
        'event_type',
        'ip_address',
        'location',
        'user_agent',
        'session',
        'message',
        'metadata',
        'created_at',
        'updated_at',
    )
