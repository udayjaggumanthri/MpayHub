"""
Admin configuration for wallets app.
"""
from django.contrib import admin
from apps.wallets.models import Wallet, WalletTransaction, WalletMergeAudit


@admin.register(Wallet)
class WalletAdmin(admin.ModelAdmin):
    list_display = ['user', 'wallet_type', 'balance', 'held_balance', 'is_archived', 'created_at']
    list_filter = ['wallet_type', 'is_archived', 'created_at']
    search_fields = ['user__user_id', 'user__phone']
    readonly_fields = ['balance', 'held_balance', 'created_at', 'updated_at']


@admin.register(WalletTransaction)
class WalletTransactionAdmin(admin.ModelAdmin):
    list_display = ['wallet', 'amount', 'transaction_type', 'reference', 'created_at']
    list_filter = ['transaction_type', 'created_at']
    search_fields = ['wallet__user__user_id', 'reference']
    readonly_fields = ['created_at', 'updated_at']


@admin.register(WalletMergeAudit)
class WalletMergeAuditAdmin(admin.ModelAdmin):
    list_display = [
        'user', 'status', 'main_before', 'bbps_before', 'commission_before',
        'profit_before', 'merged_total', 'main_after', 'bridge_service_id', 'created_at',
    ]
    list_filter = ['status', 'created_at']
    search_fields = ['user__user_id', 'bridge_service_id']
    readonly_fields = [
        'main_before', 'bbps_before', 'commission_before', 'profit_before',
        'merged_total', 'main_after', 'bridge_service_id', 'created_at', 'updated_at',
    ]
