/**
 * User-friendly login error messages (maps API / validation payloads).
 */
import { ACCESS_CODES, messageForAccessCode } from './accessControl';

const DISABLED_COPY = {
  title: 'Account disabled',
  message: 'Your account is disabled. Contact your administrator.',
};

/** Remove DRF field keys accidentally shown in UI (e.g. "non_field_errors: …"). */
export function stripErrorFieldPrefix(text) {
  return String(text || '')
    .replace(/^non_field_errors:\s*/i, '')
    .replace(/^[a-z_]+:\s*/i, '')
    .trim();
}

const CREDENTIALS_COPY = {
  title: 'Login failed',
  message: 'Invalid phone number or password. Please check your details and try again.',
};

const GENERIC_COPY = {
  title: 'Unable to sign in',
  message: 'Something went wrong. Please try again in a moment.',
};

function textIncludesDisabled(text) {
  const t = String(text || '').toLowerCase();
  return t.includes('disabled') || t.includes('deactivated') || t.includes('inactive');
}

function flattenErrorStrings(errors) {
  if (!errors) return [];
  if (Array.isArray(errors)) return errors.map((e) => String(e));
  if (typeof errors === 'object') {
    return Object.entries(errors).flatMap(([key, val]) => {
      const items = Array.isArray(val) ? val : [val];
      if (key === 'non_field_errors' || key === 'detail') {
        return items.map((item) => String(item));
      }
      return items.map((item) => `${key}: ${item}`);
    });
  }
  return [String(errors)];
}

/**
 * @returns {{ title: string, message: string, variant: 'disabled' | 'credentials' | 'generic' }}
 */
export function parseLoginFailure(result) {
  if (!result || result.success) return null;

  const code = result.errorCode || result.accessError?.code || result.error?.code || null;
  if (code === ACCESS_CODES.USER_DISABLED) {
    return { ...DISABLED_COPY, variant: 'disabled' };
  }

  const parts = flattenErrorStrings(result.errors).map(stripErrorFieldPrefix);
  const cleanMessage = stripErrorFieldPrefix(result.message);
  const blob = [cleanMessage, ...parts].filter(Boolean).join(' ');

  if (textIncludesDisabled(blob) || textIncludesDisabled(result.message)) {
    return { ...DISABLED_COPY, variant: 'disabled' };
  }

  const fromAccess = messageForAccessCode(code);
  if (fromAccess) {
    return {
      title: 'Access limited',
      message: fromAccess,
      variant: 'generic',
    };
  }

  if (
    textIncludesDisabled(parts.join(' ')) ||
    /invalid (phone|credentials|password)/i.test(blob) ||
    code === 'INVALID_CREDENTIALS'
  ) {
    if (/invalid/i.test(blob) && !textIncludesDisabled(blob)) {
      return { ...CREDENTIALS_COPY, variant: 'credentials' };
    }
  }

  if (/invalid/i.test(blob)) {
    return { ...CREDENTIALS_COPY, variant: 'credentials' };
  }

  const message =
    (cleanMessage && cleanMessage !== 'Login failed' ? cleanMessage : null) ||
    parts[0] ||
    GENERIC_COPY.message;

  return {
    title: GENERIC_COPY.title,
    message: stripErrorFieldPrefix(message) || GENERIC_COPY.message,
    variant: 'generic',
  };
}
