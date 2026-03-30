"""
Admin configuration for admin_panel app.
"""
from django.contrib import admin
from apps.admin_panel.models import Announcement, PaymentGateway, PayoutGateway


@admin.register(Announcement)
class AnnouncementAdmin(admin.ModelAdmin):
    list_display = ['title', 'priority', 'is_active', 'has_image', 'created_at']
    list_filter = ['priority', 'is_active', 'created_at']
    search_fields = ['title', 'message']

    @admin.display(boolean=True)
    def has_image(self, obj):
        return bool(obj.image)


@admin.register(PaymentGateway)
class PaymentGatewayAdmin(admin.ModelAdmin):
    list_display = ['name', 'charge_rate', 'status', 'category', 'created_at']
    list_filter = ['status', 'category', 'created_at']
    search_fields = ['name']


@admin.register(PayoutGateway)
class PayoutGatewayAdmin(admin.ModelAdmin):
    list_display = ['name', 'status', 'created_at']
    list_filter = ['status', 'created_at']
    search_fields = ['name']
