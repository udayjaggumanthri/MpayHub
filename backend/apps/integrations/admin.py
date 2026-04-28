from django.contrib import admin

from apps.integrations.models import (
    ApiMaster,
    BillAvenueAgentProfile,
    BillAvenueConfig,
    BillAvenueModeChannelPolicy,
)


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


@admin.register(BillAvenueConfig)
class BillAvenueConfigAdmin(admin.ModelAdmin):
    list_display = [
        'name',
        'mode',
        'api_format',
        'crypto_key_derivation',
        'enc_request_encoding',
        'enabled',
        'is_active',
        'mdm_refresh_hours',
        'mdm_max_calls_per_day',
        'updated_at',
    ]
    list_filter = ['mode', 'api_format', 'crypto_key_derivation', 'enc_request_encoding', 'enabled', 'is_active']
    search_fields = ['name', 'base_url', 'institute_id']
    readonly_fields = ['activated_at']


@admin.register(BillAvenueAgentProfile)
class BillAvenueAgentProfileAdmin(admin.ModelAdmin):
    list_display = [
        'name',
        'config',
        'agent_id',
        'init_channel',
        'enabled',
        'require_ip',
        'require_mac',
    ]
    list_filter = ['init_channel', 'enabled', 'require_ip', 'require_mac', 'require_imei']
    search_fields = ['name', 'agent_id', 'config__name']


@admin.register(BillAvenueModeChannelPolicy)
class BillAvenueModeChannelPolicyAdmin(admin.ModelAdmin):
    list_display = [
        'config',
        'payment_mode',
        'payment_channel',
        'action',
        'biller_id',
        'biller_category',
        'enabled',
    ]
    list_filter = ['action', 'enabled', 'payment_channel']
    search_fields = ['payment_mode', 'payment_channel', 'biller_id', 'biller_category', 'config__name']
