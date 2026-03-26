"""
SMS service integration for sending OTP and notifications.
"""
import requests
from django.conf import settings
from apps.integrations.base import BaseIntegration


class SMSService(BaseIntegration):
    """
    SMS service for sending OTP and notifications.
    Supports multiple providers (MSG91, Twilio, etc.) with fallback to console in development.
    """
    
    def __init__(self):
        self.api_key = getattr(settings, 'SMS_API_KEY', None)
        self.api_url = getattr(settings, 'SMS_API_URL', None)
        self.provider = getattr(settings, 'SMS_PROVIDER', 'console')
        super().__init__()
    
    def _load_config(self):
        """Load SMS configuration."""
        # Configuration is loaded in __init__
        pass
    
    def is_available(self):
        """Check if SMS service is available."""
        if settings.DEBUG:
            return True  # Always available in debug mode (console output)
        return self.api_key and self.api_url is not None
    
    def handle_error(self, error):
        """Handle SMS service errors."""
        # Log error (in production, use proper logging)
        print(f"SMS Service Error: {error}")
    
    def send_otp(self, phone, otp_code, purpose='password-reset'):
        """
        Send OTP to phone number.
        
        Args:
            phone: Phone number (10 digits)
            otp_code: OTP code to send
            purpose: Purpose of OTP (password-reset, aadhaar-verification, etc.)
        """
        if not self.is_available():
            if settings.DEBUG:
                print(f"[SMS] OTP for {phone}: {otp_code} (Purpose: {purpose})")
            return
        
        # In development, just print to console
        if settings.DEBUG:
            print(f"[SMS] OTP for {phone}: {otp_code} (Purpose: {purpose})")
            return
        
        # Production: Send via actual SMS provider
        try:
            if self.provider == 'msg91':
                self._send_via_msg91(phone, otp_code, purpose)
            elif self.provider == 'twilio':
                self._send_via_twilio(phone, otp_code, purpose)
            else:
                # Default: Just log
                print(f"[SMS] OTP for {phone}: {otp_code}")
        except Exception as e:
            self.handle_error(e)
            # Don't raise exception - OTP is still valid even if SMS fails
    
    def _send_via_msg91(self, phone, otp_code, purpose):
        """Send OTP via MSG91."""
        # Implement MSG91 integration
        # This is a placeholder - implement actual API call
        pass
    
    def _send_via_twilio(self, phone, otp_code, purpose):
        """Send OTP via Twilio."""
        # Implement Twilio integration
        # This is a placeholder - implement actual API call
        pass
    
    def send_notification(self, phone, message):
        """
        Send notification SMS.
        
        Args:
            phone: Phone number
            message: Message to send
        """
        if not self.is_available():
            if settings.DEBUG:
                print(f"[SMS] Notification to {phone}: {message}")
            return
        
        if settings.DEBUG:
            print(f"[SMS] Notification to {phone}: {message}")
            return
        
        # Production: Send via actual SMS provider
        try:
            if self.provider == 'msg91':
                self._send_notification_via_msg91(phone, message)
            elif self.provider == 'twilio':
                self._send_notification_via_twilio(phone, message)
        except Exception as e:
            self.handle_error(e)
    
    def _send_notification_via_msg91(self, phone, message):
        """Send notification via MSG91."""
        pass
    
    def _send_notification_via_twilio(self, phone, message):
        """Send notification via Twilio."""
        pass
