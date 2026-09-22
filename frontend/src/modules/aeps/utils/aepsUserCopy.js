/**
 * Role-aware AEPS copy: agents see friendly text; Admin/Super Admin see provider details.
 */

const VENDOR_RE = /\b(fingpay|tapits|fpaeps(?:service|web)?|fingpayap|fpuat)\b/gi;

const SUPPORT_MARKERS = [
  'support context:',
  'merchantloginid=',
  'supermerchantid=',
  'egressip=',
  'env=simple',
  'env=uat',
  'env=prod',
];

export function isAepsOperatorRole(user) {
  const role = String(user?.role || user?.user_role || '').trim();
  return role === 'Admin' || role === 'Super Admin';
}

/** Strip vendor names and ops breadcrumbs from agent-facing text. */
export function sanitizeAepsUserMessage(raw) {
  let text = String(raw || '').trim();
  if (!text) return '';

  const lower = text.toLowerCase();
  for (const marker of SUPPORT_MARKERS) {
    const idx = lower.indexOf(marker);
    if (idx !== -1) {
      text = text.slice(0, idx).trim();
      break;
    }
  }

  text = text
    .replace(VENDOR_RE, 'the payment network')
    .replace(/\bthe payment network must enable\b/gi, 'support must enable')
    .replace(/\bask the payment network to\b/gi, 'ask support to')
    .replace(/\bTapits must\b/gi, 'Support must')
    .replace(/\bthe payment network must publish\b/gi, 'support must enable')
    .replace(/\s{2,}/g, ' ')
    .replace(/\s+([.,;:])/g, '$1')
    .trim();

  // Soften leftover ops jargon for retailers
  text = text
    .replace(/\bSimple API endpoint\b/gi, 'deposit service')
    .replace(/\bSimple CD OTP URL\b/gi, 'OTP deposit service')
    .replace(/\bon fpaepsservice\b/gi, '')
    .replace(/\bHTTP 404\b/gi, 'service unavailable')
    .replace(/\s{2,}/g, ' ')
    .trim();

  if (!text) {
    return 'This transaction could not be completed. Please try again or contact support.';
  }
  return text;
}

export function splitAepsMessageForRole(raw, { isOperator = false } = {}) {
  const full = String(raw || '').trim();
  if (!full) return { headline: '', support: '', display: '' };

  const idx = full.toLowerCase().indexOf('support context:');
  const headlineRaw = idx === -1 ? full : full.slice(0, idx).trim();
  const supportRaw = idx === -1 ? '' : full.slice(idx).replace(/^support context:\s*/i, '').trim();

  if (isOperator) {
    return {
      headline: headlineRaw,
      support: supportRaw || (full.includes('merchantLoginId') ? full : ''),
      display: headlineRaw,
    };
  }

  const display = sanitizeAepsUserMessage(headlineRaw || full);
  return { headline: display, support: '', display };
}

export function aepsBankDisplay(txn) {
  const name = String(txn?.bank_name || '').trim();
  const iin = String(txn?.bank_iin || '').trim();
  if (name && iin && name !== iin) return `${name} (${iin})`;
  if (name) return name;
  if (iin) return iin;
  return '—';
}
