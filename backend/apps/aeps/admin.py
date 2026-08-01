from django.contrib import admin

from apps.aeps import models


@admin.register(models.AepsProviderConfig)
class AepsProviderConfigAdmin(admin.ModelAdmin):
    list_display = ('name', 'environment', 'is_active', 'super_merchant_login_id', 'updated_at')
    list_filter = ('environment', 'is_active')


@admin.register(models.AepsEntitlement)
class AepsEntitlementAdmin(admin.ModelAdmin):
    list_display = ('user', 'enabled', 'source', 'assigned_at')
    list_filter = ('enabled', 'source')
    search_fields = ('user__phone', 'user__user_id')


@admin.register(models.AepsAccessRequest)
class AepsAccessRequestAdmin(admin.ModelAdmin):
    list_display = ('user', 'status', 'created_at', 'reviewed_at')
    list_filter = ('status',)


@admin.register(models.AepsMerchantProfile)
class AepsMerchantProfileAdmin(admin.ModelAdmin):
    list_display = ('merchant_login_id', 'user', 'stage', 'device_ready', 'updated_at')
    list_filter = ('stage', 'device_ready')
    search_fields = ('merchant_login_id', 'user__phone')


@admin.register(models.AepsTransaction)
class AepsTransactionAdmin(admin.ModelAdmin):
    list_display = ('merchant_tran_id', 'product', 'status', 'amount', 'bank_rrn', 'created_at')
    list_filter = ('product', 'status')
    search_fields = ('merchant_tran_id', 'bank_rrn', 'fp_transaction_id')


admin.site.register(models.AepsDaily2FA)
admin.site.register(models.AepsBankIinCache)
admin.site.register(models.AepsReconBatch)
admin.site.register(models.AepsReconItem)
admin.site.register(models.AepsApiAuditLog)
