"""
Admin configuration for fund management app.
"""
from django.contrib import admin
from apps.fund_management.models import LoadMoney, Payout


@admin.register(LoadMoney)
class LoadMoneyAdmin(admin.ModelAdmin):
    list_display = ['transaction_id', 'user', 'amount', 'gateway', 'status', 'created_at']
    list_filter = ['status', 'gateway', 'created_at']
    search_fields = ['transaction_id', 'user__user_id', 'user__phone']
    readonly_fields = ['transaction_id', 'created_at', 'updated_at']


@admin.register(Payout)
class PayoutAdmin(admin.ModelAdmin):
    list_display = ['transaction_id', 'user', 'amount', 'status', 'created_at']
    list_filter = ['status', 'created_at']
    search_fields = ['transaction_id', 'user__user_id', 'user__phone']
    readonly_fields = ['transaction_id', 'created_at', 'updated_at']
