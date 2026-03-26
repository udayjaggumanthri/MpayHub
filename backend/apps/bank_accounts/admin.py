"""
Admin configuration for bank_accounts app.
"""
from django.contrib import admin
from apps.bank_accounts.models import BankAccount


@admin.register(BankAccount)
class BankAccountAdmin(admin.ModelAdmin):
    list_display = ['account_holder_name', 'account_number', 'bank_name', 'ifsc', 'is_verified', 'user', 'created_at']
    list_filter = ['is_verified', 'bank_name', 'created_at']
    search_fields = ['account_holder_name', 'account_number', 'ifsc', 'user__user_id']
    readonly_fields = ['created_at', 'updated_at']
