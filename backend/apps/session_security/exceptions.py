"""Domain exceptions for session security (fail-closed login)."""


class SessionSecurityError(Exception):
    """Base session-security error."""

    code = 'SESSION_SECURITY_ERROR'
    status_code = 400

    def __init__(self, message: str, *, code: str | None = None):
        super().__init__(message)
        self.message = message
        if code:
            self.code = code


class GeoCaptureFailed(SessionSecurityError):
    code = 'GEO_CAPTURE_FAILED'
    status_code = 403


class IpCaptureFailed(SessionSecurityError):
    code = 'IP_CAPTURE_FAILED'
    status_code = 403


class SessionInvalid(SessionSecurityError):
    code = 'SESSION_INVALID'
    status_code = 401


class SessionReplaced(SessionSecurityError):
    code = 'SESSION_REPLACED'
    status_code = 401


class SessionIdleTimeout(SessionSecurityError):
    code = 'SESSION_IDLE'
    status_code = 401
