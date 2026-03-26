"""
Admin configuration for wallets app.
"""
from django.contrib import admin
from apps.wallets.models import Wallet, WalletTransaction


@admin.register(Wallet)
class WalletAdmin(admin.ModelAdmin):
    list_display = ['user', 'wallet_type', 'balance', 'created_at']
    list_filter = ['wallet_type', 'created_at']
    search_fields = ['user__user_id', 'user__phone']
    readonly_fields = ['balance', 'created_at', 'updated_at']


@admin.register(WalletTransaction)
class WalletTransactionAdmin(admin.ModelAdmin):
    list_display = ['wallet', 'amount', 'transaction_type', 'reference', 'created_at']
    list_filter = ['transaction_type', 'created_at']
    search_fields = ['wallet__user__user_id', 'reference']
    readonly_fields = ['created_at', 'updated_at']
