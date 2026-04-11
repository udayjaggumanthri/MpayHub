"""
JWT / session auth that rejects disabled (is_active=False) users.
"""
from rest_framework.authentication import SessionAuthentication
from rest_framework.exceptions import AuthenticationFailed
from rest_framework_simplejwt.authentication import JWTAuthentication


class ActiveUserJWTAuthentication(JWTAuthentication):
    """Invalidate API access for deactivated accounts while a token is still unexpired."""

    def get_user(self, validated_token):
        user = super().get_user(validated_token)
        if user is not None and not user.is_active:
            raise AuthenticationFailed('User account is disabled.')
        return user


class ActiveUserSessionAuthentication(SessionAuthentication):
    """Same for session-based API usage (e.g. browsable API)."""

    def authenticate(self, request):
        result = super().authenticate(request)
        if result is None:
            return None
        user, auth = result
        if not user.is_active:
            raise AuthenticationFailed('User account is disabled.')
        return user, auth
