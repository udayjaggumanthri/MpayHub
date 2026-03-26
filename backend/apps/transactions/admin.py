"""
Admin configuration for transactions app.
"""
from django.contrib import admin
from apps.transactions.models import Transaction, PassbookEntry


@admin.register(Transaction)
class TransactionAdmin(admin.ModelAdmin):
    list_display = ['service_id', 'user', 'transaction_type', 'amount', 'status', 'created_at']
    list_filter = ['transaction_type', 'status', 'created_at']
    search_fields = ['service_id', 'user__user_id', 'reference']
    readonly_fields = ['created_at', 'updated_at']


@admin.register(PassbookEntry)
class PassbookEntryAdmin(admin.ModelAdmin):
    list_display = ['service_id', 'user', 'service', 'debit_amount', 'credit_amount', 'created_at']
    list_filter = ['service', 'created_at']
    search_fields = ['service_id', 'user__user_id', 'description']
    readonly_fields = ['created_at', 'updated_at']
