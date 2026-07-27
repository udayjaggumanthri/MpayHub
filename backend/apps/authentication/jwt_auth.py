"""
JWT / session auth that rejects users who may not log in (disabled without pay-in exception)
and enforces server-side UserSession (sid claim) + idle timeout.
"""
from django.utils.translation import gettext_lazy as _
from rest_framework.authentication import SessionAuthentication
from rest_framework.exceptions import AuthenticationFailed
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.exceptions import InvalidToken
from rest_framework_simplejwt.settings import api_settings
from rest_framework_simplejwt.utils import get_md5_hash_password

from apps.core.financial_access import user_may_login


class ActiveUserJWTAuthentication(JWTAuthentication):
    """
    Authenticate JWT users who may log in (active, or disabled with pay-in-only exception).

    Does not call ``JWTAuthentication.get_user`` directly — the parent rejects any
    ``is_active=False`` user before pay-in exception can apply.

    Also validates the opaque session id claim (``sid``) against ``UserSession``.
    """

    def authenticate(self, request):
        result = super().authenticate(request)
        if result is None:
            return None
        user, validated_token = result
        try:
            from apps.session_security.exceptions import SessionSecurityError
            from apps.session_security.services.facade import get_facade

            get_facade().authenticate_access(request, validated_token, user)
        except SessionSecurityError as exc:
            raise AuthenticationFailed(
                detail={'code': exc.code, 'message': exc.message},
                code=exc.code,
            ) from exc
        return user, validated_token

    def get_user(self, validated_token):
        try:
            user_id = validated_token[api_settings.USER_ID_CLAIM]
        except KeyError as e:
            raise InvalidToken(
                _('Token contained no recognizable user identification')
            ) from e

        try:
            user = self.user_model.objects.get(**{api_settings.USER_ID_FIELD: user_id})
        except self.user_model.DoesNotExist as e:
            raise AuthenticationFailed(_('User not found'), code='user_not_found') from e

        if not user_may_login(user):
            raise AuthenticationFailed(_('User account is disabled.'), code='user_inactive')

        if api_settings.CHECK_REVOKE_TOKEN:
            if validated_token.get(api_settings.REVOKE_TOKEN_CLAIM) != get_md5_hash_password(
                user.password
            ):
                raise AuthenticationFailed(
                    _("The user's password has been changed."), code='password_changed'
                )

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
