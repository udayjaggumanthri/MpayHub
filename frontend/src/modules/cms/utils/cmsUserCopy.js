/**
 * Role-aware CMS copy: agents see friendly text; Admin/Super Admin see provider details.
 */

const VENDOR_RE = /\b(fingpay|tapits|ubercms|fpuat|fpcorp|fingpayuat)\b/gi;

export function isCmsOperatorRole(user) {
  const role = String(user?.role || user?.user_role || '').trim();
  return role === 'Admin' || role === 'Super Admin';
}

export function sanitizeCmsUserMessage(raw) {
  let text = String(raw || '').trim();
  if (!text) return '';
  text = text
    .replace(VENDOR_RE, 'the payment network')
    .replace(/\bHTTP 404\b/gi, 'service unavailable')
    .replace(/\s{2,}/g, ' ')
    .trim();
  if (!text) {
    return 'This request could not be completed. Please try again or contact support.';
  }
  return text;
}

export function formatCmsAmount(raw) {
  if (raw == null || raw === '') return '—';
  const n = Number(String(raw).replace(/,/g, '').trim());
  if (!Number.isFinite(n)) return String(raw);
  return `₹${n.toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}

export function formatCmsDateTime(value) {
  if (!value) return '—';
  try {
    const d = value instanceof Date ? value : new Date(value);
    if (Number.isNaN(d.getTime())) return String(value);
    return d.toLocaleString('en-IN', {
      day: '2-digit',
      month: 'short',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
    });
  } catch {
    return String(value);
  }
}

export function cmsStatusTone(status) {
  const s = String(status || '').toLowerCase();
  if (s === 'success') return 'success';
  if (s === 'failed' || s === 'expired') return 'danger';
  if (s === 'initiated' || s === 'pending') return 'pending';
  return 'neutral';
}
