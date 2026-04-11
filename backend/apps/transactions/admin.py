"""
Admin configuration for transactions app.
"""
from django.contrib import admin
from apps.transactions.models import CommissionLedger, PassbookEntry, Transaction


@admin.register(Transaction)
class TransactionAdmin(admin.ModelAdmin):
    list_display = ['service_id', 'user', 'transaction_type', 'amount', 'status', 'created_at']
    list_filter = ['transaction_type', 'status', 'created_at']
    search_fields = ['service_id', 'user__user_id', 'reference']
    readonly_fields = ['created_at', 'updated_at']


@admin.register(CommissionLedger)
class CommissionLedgerAdmin(admin.ModelAdmin):
    list_display = ['reference_service_id', 'user', 'role_at_time', 'amount', 'source', 'created_at']
    list_filter = ['source', 'wallet_type', 'created_at']
    search_fields = ['reference_service_id', 'role_at_time']


@admin.register(PassbookEntry)
class PassbookEntryAdmin(admin.ModelAdmin):
    list_display = ['service_id', 'user', 'wallet_type', 'service', 'debit_amount', 'credit_amount', 'created_at']
    list_filter = ['wallet_type', 'service', 'created_at']
    search_fields = ['service_id', 'user__user_id', 'description']
    readonly_fields = ['created_at', 'updated_at']
