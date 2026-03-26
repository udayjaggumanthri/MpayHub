"""
Admin configuration for authentication app.
"""
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.utils.html import format_html
from apps.authentication.models import User, OTP, UserSession
from apps.users.models import UserProfile, KYC


class UserProfileInline(admin.StackedInline):
    """Inline admin for UserProfile."""
    model = UserProfile
    can_delete = False
    verbose_name_plural = 'Profile Information'
    fk_name = 'user'
    fields = ('first_name', 'last_name', 'alternate_phone', 'business_name', 'business_address')
    extra = 0


class KYCInline(admin.StackedInline):
    """Inline admin for KYC."""
    model = KYC
    can_delete = False
    verbose_name_plural = 'KYC Information'
    fk_name = 'user'
    fields = ('pan', 'pan_verified', 'aadhaar', 'aadhaar_verified', 'verification_status')
    readonly_fields = ('pan_verified', 'aadhaar_verified', 'pan_verified_at', 'aadhaar_verified_at')
    extra = 0


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    """Enhanced User admin with profile and KYC inline editing."""
    list_display = ['user_id', 'phone', 'email', 'get_full_name', 'role', 'is_active', 'created_at', 'view_actions']
    list_filter = ['role', 'is_active', 'is_staff', 'is_superuser', 'created_at']
    search_fields = ['user_id', 'phone', 'email', 'first_name', 'last_name']
    list_editable = ['is_active']  # Allow quick editing of is_active
    ordering = ['-created_at']
    
    # Add inlines for related models
    inlines = [UserProfileInline, KYCInline]
    
    fieldsets = (
        ('Authentication', {
            'fields': ('phone', 'email', 'password', 'user_id', 'mpin_status')
        }),
        ('Personal Information', {
            'fields': ('first_name', 'last_name')
        }),
        ('Account Settings', {
            'fields': ('role', 'is_active', 'is_staff', 'is_superuser')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at', 'last_login'),
            'classes': ('collapse',)
        }),
    )
    
    add_fieldsets = (
        ('Create User', {
            'classes': ('wide',),
            'fields': ('phone', 'email', 'password1', 'password2', 'first_name', 'last_name', 'role'),
        }),
    )
    
    def get_readonly_fields(self, request, obj=None):
        """Make user_id readonly, but allow editing other fields."""
        readonly = ['user_id', 'created_at', 'updated_at', 'last_login', 'mpin_status']
        if obj:  # Editing an existing object
            readonly.append('phone')  # Don't allow changing phone after creation
        return readonly
    
    def mpin_status(self, obj):
        """Display MPIN status."""
        if obj.mpin_hash:
            return format_html('<span style="color: green;">✓ MPIN Set</span>')
        return format_html('<span style="color: red;">✗ MPIN Not Set</span>')
    mpin_status.short_description = 'MPIN Status'
    
    def get_fieldsets(self, request, obj=None):
        """Return fieldsets - mpin is handled as a form field, not in fieldsets."""
        # Don't modify fieldsets - mpin will be added via get_form
        # Django will render it, but it won't be in the organized fieldsets
        # That's okay - it will still appear in the form
        return super().get_fieldsets(request, obj)
    
    def get_form(self, request, obj=None, **kwargs):
        """Add MPIN field to the form."""
        # Get the base form first - this validates fieldsets against model fields
        form = super().get_form(request, obj, **kwargs)
        
        # Add MPIN field for setting/updating MPIN
        from django import forms
        from django.core.validators import RegexValidator
        
        # Create a new form class that extends the base form
        class MPINForm(form):
            mpin = forms.CharField(
                max_length=6,
                min_length=6,
                required=not obj,  # Required for new users, optional for existing users
                help_text='Enter 6-digit MPIN (required for new users).',
                widget=forms.PasswordInput(attrs={
                    'placeholder': 'Enter MPIN (6 digits)',
                    'maxlength': '6',
                    'minlength': '6',
                    'pattern': '[0-9]{6}',
                    'required': not obj  # HTML5 required attribute
                }),
                label='MPIN',
                validators=[RegexValidator(
                    regex=r'^\d{6}$',
                    message='MPIN must be exactly 6 digits.'
                )]
            )
            
            def __init__(self, *args, **kwargs):
                super().__init__(*args, **kwargs)
                # For new users (no instance), MPIN is required
                if not self.instance or not self.instance.pk:
                    self.fields['mpin'].required = True
                    self.fields['mpin'].help_text = 'Enter 6-digit MPIN (required).'
                else:
                    # For existing users, MPIN is optional (can update or leave blank)
                    self.fields['mpin'].required = False
                    if self.instance.mpin_hash:
                        self.fields['mpin'].help_text = 'Enter new 6-digit MPIN to change. Leave blank to keep current MPIN.'
                    else:
                        self.fields['mpin'].required = True
                        self.fields['mpin'].help_text = 'MPIN is required. Please enter a 6-digit MPIN.'
        
        return MPINForm
    
    def view_actions(self, obj):
        """Display action buttons in list view."""
        from django.urls import reverse
        if obj.pk:
            edit_url = reverse('admin:authentication_user_change', args=[obj.pk])
            delete_url = reverse('admin:authentication_user_delete', args=[obj.pk])
            return format_html(
                '<a class="button" href="{}" style="margin-right: 5px; padding: 5px 10px; background: #417690; color: white; text-decoration: none; border-radius: 3px;">Edit</a> '
                '<a class="button" href="{}" style="padding: 5px 10px; background-color: #ba2121; color: white; text-decoration: none; border-radius: 3px;">Delete</a>',
                edit_url,
                delete_url
            )
        return '-'
    view_actions.short_description = 'Actions'
    view_actions.allow_tags = True
    
    def has_delete_permission(self, request, obj=None):
        """Allow deletion for superusers."""
        return request.user.is_superuser
    
    def delete_model(self, request, obj):
        """Prevent deleting yourself."""
        if obj.id == request.user.id:
            from django.contrib import messages
            messages.error(request, 'You cannot delete your own account.')
            return
        super().delete_model(request, obj)
    
    def get_full_name(self, obj):
        """Display full name from User or UserProfile."""
        if obj.first_name or obj.last_name:
            return f"{obj.first_name} {obj.last_name}".strip()
        # Try to get from profile
        try:
            if hasattr(obj, 'profile') and obj.profile:
                return obj.profile.full_name
        except:
            pass
        return '-'
    get_full_name.short_description = 'Full Name'
    
    def get_queryset(self, request):
        """Optimize queryset with related objects."""
        qs = super().get_queryset(request)
        return qs.select_related('profile', 'kyc').prefetch_related('profile', 'kyc')
    
    def save_model(self, request, obj, form, change):
        """Save user and create profile if it doesn't exist."""
        # Get MPIN from form
        mpin = form.cleaned_data.get('mpin', '').strip()
        
        # For new users, MPIN is mandatory
        if not change:  # Creating a new user
            if not mpin or len(mpin) != 6 or not mpin.isdigit():
                from django.core.exceptions import ValidationError
                raise ValidationError('MPIN is required and must be exactly 6 digits for new users.')
        
        # Save user first
        super().save_model(request, obj, form, change)
        
        # Handle MPIN (mandatory for new users, optional for updates)
        if mpin and len(mpin) == 6 and mpin.isdigit():
            obj.set_mpin(mpin)
        elif not change:
            # New user without MPIN - this should not happen due to form validation, but double-check
            from django.core.exceptions import ValidationError
            raise ValidationError('MPIN is required for new users.')
        
        # Ensure profile exists
        if not hasattr(obj, 'profile') or not obj.profile:
            UserProfile.objects.get_or_create(
                user=obj,
                defaults={
                    'first_name': obj.first_name or '',
                    'last_name': obj.last_name or ''
                }
            )
        # Ensure KYC exists
        if not hasattr(obj, 'kyc') or not obj.kyc:
            KYC.objects.get_or_create(user=obj)


@admin.register(OTP)
class OTPAdmin(admin.ModelAdmin):
    list_display = ['phone', 'code', 'purpose', 'is_used', 'expires_at', 'created_at']
    list_filter = ['purpose', 'is_used', 'created_at']
    search_fields = ['phone', 'code']
    readonly_fields = ['created_at', 'updated_at']


@admin.register(UserSession)
class UserSessionAdmin(admin.ModelAdmin):
    list_display = ['user', 'is_active', 'expires_at', 'created_at']
    list_filter = ['is_active', 'created_at']
    search_fields = ['user__user_id', 'user__phone']
    readonly_fields = ['created_at', 'updated_at']
