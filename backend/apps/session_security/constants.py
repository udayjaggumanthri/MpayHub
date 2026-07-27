"""Constants for session security / user activity audit."""

SESSION_CLAIM = 'sid'

# Auth / session
EVENT_LOGIN_SUCCESS = 'login_success'
EVENT_LOGIN_FAILURE = 'login_failure'
EVENT_LOGOUT = 'logout'
EVENT_SESSION_REPLACED = 'session_replaced'
EVENT_SESSION_REJECTED = 'session_rejected'
EVENT_IDLE_TIMEOUT = 'idle_timeout'
EVENT_REFRESH_DENIED = 'refresh_denied'
EVENT_GEO_CAPTURE_FAILED = 'geo_capture_failed'

# Money
EVENT_PAYIN_CREATED = 'payin_created'
EVENT_PAYIN_SUCCESS = 'payin_success'
EVENT_PAYIN_FAILED = 'payin_failed'
EVENT_PAYOUT_CREATED = 'payout_created'
EVENT_PAYOUT_SUCCESS = 'payout_success'
EVENT_PAYOUT_FAILED = 'payout_failed'
EVENT_BBPS_PAYMENT = 'bbps_payment'
EVENT_WALLET_TRANSFER = 'wallet_transfer'

# Admin
EVENT_ACCESS_CONTROLS_CHANGED = 'access_controls_changed'
EVENT_ROLE_CHANGED = 'role_changed'
EVENT_USER_DISABLED = 'user_disabled'
EVENT_USER_ENABLED = 'user_enabled'

# Account / product actions (non-auth, non-money settlement)
EVENT_CONTACT_CREATED = 'contact_created'
EVENT_CONTACT_UPDATED = 'contact_updated'
EVENT_CONTACT_DELETED = 'contact_deleted'
EVENT_REPORT_VIEWED = 'report_viewed'
EVENT_BANK_ACCOUNT_ADDED = 'bank_account_added'
EVENT_BANK_ACCOUNT_UPDATED = 'bank_account_updated'
EVENT_BANK_ACCOUNT_DELETED = 'bank_account_deleted'

AUTH_EVENTS = frozenset(
    {
        EVENT_LOGIN_SUCCESS,
        EVENT_LOGIN_FAILURE,
        EVENT_LOGOUT,
        EVENT_SESSION_REPLACED,
        EVENT_SESSION_REJECTED,
        EVENT_IDLE_TIMEOUT,
        EVENT_REFRESH_DENIED,
        EVENT_GEO_CAPTURE_FAILED,
    }
)
MONEY_EVENTS = frozenset(
    {
        EVENT_PAYIN_CREATED,
        EVENT_PAYIN_SUCCESS,
        EVENT_PAYIN_FAILED,
        EVENT_PAYOUT_CREATED,
        EVENT_PAYOUT_SUCCESS,
        EVENT_PAYOUT_FAILED,
        EVENT_BBPS_PAYMENT,
        EVENT_WALLET_TRANSFER,
    }
)
ADMIN_EVENTS = frozenset(
    {
        EVENT_ACCESS_CONTROLS_CHANGED,
        EVENT_ROLE_CHANGED,
        EVENT_USER_DISABLED,
        EVENT_USER_ENABLED,
    }
)
ACCOUNT_EVENTS = frozenset(
    {
        EVENT_CONTACT_CREATED,
        EVENT_CONTACT_UPDATED,
        EVENT_CONTACT_DELETED,
        EVENT_REPORT_VIEWED,
        EVENT_BANK_ACCOUNT_ADDED,
        EVENT_BANK_ACCOUNT_UPDATED,
        EVENT_BANK_ACCOUNT_DELETED,
    }
)

CATEGORY_AUTH = 'auth'
CATEGORY_MONEY = 'money'
CATEGORY_ADMIN = 'admin'
CATEGORY_ACCOUNT = 'account'
CATEGORY_ALL = 'all'

TERMINATION_REPLACED = 'replaced'
TERMINATION_LOGOUT = 'logout'
TERMINATION_IDLE = 'idle'
TERMINATION_ADMIN = 'admin'

IDLE_TIMEOUT_MIN = 1
IDLE_TIMEOUT_MAX = 60
IDLE_TIMEOUT_DEFAULT = 5

ACTIVITY_TOUCH_THROTTLE_SECONDS = 30

CACHE_SETTINGS_KEY = 'session_security_settings_v1'
CACHE_SETTINGS_TTL = 15


def event_category(event_type: str) -> str:
    if event_type in AUTH_EVENTS:
        return CATEGORY_AUTH
    if event_type in MONEY_EVENTS:
        return CATEGORY_MONEY
    if event_type in ADMIN_EVENTS:
        return CATEGORY_ADMIN
    if event_type in ACCOUNT_EVENTS:
        return CATEGORY_ACCOUNT
    return CATEGORY_ALL
