"""
Admin configuration for BBPS app.
"""
from django.contrib import admin
from apps.bbps.models import Biller, Bill, BillPayment


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
