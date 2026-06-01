import { normalizeCategorySlug } from '../../constants/bbpsCanonicalCategories';

export const deriveCustomerId = (row) => {
  const r = row || {};
  const rd = r.receipt_details && typeof r.receipt_details === 'object' ? r.receipt_details : {};
  const details = r.customer_details && typeof r.customer_details === 'object' ? r.customer_details : {};
  const inputParams = Array.isArray(r.input_params) ? r.input_params : Array.isArray(r.inputParams) ? r.inputParams : [];
  const paramPatterns = /customer.?id|customer.?number|consumer.?number|subscriber|mobile|msisdn|account.?id|consumer.?id/i;
  const fromInputParam =
    inputParams.find((p) => paramPatterns.test(String(p?.paramName || p?.param_name || '')))?.paramValue ||
    inputParams.find((p) => paramPatterns.test(String(p?.param_name || '')))?.param_value ||
    '';
  const fromDetails = Object.entries(details).find(([k]) => paramPatterns.test(String(k || '')))?.[1];
  return (
    rd.bill_number ||
    r.customer_id ||
    r.customer_number ||
    details.customer_id ||
    details.customerId ||
    details['Customer ID'] ||
    details['CustomerId'] ||
    details['Customer Number'] ||
    details['Mobile Number'] ||
    details['Subscriber ID'] ||
    fromDetails ||
    fromInputParam ||
    r.mobile ||
    r.card_last4 ||
    ''
  );
};

const toInputParamRows = (row) =>
  Array.isArray(row?.inputParams)
    ? row.inputParams
    : Array.isArray(row?.input_params)
      ? row.input_params
      : [];

const toCustomerDetails = (row) => {
  const details = row?.customerDetails || row?.customer_details;
  return details && typeof details === 'object' ? details : {};
};

const pickFromInputParams = (row, patterns = []) => {
  const rows = toInputParamRows(row);
  for (const item of rows) {
    const key = String(item?.paramName || item?.param_name || '').toLowerCase();
    const value = String(item?.paramValue || item?.param_value || '').trim();
    if (!key || !value) continue;
    if (patterns.some((rx) => rx.test(key))) return value;
  }
  return '';
};

const pickFromCustomerDetails = (row, patterns = []) => {
  const details = toCustomerDetails(row);
  for (const [k, v] of Object.entries(details)) {
    const key = String(k || '').toLowerCase();
    const value = String(v || '').trim();
    if (!key || !value) continue;
    if (patterns.some((rx) => rx.test(key))) return value;
  }
  return '';
};

export const deriveReceiptIdentity = (row) => {
  const rawCat = String(row?.billType || row?.bill_type || row?.category || '');
  const category = rawCat.toLowerCase();
  const byPattern = (patterns) => pickFromCustomerDetails(row, patterns) || pickFromInputParams(row, patterns);

  const catNorm = normalizeCategorySlug(rawCat);
  const isFastag = catNorm === 'fastag' || catNorm === 'fast-tag' || rawCat.toLowerCase().includes('fastag');
  if (isFastag) {
    const vehicleNumber =
      byPattern([/vehicle/, /registration/, /\breg\b/, /\bvrn\b/, /\brc\b/, /veh.*no/, /car.*no/]) ||
      String(row?.vehicle_number || row?.vehicle_no || '').trim();
    if (vehicleNumber) return { label: 'Vehicle Number', value: vehicleNumber };
  }

  if (category.includes('credit') && category.includes('card')) {
    const last4 =
      byPattern([/card.*last.?4/, /last.?4/, /card.*digit/]) ||
      String(row?.cardLast4 || row?.card_last4 || '').trim();
    if (last4) return { label: 'Card Number (Last 4)', value: last4 };
  }

  if (category.includes('mobile')) {
    const mobile = byPattern([/mobile/, /phone/]) || String(row?.mobile || '').trim();
    if (mobile) return { label: 'Mobile Number', value: mobile };
  }

  const fallback = deriveCustomerId(row);
  return { label: 'Customer ID', value: fallback || 'N/A' };
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
