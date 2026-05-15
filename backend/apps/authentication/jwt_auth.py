"""
JWT / session auth that rejects users who may not log in (disabled without pay-in exception).
"""
from apps.core.financial_access import user_may_login
from rest_framework.authentication import SessionAuthentication
from rest_framework.exceptions import AuthenticationFailed
from rest_framework_simplejwt.authentication import JWTAuthentication


class ActiveUserJWTAuthentication(JWTAuthentication):
    """Invalidate API access when account is disabled and pay-in-only exception does not apply."""

    def get_user(self, validated_token):
        user = super().get_user(validated_token)
        if user is not None and not user_may_login(user):
            raise AuthenticationFailed('User account is disabled.')
        return user


class ActiveUserSessionAuthentication(SessionAuthentication):
    """Same for session-based API usage (e.g. browsable API)."""

    def authenticate(self, request):
        result = super().authenticate(request)
        if result is None:
            return None
        user, auth = result
        if not user_may_login(user):
            raise AuthenticationFailed('User account is disabled.')
        return user, auth
