"""
Admin configuration for BBPS app.
"""
from django.contrib import admin
from apps.bbps.models import (
    Bill,
    BillPayment,
    BbpsApiAuditLog,
    BbpsBillerAdditionalInfoSchema,
    BbpsBillerCcf1Config,
    BbpsBillerInputParam,
    BbpsBillerMaster,
    BbpsCategoryCommissionRule,
    BbpsCommissionAudit,
    BbpsBillerPaymentChannelLimit,
    BbpsBillerPaymentModeLimit,
    BbpsBillerPlanMeta,
    BbpsComplaint,
    BbpsComplaintEvent,
    BbpsDepositEnquirySnapshot,
    BbpsFetchSession,
    BbpsPaymentAttempt,
    BbpsPlanPullRun,
    BbpsPushWebhookEvent,
    BbpsProviderBillerMap,
    BbpsServiceCategory,
    BbpsServiceProvider,
    BbpsStatusPollLog,
    Biller,
)


@admin.register(Biller)
class BillerAdmin(admin.ModelAdmin):
    list_display = ['name', 'category', 'biller_id', 'is_active', 'created_at']
    list_filter = ['category', 'is_active', 'created_at']
    search_fields = ['name', 'biller_id']


@admin.register(Bill)
class BillAdmin(admin.ModelAdmin):
    list_display = ['biller', 'amount', 'due_date', 'status', 'created_at']
    list_filter = ['status', 'created_at']
    search_fields = ['biller__name']


@admin.register(BillPayment)
class BillPaymentAdmin(admin.ModelAdmin):
    list_display = ['service_id', 'user', 'biller', 'amount', 'status', 'created_at']
    list_filter = ['status', 'bill_type', 'created_at']
    search_fields = ['service_id', 'user__user_id', 'biller']


@admin.register(BbpsBillerMaster)
class BbpsBillerMasterAdmin(admin.ModelAdmin):
    list_display = [
        'biller_id',
        'biller_name',
        'biller_category',
        'biller_status',
        'biller_fetch_requirement',
        'biller_support_bill_validation',
        'last_synced_at',
    ]
    list_filter = [
        'biller_status',
        'biller_fetch_requirement',
        'biller_support_bill_validation',
        'is_stale',
    ]
    search_fields = ['biller_id', 'biller_name', 'biller_category']


@admin.register(BbpsServiceCategory)
class BbpsServiceCategoryAdmin(admin.ModelAdmin):
    list_display = ['code', 'name', 'is_active', 'display_order', 'updated_at']
    list_filter = ['is_active']
    search_fields = ['code', 'name']


@admin.register(BbpsServiceProvider)
class BbpsServiceProviderAdmin(admin.ModelAdmin):
    list_display = ['code', 'name', 'provider_type', 'category', 'priority', 'is_active', 'updated_at']
    list_filter = ['provider_type', 'is_active', 'category']
    search_fields = ['code', 'name', 'category__code', 'category__name']


@admin.register(BbpsProviderBillerMap)
class BbpsProviderBillerMapAdmin(admin.ModelAdmin):
    list_display = ['provider', 'biller_master', 'priority', 'is_active', 'effective_from', 'effective_to']
    list_filter = ['is_active', 'provider__category']
    search_fields = ['provider__name', 'provider__code', 'biller_master__biller_id', 'biller_master__biller_name']


@admin.register(BbpsCategoryCommissionRule)
class BbpsCategoryCommissionRuleAdmin(admin.ModelAdmin):
    list_display = ['rule_code', 'category', 'commission_type', 'value', 'min_commission', 'max_commission', 'is_active']
    list_filter = ['commission_type', 'is_active', 'category']
    search_fields = ['rule_code', 'category__code', 'category__name']


@admin.register(BbpsCommissionAudit)
class BbpsCommissionAuditAdmin(admin.ModelAdmin):
    list_display = ['rule', 'action', 'changed_by_user_id', 'created_at']
    list_filter = ['action']
    search_fields = ['rule__rule_code']
    readonly_fields = ['previous_snapshot', 'new_snapshot']


@admin.register(BbpsBillerInputParam)
class BbpsBillerInputParamAdmin(admin.ModelAdmin):
    list_display = ['biller', 'param_name', 'data_type', 'is_optional', 'min_length', 'max_length']
    list_filter = ['data_type', 'is_optional', 'visibility']
    search_fields = ['biller__biller_id', 'biller__biller_name', 'param_name']


@admin.register(BbpsBillerPaymentModeLimit)
class BbpsBillerPaymentModeLimitAdmin(admin.ModelAdmin):
    list_display = ['biller', 'payment_mode', 'min_amount', 'max_amount', 'is_active']
    list_filter = ['is_active', 'payment_mode']
    search_fields = ['biller__biller_id', 'payment_mode']


@admin.register(BbpsBillerPaymentChannelLimit)
class BbpsBillerPaymentChannelLimitAdmin(admin.ModelAdmin):
    list_display = ['biller', 'payment_channel', 'min_amount', 'max_amount', 'is_active']
    list_filter = ['is_active', 'payment_channel']
    search_fields = ['biller__biller_id', 'payment_channel']


@admin.register(BbpsBillerAdditionalInfoSchema)
class BbpsBillerAdditionalInfoSchemaAdmin(admin.ModelAdmin):
    list_display = ['biller', 'info_group', 'info_name', 'data_type', 'is_optional']
    list_filter = ['info_group', 'is_optional']
    search_fields = ['biller__biller_id', 'info_name']


@admin.register(BbpsBillerPlanMeta)
class BbpsBillerPlanMetaAdmin(admin.ModelAdmin):
    list_display = ['biller', 'plan_id', 'category_type', 'amount_in_rupees', 'status', 'effective_to']
    list_filter = ['status', 'category_type']
    search_fields = ['biller__biller_id', 'plan_id', 'plan_desc']


@admin.register(BbpsBillerCcf1Config)
class BbpsBillerCcf1ConfigAdmin(admin.ModelAdmin):
    list_display = ['biller', 'fee_code', 'fee_direction', 'flat_fee', 'percent_fee']
    search_fields = ['biller__biller_id', 'fee_code']


@admin.register(BbpsApiAuditLog)
class BbpsApiAuditLogAdmin(admin.ModelAdmin):
    list_display = ['endpoint_name', 'request_id', 'service_id', 'status_code', 'latency_ms', 'success', 'created_at']
    list_filter = ['endpoint_name', 'success', 'status_code']
    search_fields = ['request_id', 'service_id']
    readonly_fields = ['request_meta', 'response_meta']


@admin.register(BbpsFetchSession)
class BbpsFetchSessionAdmin(admin.ModelAdmin):
    list_display = ['id', 'user', 'biller_master', 'request_id', 'service_id', 'amount_paise', 'status', 'created_at']
    list_filter = ['status']
    search_fields = ['request_id', 'service_id', 'user__user_id', 'biller_master__biller_id']


@admin.register(BbpsPaymentAttempt)
class BbpsPaymentAttemptAdmin(admin.ModelAdmin):
    list_display = ['id', 'user', 'service_id', 'request_id', 'biller_id', 'payment_mode', 'status', 'created_at']
    list_filter = ['status', 'payment_mode', 'payment_channel']
    search_fields = ['service_id', 'request_id', 'txn_ref_id', 'idempotency_key']


@admin.register(BbpsStatusPollLog)
class BbpsStatusPollLogAdmin(admin.ModelAdmin):
    list_display = ['attempt', 'track_type', 'track_value', 'response_code', 'txn_status', 'created_at']
    list_filter = ['track_type', 'txn_status']
    search_fields = ['track_value', 'attempt__service_id']


@admin.register(BbpsComplaint)
class BbpsComplaintAdmin(admin.ModelAdmin):
    list_display = ['complaint_id', 'user', 'txn_ref_id', 'complaint_status', 'response_code', 'created_at']
    list_filter = ['complaint_status', 'response_code']
    search_fields = ['complaint_id', 'txn_ref_id', 'user__user_id']


@admin.register(BbpsComplaintEvent)
class BbpsComplaintEventAdmin(admin.ModelAdmin):
    list_display = ['complaint', 'complaint_status', 'created_at']
    search_fields = ['complaint__complaint_id', 'complaint_status']


@admin.register(BbpsPlanPullRun)
class BbpsPlanPullRunAdmin(admin.ModelAdmin):
    list_display = ['id', 'response_code', 'plan_count', 'created_at']
    search_fields = ['response_code']


@admin.register(BbpsDepositEnquirySnapshot)
class BbpsDepositEnquirySnapshotAdmin(admin.ModelAdmin):
    list_display = ['request_id', 'from_date', 'to_date', 'trans_type', 'current_balance', 'created_at']
    search_fields = ['request_id']


@admin.register(BbpsPushWebhookEvent)
class BbpsPushWebhookEventAdmin(admin.ModelAdmin):
    list_display = ['request_id', 'txn_ref_id', 'event_type', 'response_code', 'processed', 'created_at']
    list_filter = ['event_type', 'processed', 'response_code']
    search_fields = ['request_id', 'txn_ref_id']
