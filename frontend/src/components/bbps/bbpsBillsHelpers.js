import { normalizeCategorySlug } from '../../constants/bbpsCanonicalCategories';

/** Params that are never the consumer identity on a receipt. */
const SKIP_IDENTITY_PARAM_RX =
  /^(plan.?id|amount|payment.?amount|bill.?amount|circle|operator|otp|mpin|remark|remarks|email|dob|date.?of.?birth|init.?channel|payment.?mode)$/i;

/**
 * Higher score = better receipt identity candidate.
 * Covers electricity Service Number, CA Number, FASTag vehicle, CC last-4, etc.
 */
const IDENTITY_SCORE_RULES = [
  { rx: /service.?number|service.?no|\bservice.?id\b/i, score: 100 },
  { rx: /consumer.?number|consumer.?no|consumer.?id|ca.?number|connection.?number|connection.?id/i, score: 96 },
  { rx: /customer.?id|customer.?number|customer.?no|account.?id|account.?number|utility.?number|utility.?id/i, score: 92 },
  { rx: /vehicle|registration|reg\.?\s*no|\bvrn\b|\brc\b|veh.*no/i, score: 92 },
  { rx: /card.?last|last.?4|last.?four|card.?digit/i, score: 92 },
  { rx: /subscriber|policy.?number|loan.?account|rr.?number|meter.?number|k.?number|uc.?id/i, score: 88 },
  { rx: /mobile|phone|msisdn|telephone/i, score: 72 },
  { rx: /\bnumber\b|\bid\b|\baccount\b|\breference\b/i, score: 40 },
];

const isBlankIdentity = (value) => {
  const s = String(value ?? '').trim();
  if (!s) return true;
  const upper = s.toUpperCase();
  return upper === 'N/A' || upper === 'NA' || upper === '-';
};

const scoreIdentityKey = (rawKey) => {
  const key = String(rawKey || '').trim();
  if (!key || SKIP_IDENTITY_PARAM_RX.test(key)) return 0;
  let best = 0;
  for (const rule of IDENTITY_SCORE_RULES) {
    if (rule.rx.test(key) && rule.score > best) best = rule.score;
  }
  return best;
};

const toInputParamRows = (row) =>
  Array.isArray(row?.inputParams)
    ? row.inputParams
    : Array.isArray(row?.input_params)
      ? row.input_params
      : Array.isArray(row)
        ? row
        : [];

const toCustomerDetails = (row) => {
  const details = row?.customerDetails || row?.customer_details || row;
  return details && typeof details === 'object' && !Array.isArray(details) ? details : {};
};

const humanizeParamLabel = (raw) => {
  const s = String(raw || '').trim();
  if (!s) return 'Customer ID';
  // Keep spaced MDM labels like "Service Number" / "CA Number" as-is.
  if (/\s/.test(s)) return s;
  // CustomerId / ServiceNumber → Customer ID / Service Number
  const spaced = s
    .replace(/([a-z0-9])([A-Z])/g, '$1 $2')
    .replace(/[_-]+/g, ' ')
    .trim();
  return spaced
    .split(/\s+/)
    .map((part) => {
      if (/^id$/i.test(part)) return 'ID';
      if (part.length <= 2 && /^[a-z]+$/i.test(part)) return part.toUpperCase();
      return part.charAt(0).toUpperCase() + part.slice(1);
    })
    .join(' ');
};

/**
 * Pick the best { label, value } from BBPS input params / customer_details.
 * Prefer MDM param names (Service Number, Vehicle Number, …) over a hard-coded "Customer ID".
 */
export const pickPrimaryIdentity = ({
  inputParams = [],
  customerDetails = {},
  inputSchema = [],
  inputValues = {},
} = {}) => {
  const candidates = [];

  const pushCandidate = (label, value, { scoreBoost = 0, order = 999 } = {}) => {
    if (isBlankIdentity(value)) return;
    const key = String(label || '').trim();
    const base = scoreIdentityKey(key);
    // Unknown but present MDM params still qualify as a weak identity (order-based).
    const score = (base || 15) + scoreBoost - order * 0.01;
    if (score <= 0) return;
    candidates.push({
      label: humanizeParamLabel(key),
      value: String(value).trim(),
      score,
    });
  };

  if (Array.isArray(inputSchema) && inputSchema.length) {
    inputSchema.forEach((field, idx) => {
      const paramName = field?.param_name || field?.paramName || '';
      if (!paramName || field?.send_in_input_params === false) return;
      const label =
        field?.display_label ||
        field?.display_name ||
        field?.label ||
        paramName;
      const value = inputValues?.[paramName];
      const mandatoryBoost = field?.is_optional === false || field?.optional === false ? 8 : 0;
      pushCandidate(label, value, { scoreBoost: mandatoryBoost + 5, order: idx });
    });
  }

  toInputParamRows({ inputParams, input_params: inputParams }).forEach((item, idx) => {
    const label = item?.paramName || item?.param_name || '';
    const value = item?.paramValue ?? item?.param_value ?? '';
    pushCandidate(label, value, { scoreBoost: 3, order: idx });
  });

  Object.entries(toCustomerDetails(customerDetails)).forEach(([label, value], idx) => {
    pushCandidate(label, value, { order: idx });
  });

  if (!candidates.length) return null;
  candidates.sort((a, b) => b.score - a.score);
  return { label: candidates[0].label, value: candidates[0].value };
};

export const deriveCustomerId = (row) => {
  const r = row || {};
  const rd = r.receipt_details && typeof r.receipt_details === 'object' ? r.receipt_details : {};
  const primary = pickPrimaryIdentity({
    inputParams: toInputParamRows(r),
    customerDetails: toCustomerDetails(r),
  });
  if (primary?.value) return primary.value;

  return (
    rd.bill_number ||
    r.customer_id ||
    r.customer_number ||
    r.mobile ||
    r.card_last4 ||
    ''
  );
};

export const deriveReceiptIdentity = (row) => {
  const r = row || {};
  const rawCat = String(r?.billType || r?.bill_type || r?.category || '');
  const category = rawCat.toLowerCase();
  const catNorm = normalizeCategorySlug(rawCat);
  const rd =
    (r.receiptDetails && typeof r.receiptDetails === 'object' && r.receiptDetails) ||
    (r.receipt_details && typeof r.receipt_details === 'object' && r.receipt_details) ||
    {};
  const fromReceiptLabel = String(rd.identity_label || '').trim();
  const fromReceiptValue = String(rd.identity_value || '').trim();
  if (fromReceiptValue && !/^n\/?a$/i.test(fromReceiptValue)) {
    return {
      label: humanizeParamLabel(fromReceiptLabel || 'Customer ID'),
      value: fromReceiptValue,
    };
  }

  const primary = pickPrimaryIdentity({
    inputParams: toInputParamRows(r),
    customerDetails: toCustomerDetails(r),
    inputSchema: Array.isArray(r.inputSchema) ? r.inputSchema : [],
    inputValues: r.inputValues && typeof r.inputValues === 'object' ? r.inputValues : {},
  });

  const isFastag = catNorm === 'fastag' || catNorm === 'fast-tag' || category.includes('fastag');
  if (isFastag) {
    if (primary && /vehicle|registration|reg|vrn|rc/i.test(primary.label)) {
      return { label: 'Vehicle Number', value: primary.value };
    }
    if (primary?.value) return { label: 'Vehicle Number', value: primary.value };
    const fallbackVehicle = String(r?.vehicle_number || r?.vehicle_no || '').trim();
    if (fallbackVehicle) return { label: 'Vehicle Number', value: fallbackVehicle };
  }

  if (category.includes('credit') && category.includes('card')) {
    if (primary && /card|last.?4|digit/i.test(primary.label)) {
      return { label: 'Card Number (Last 4)', value: primary.value };
    }
    const last4 = String(r?.cardLast4 || r?.card_last4 || '').trim();
    if (last4) return { label: 'Card Number (Last 4)', value: last4 };
  }

  if (category.includes('mobile') && primary && /mobile|phone|msisdn/i.test(primary.label)) {
    return { label: 'Mobile Number', value: primary.value };
  }

  if (primary?.value) return primary;

  const legacy = deriveCustomerId(r);
  return { label: 'Customer ID', value: legacy || 'N/A' };
};

/**
 * Live pay-form identity from MDM input schema + entered values.
 */
export const deriveFormReceiptIdentity = ({
  category = '',
  inputSchema = [],
  inputValues = {},
  billDetails = null,
  user = null,
} = {}) => {
  const primary = pickPrimaryIdentity({ inputSchema, inputValues });
  const identity = deriveReceiptIdentity({
    category,
    billType: category,
    inputSchema,
    inputValues,
    inputParams: Array.isArray(inputSchema)
      ? inputSchema
          .filter((p) => p?.send_in_input_params !== false)
          .map((p) => ({
            paramName: p.param_name,
            paramValue: inputValues?.[p.param_name] || '',
          }))
          .filter((row) => String(row.paramValue || '').trim())
      : [],
    customerDetails: inputValues,
    card_last4: inputValues?.['Card Last 4 Digits'] || inputValues?.['Card Last4 Digits'],
    mobile: inputValues?.['Mobile Number'] || user?.phone,
    vehicle_number: billDetails?.billNumber,
  });

  if (identity?.value && identity.value !== 'N/A') return identity;
  if (primary?.value) return primary;

  const phone = String(billDetails?.telephoneNumber || user?.phone || '').trim();
  if (phone) return { label: 'Mobile Number', value: phone };
  return { label: 'Customer ID', value: 'N/A' };
};

export const getStatusColor = (status) => {
  switch (status) {
    case 'SUCCESS':
      return 'bg-green-100 text-green-800 border-green-200';
    case 'PENDING':
      return 'bg-yellow-100 text-yellow-800 border-yellow-200';
    case 'FAILURE':
    case 'FAILED':
      return 'bg-red-100 text-red-800 border-red-200';
    default:
      return 'bg-gray-100 text-gray-800 border-gray-200';
  }
};
