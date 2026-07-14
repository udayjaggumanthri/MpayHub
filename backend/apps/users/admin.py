"""
Admin configuration for users app.
"""
from django.contrib import admin
from apps.users.models import UserProfile, KYC, UserHierarchy, KycApprovalAudit


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ['user', 'full_name', 'business_name', 'created_at']
    list_filter = ['created_at']
    search_fields = ['user__user_id', 'user__phone', 'first_name', 'last_name', 'business_name']
    readonly_fields = ['created_at', 'updated_at']


@admin.register(KYC)
class KYCAdmin(admin.ModelAdmin):
    list_display = [
        'user', 'pan', 'pan_verified', 'aadhaar', 'aadhaar_verified',
        'verification_status', 'decided_by', 'decided_at', 'created_at',
    ]
    list_filter = ['pan_verified', 'aadhaar_verified', 'verification_status', 'created_at']
    search_fields = ['user__user_id', 'user__phone', 'pan', 'aadhaar']
    readonly_fields = ['created_at', 'updated_at', 'decided_at', 'decided_by', 'decision_notes']


@admin.register(KycApprovalAudit)
class KycApprovalAuditAdmin(admin.ModelAdmin):
    list_display = ['user', 'decision', 'previous_status', 'new_status', 'decided_by', 'created_at']
    list_filter = ['decision', 'created_at']
    search_fields = ['user__user_id', 'notes']
    readonly_fields = [
        'user', 'kyc', 'decision', 'previous_status', 'new_status',
        'decided_by', 'notes', 'created_at', 'updated_at',
    ]


@admin.register(UserHierarchy)
class UserHierarchyAdmin(admin.ModelAdmin):
    list_display = ['parent_user', 'child_user', 'created_at']
    list_filter = ['created_at']
    search_fields = ['parent_user__user_id', 'child_user__user_id']
    readonly_fields = ['created_at', 'updated_at']
