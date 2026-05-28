from django.contrib import admin

from apps.core.models import SystemMaintenanceAuditLog, SystemMaintenanceConfig


@admin.register(SystemMaintenanceConfig)
class SystemMaintenanceConfigAdmin(admin.ModelAdmin):
    list_display = (
        'pk',
        'pay_in_enabled',
        'payout_enabled',
        'bbps_enabled',
        'updated_at',
        'updated_by',
    )
    readonly_fields = ('updated_at',)


@admin.register(SystemMaintenanceAuditLog)
class SystemMaintenanceAuditLogAdmin(admin.ModelAdmin):
    list_display = ('module', 'enabled', 'changed_by', 'created_at')
    list_filter = ('module', 'enabled')
    readonly_fields = ('created_at', 'updated_at')
