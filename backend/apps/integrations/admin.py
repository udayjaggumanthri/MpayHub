from django.contrib import admin

from apps.integrations.models import ApiMaster


@admin.register(ApiMaster)
class ApiMasterAdmin(admin.ModelAdmin):
    list_display = [
        'provider_name',
        'provider_code',
        'provider_type',
        'auth_type',
        'status',
        'is_default',
        'priority',
        'updated_at',
    ]
    list_filter = ['provider_type', 'auth_type', 'status', 'is_default', 'supports_webhook']
    search_fields = ['provider_name', 'provider_code', 'base_url']
