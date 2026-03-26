"""
Admin configuration for contacts app.
"""
from django.contrib import admin
from apps.contacts.models import Contact


@admin.register(Contact)
class ContactAdmin(admin.ModelAdmin):
    list_display = ['name', 'phone', 'email', 'user', 'created_at']
    list_filter = ['created_at']
    search_fields = ['name', 'phone', 'email', 'user__user_id']
    readonly_fields = ['created_at', 'updated_at']
