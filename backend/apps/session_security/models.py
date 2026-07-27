"""
Session security models: policy singleton and append-only user activity audit logs.
"""
from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models

from apps.core.models import TimestampedModel
from apps.session_security.constants import (
    EVENT_ACCESS_CONTROLS_CHANGED,
    EVENT_BBPS_PAYMENT,
    EVENT_GEO_CAPTURE_FAILED,
    EVENT_IDLE_TIMEOUT,
    EVENT_LOGIN_FAILURE,
    EVENT_LOGIN_SUCCESS,
    EVENT_LOGOUT,
    EVENT_PAYIN_CREATED,
    EVENT_PAYIN_FAILED,
    EVENT_PAYIN_SUCCESS,
    EVENT_PAYOUT_CREATED,
    EVENT_PAYOUT_FAILED,
    EVENT_PAYOUT_SUCCESS,
    EVENT_REFRESH_DENIED,
    EVENT_ROLE_CHANGED,
    EVENT_SESSION_REJECTED,
    EVENT_SESSION_REPLACED,
    EVENT_USER_DISABLED,
    EVENT_USER_ENABLED,
    EVENT_WALLET_TRANSFER,
    IDLE_TIMEOUT_DEFAULT,
    IDLE_TIMEOUT_MAX,
    IDLE_TIMEOUT_MIN,
)


class SessionSecuritySettings(models.Model):
    """
    Singleton admin-controlled session security policy (pk=1).
    """

    SINGLETON_PK = 1

    ip_location_enforcement_enabled = models.BooleanField(
        default=True,
        help_text='Require successful IP + geolocation capture on login/refresh.',
    )
    audit_logging_enabled = models.BooleanField(
        default=True,
        help_text='Persist per-user login/session and activity audit events.',
    )
    single_session_enforcement_enabled = models.BooleanField(
        default=True,
        help_text='Terminate prior sessions when a user logs in elsewhere '
        '(unless allow_concurrent_sessions).',
    )
    idle_timeout_minutes = models.PositiveSmallIntegerField(
        default=IDLE_TIMEOUT_DEFAULT,
        validators=[
            MinValueValidator(IDLE_TIMEOUT_MIN),
            MaxValueValidator(IDLE_TIMEOUT_MAX),
        ],
        help_text='Minutes of inactivity before the session expires (1–60).',
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='session_security_settings_updates',
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'session_security_settings'
        verbose_name = 'Session security settings'
        verbose_name_plural = 'Session security settings'

    def __str__(self):
        return 'Session security settings'

    def save(self, *args, **kwargs):
        self.pk = self.SINGLETON_PK
        super().save(*args, **kwargs)


class UserLoginAuditLog(TimestampedModel):
    """
    Append-only per-user activity audit trail (auth, money, admin access).

    Table name retained for backward compatibility.
    """

    EVENT_CHOICES = [
        (EVENT_LOGIN_SUCCESS, 'Login success'),
        (EVENT_LOGIN_FAILURE, 'Login failure'),
        (EVENT_LOGOUT, 'Logout'),
        (EVENT_SESSION_REPLACED, 'Session replaced'),
        (EVENT_SESSION_REJECTED, 'Session rejected'),
        (EVENT_IDLE_TIMEOUT, 'Idle timeout'),
        (EVENT_REFRESH_DENIED, 'Refresh denied'),
        (EVENT_GEO_CAPTURE_FAILED, 'Geo capture failed'),
        (EVENT_PAYIN_CREATED, 'Pay-in created'),
        (EVENT_PAYIN_SUCCESS, 'Pay-in success'),
        (EVENT_PAYIN_FAILED, 'Pay-in failed'),
        (EVENT_PAYOUT_CREATED, 'Payout created'),
        (EVENT_PAYOUT_SUCCESS, 'Payout success'),
        (EVENT_PAYOUT_FAILED, 'Payout failed'),
        (EVENT_BBPS_PAYMENT, 'BBPS payment'),
        (EVENT_WALLET_TRANSFER, 'Wallet transfer'),
        (EVENT_ACCESS_CONTROLS_CHANGED, 'Access controls changed'),
        (EVENT_ROLE_CHANGED, 'Role changed'),
        (EVENT_USER_DISABLED, 'User disabled'),
        (EVENT_USER_ENABLED, 'User enabled'),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='login_audit_logs',
    )
    phone_attempted = models.CharField(max_length=20, blank=True, default='', db_index=True)
    event_type = models.CharField(max_length=32, choices=EVENT_CHOICES, db_index=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    location = models.JSONField(default=dict, blank=True)
    user_agent = models.TextField(blank=True, default='')
    session = models.ForeignKey(
        'authentication.UserSession',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='audit_logs',
    )
    message = models.TextField(blank=True, default='')
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        db_table = 'user_login_audit_logs'
        verbose_name = 'User activity audit log'
        verbose_name_plural = 'User activity audit logs'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', 'created_at']),
            models.Index(fields=['event_type', 'created_at']),
        ]

    def __str__(self):
        who = self.user_id or self.phone_attempted or 'unknown'
        return f'{self.event_type} ({who}) at {self.created_at}'


# Semantic alias for callers / docs
UserActivityAuditLog = UserLoginAuditLog
