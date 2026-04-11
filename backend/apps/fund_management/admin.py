"""
Admin configuration for fund management app.
"""
from django.contrib import admin
from apps.fund_management.models import LoadMoney, Payout, PayInPackage


@admin.register(PayInPackage)
class PayInPackageAdmin(admin.ModelAdmin):
    list_display = [
        'display_name', 'code', 'provider', 'min_amount', 'max_amount_per_txn',
        'is_active', 'sort_order',
    ]
    list_filter = ['is_active', 'provider']
    search_fields = ['code', 'display_name']
    ordering = ['sort_order', 'display_name']


@admin.register(LoadMoney)
class LoadMoneyAdmin(admin.ModelAdmin):
    list_display = ['transaction_id', 'user', 'amount', 'package', 'gateway', 'status', 'created_at']
    list_filter = ['status', 'gateway', 'created_at']
    search_fields = ['transaction_id', 'user__user_id', 'user__phone']
    readonly_fields = ['transaction_id', 'created_at', 'updated_at']


@admin.register(Payout)
class PayoutAdmin(admin.ModelAdmin):
    list_display = ['transaction_id', 'user', 'amount', 'status', 'created_at']
    list_filter = ['status', 'created_at']
    search_fields = ['transaction_id', 'user__user_id', 'user__phone']
    readonly_fields = ['transaction_id', 'created_at', 'updated_at']
