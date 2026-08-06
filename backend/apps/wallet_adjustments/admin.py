from django.contrib import admin

from apps.wallet_adjustments.models import WalletAdjustment


@admin.register(WalletAdjustment)
class WalletAdjustmentAdmin(admin.ModelAdmin):
    list_display = (
        'adjustment_id',
        'user',
        'wallet_type',
        'adjustment_type',
        'amount',
        'reference_number',
        'status',
        'adjusted_by_name',
        'created_at',
    )
    list_filter = ('wallet_type', 'adjustment_type', 'status', 'reason_category')
    search_fields = (
        'adjustment_id',
        'reference_number',
        'user__phone',
        'user__user_id',
        'user__display_code',
        'remarks',
    )
    readonly_fields = (
        'adjustment_id',
        'user',
        'wallet_type',
        'adjustment_type',
        'amount',
        'reference_number',
        'reason_category',
        'remarks',
        'balance_before',
        'balance_after',
        'passbook_entry',
        'wallet_transaction',
        'adjusted_by',
        'adjusted_by_name',
        'status',
        'failure_reason',
        'created_at',
        'updated_at',
    )
    ordering = ('-created_at',)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
