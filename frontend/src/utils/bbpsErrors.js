/**
 * Parse BBPS / BillAvenue API failures into UI-safe copy.
 * Never render raw JSON error blobs to partners.
 */

const PROVIDER_TITLES = {
  E135: 'Missing or mismatched details',
  E204: 'Fetch reference already used',
  E210: 'Fetch reference expired',
  E211: 'Bill snapshot mismatch',
  E212: 'Extra bill details mismatch',
  E092: 'Remitter details missing',
  E077: 'Payment method not supported',
  E078: 'Payment channel not accepted',
  UM001: 'Request format rejected',
  BFR001: 'Invalid account details',
  BFR004: 'No bill due',
  BFR006: 'Unable to fetch bill',
  BRP046: 'QuickPay only',
  VE003: 'Agent ID rejected',
  VE008: 'Required field missing',
  VE009: 'Value too short',
  VE010: 'Value too long',
  VE011: 'Wrong field type',
  VE012: 'Invalid field format',
  TIMEOUT: 'Provider timed out',
};

function looksLikeJson(text) {
  const t = String(text || '').trim();
  return t.startsWith('{') || t.includes('"errorCode"') || t.includes('"errorMessage"');
}

function extractFromJsonBlob(text) {
  const t = String(text || '');
  try {
    const start = t.indexOf('{');
    if (start >= 0) {
      const parsed = JSON.parse(t.slice(start).match(/\{[\s\S]*\}/)?.[0] || '');
      if (parsed && typeof parsed === 'object') {
        return {
          code: String(parsed.errorCode || '').trim().toUpperCase(),
          message: String(parsed.errorMessage || '').trim(),
        };
      }
    }
  } catch {
    /* ignore */
  }
  const m = t.match(/"errorCode"\s*:\s*"([^"]+)"/i);
  const m2 = t.match(/"errorMessage"\s*:\s*"([^"]+)"/i);
  return {
    code: m ? m[1].trim().toUpperCase() : '',
    message: m2 ? m2[1].trim() : '',
  };
}

function normalizeFieldErrors(errors) {
  if (!Array.isArray(errors)) return {};
  const map = {};
  errors.forEach((e) => {
    if (e && typeof e === 'object' && e.param) {
      map[String(e.param)] = String(e.message || e.code || 'Invalid value');
    }
  });
  return map;
}

/**
 * @param {object} result - API client result (success:false)
 * @returns {{ title: string, detail: string, hint: string, reference: string, retryable: boolean, fieldErrors: Record<string,string>, providerCode: string }}
 */
export function parseBbpsError(result) {
  const err = (result && result.error) || {};
  const rawMessage = String(result?.message || '').trim();
  const providerCode = String(err.provider_code || '').trim().toUpperCase();
  const hint = String(err.action_hint || '').trim();
  const reference = String(result?.traceId || err.trace_id || '').trim();
  const retryable = Boolean(err.retryable);
  const fieldErrors = normalizeFieldErrors(result?.errors);

  let code = providerCode;
  let detail = rawMessage;

  if (looksLikeJson(rawMessage)) {
    const extracted = extractFromJsonBlob(rawMessage);
    if (extracted.code) code = code || extracted.code;
    if (extracted.message) detail = extracted.message;
    else if (looksLikeJson(detail)) {
      detail = 'The bill payment provider rejected this request. Please verify your details and try again.';
    }
  }

  // Strip leftover "BillAvenue API failed ... (CODE — msg)" wrappers if still present
  const paren = detail.match(/code=\S+\s*\((.+)\)\s*$/i);
  if (paren) {
    const inner = paren[1].trim();
    if (looksLikeJson(inner)) {
      const extracted = extractFromJsonBlob(inner);
      if (extracted.code) code = code || extracted.code;
      detail = extracted.message || 'The bill payment provider rejected this request. Please verify your details and try again.';
    } else if (inner.includes('—') || inner.includes(' - ')) {
      const parts = inner.split(/\s*[—-]\s*/, 2);
      if (parts.length === 2 && /^[A-Z]{1,3}\d+$/i.test(parts[0].trim())) {
        code = code || parts[0].trim().toUpperCase();
        detail = parts[1].trim();
      } else {
        detail = inner;
      }
    } else {
      detail = inner;
    }
  }

  if (looksLikeJson(detail)) {
    detail = 'The bill payment provider rejected this request. Please verify your details and try again.';
  }

  const title =
    PROVIDER_TITLES[code] ||
    (detail && detail.length < 80 ? detail : 'Could not complete this request');

  // Avoid duplicating title in detail when they're the same
  const safeDetail =
    detail && detail !== title
      ? detail
      : hint || 'Please check your details and try again.';

  return {
    title,
    detail: safeDetail,
    hint,
    reference,
    retryable,
    fieldErrors,
    providerCode: code,
  };
}

export default parseBbpsError;
