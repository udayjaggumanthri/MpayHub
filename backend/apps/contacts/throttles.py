"""Rate limits for contact endpoints (authenticated per-user)."""

from rest_framework.throttling import UserRateThrottle


class ContactUserThrottle(UserRateThrottle):
    scope = 'contacts'
