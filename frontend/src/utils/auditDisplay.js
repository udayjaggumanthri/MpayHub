/** Display audit timestamps in Asia/Kolkata with seconds (unambiguous). */

const IST = 'Asia/Kolkata';

/**
 * @param {string|Date|null|undefined} value
 * @returns {string}
 */
export function formatAuditDateTime(value) {
  if (!value) return '—';
  const d = value instanceof Date ? value : new Date(value);
  if (Number.isNaN(d.getTime())) return '—';
  try {
    const formatted = new Intl.DateTimeFormat('en-IN', {
      timeZone: IST,
      day: '2-digit',
      month: 'short',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
      hour12: true,
    }).format(d);
    return `${formatted} IST`;
  } catch {
    return d.toISOString();
  }
}

/**
 * Calendar YYYY-MM-DD in Asia/Kolkata (for Today / range filters).
 * @param {Date} [date]
 * @returns {string}
 */
export function toYmdIst(date = new Date()) {
  try {
    const parts = new Intl.DateTimeFormat('en-CA', {
      timeZone: IST,
      year: 'numeric',
      month: '2-digit',
      day: '2-digit',
    }).formatToParts(date);
    const get = (type) => parts.find((p) => p.type === type)?.value || '';
    return `${get('year')}-${get('month')}-${get('day')}`;
  } catch {
    const y = date.getFullYear();
    const m = String(date.getMonth() + 1).padStart(2, '0');
    const day = String(date.getDate()).padStart(2, '0');
    return `${y}-${m}-${day}`;
  }
}

const EVENT_LABELS = {
  login_success: 'Signed in',
  login_failure: 'Sign-in failed',
  logout: 'Signed out',
  idle_timeout: 'Session idle timeout',
  refresh_denied: 'Session refresh denied',
  session_replaced: 'Signed in on another device',
  session_rejected: 'Session ended by admin',
  geo_capture_failed: 'Location capture failed',
  payin_success: 'Pay-in success',
  payin_created: 'Pay-in created',
  payin_failed: 'Pay-in failed',
  payout_success: 'Payout success',
  payout_created: 'Payout created',
  payout_failed: 'Payout failed',
  bbps_payment: 'BBPS payment',
  wallet_transfer: 'Wallet transfer',
  contact_created: 'Contact added',
  contact_updated: 'Contact updated',
  contact_deleted: 'Contact deleted',
  report_viewed: 'Report viewed',
  bank_account_added: 'Bank account added',
  bank_account_updated: 'Bank account updated',
  bank_account_deleted: 'Bank account deleted',
  access_controls_changed: 'Access controls changed',
  role_changed: 'Role changed',
  user_disabled: 'User disabled',
  user_enabled: 'User enabled',
};

/**
 * @param {string} eventType
 * @returns {string}
 */
export function formatAuditEventLabel(eventType) {
  if (!eventType) return '—';
  return EVENT_LABELS[eventType] || String(eventType).replace(/_/g, ' ');
}
