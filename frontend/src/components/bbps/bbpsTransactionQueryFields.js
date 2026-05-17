import { formatCurrency } from '../../utils/formatters';

const fmtVal = (v) => {
  const s = v != null && String(v).trim() !== '' ? String(v).trim() : '';
  return s || '—';
};

const normalizeKey = (key) =>
  String(key || '')
    .replace(/([a-z])([A-Z])/g, '$1_$2')
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '_')
    .replace(/^_+|_+$/g, '');

const pickCI = (obj, keys = []) => {
  if (!obj || typeof obj !== 'object') return '';
  for (const k of keys) {
    if (obj[k] != null && String(obj[k]).trim() !== '') return String(obj[k]).trim();
  }
  const map = Object.entries(obj).reduce((acc, [k, v]) => {
    acc[normalizeKey(k)] = v;
    return acc;
  }, {});
  for (const k of keys) {
    const v = map[normalizeKey(k)];
    if (v != null && String(v).trim() !== '') return String(v).trim();
  }
  return '';
};

const infoArrayMap = (row) => {
  const sources = [
    ...(Array.isArray(row?.additionalInfo?.info) ? row.additionalInfo.info : []),
    ...(Array.isArray(row?.paymentInfo?.info) ? row.paymentInfo.info : []),
    ...(Array.isArray(row?.billerResponse?.additionalInfo?.info) ? row.billerResponse.additionalInfo.info : []),
    ...(Array.isArray(row?.biller_response?.additional_info?.info) ? row.biller_response.additional_info.info : []),
  ];
  const out = {};
  for (const item of sources) {
    const name = String(item?.infoName || item?.name || '').trim();
    const value = String(item?.infoValue || item?.value || '').trim();
    if (name && value) out[normalizeKey(name)] = value;
  }
  return out;
};

const flattenScalars = (row, maxDepth = 4) => {
  const out = {};
  const seen = new Set();

  const walk = (obj, depth = 0, prefix = '') => {
    if (!obj || typeof obj !== 'object' || depth > maxDepth) return;
    if (Array.isArray(obj)) return;

    for (const [rawKey, value] of Object.entries(obj)) {
      const key = String(rawKey || '');
      if (!key || key.startsWith('_')) continue;

      if (value != null && typeof value === 'object') {
        if (Array.isArray(value)) continue;
        if (['billerResponse', 'biller_response', 'receipt_details', 'receiptDetails'].includes(key)) {
          walk(value, depth + 1, '');
          continue;
        }
        if (['customer_details', 'customerDetails', 'customerInfo', 'customer_info'].includes(key)) {
          if (typeof value === 'object' && !Array.isArray(value)) {
            for (const [ck, cv] of Object.entries(value)) {
              const nk = normalizeKey(ck);
              if (cv != null && typeof cv !== 'object' && String(cv).trim()) out[nk] = String(cv).trim();
            }
          }
          continue;
        }
        walk(value, depth + 1, prefix ? `${prefix}.${key}` : key);
        continue;
      }

      if (value == null || String(value).trim() === '') continue;
      const nk = normalizeKey(key);
      if (seen.has(nk)) continue;
      seen.add(nk);
      out[nk] = value;
    }
  };

  walk(row);
  Object.assign(out, infoArrayMap(row));

  const receipt = row?.receipt_details || row?.receiptDetails;
  if (receipt && typeof receipt === 'object') {
    for (const [k, v] of Object.entries(receipt)) {
      const nk = normalizeKey(k);
      if (v != null && String(v).trim() && !seen.has(nk)) {
        seen.add(nk);
        out[nk] = v;
      }
    }
  }

  return out;
};

const humanizeKey = (key) =>
  String(key || '')
    .replace(/_/g, ' ')
    .replace(/\b\w/g, (c) => c.toUpperCase());

const isAmountKey = (key) =>
  /amount|fee|ccf|charge|total|paid|rupee|rs/i.test(String(key || ''));

const isStatusKey = (key) => /status|txn_status|payment_status|txn_resp/i.test(String(key || ''));

const isDateKey = (key) => /date|time|datetime/i.test(String(key || ''));

const formatFieldValue = (key, value) => {
  if (value == null || String(value).trim() === '') return '—';
  const raw = String(value).trim();
  if (isStatusKey(key)) return raw;

  if (isAmountKey(key)) {
    const n = Number(String(raw).replace(/,/g, ''));
    if (!Number.isNaN(n)) {
      if (Number.isInteger(n) && n >= 10000 && !raw.includes('.')) {
        return formatCurrency(n / 100);
      }
      return formatCurrency(n);
    }
  }

  return raw;
};

/** Preferred display order and labels (BillAvenue + local enrichment). */
const FIELD_SPECS = [
  { label: 'Name of Biller', keys: ['biller_name', 'billername', 'biller'] },
  { label: 'Biller ID', keys: ['biller_id', 'billerid'] },
  { label: 'Customer Name', keys: ['customer_name', 'customername', 'consumer_name', 'account_holder_name'] },
  { label: 'Mobile Number', keys: ['mobile_number', 'mobilenumber', 'mobile_no', 'mobileno', 'customer_mobile'] },
  { label: 'Registered Mobile Number', keys: ['registered_mobile', 'registeredmobilenumber', 'reg_mobile_no'] },
  { label: 'Bill Number', keys: ['bill_number', 'billnumber', 'bill_no', 'consumer_number', 'customer_ref_number'] },
  { label: 'Bill Date', keys: ['bill_date', 'billdate'] },
  { label: 'Due Date', keys: ['due_date', 'duedate', 'bill_due_date'] },
  { label: 'Bill Period', keys: ['bill_period', 'billperiod'] },
  { label: 'B-Connect TXN ID', keys: ['txn_reference_id', 'txnreferenceid', 'txn_ref_id', 'txnrefid'] },
  { label: 'Request ID', keys: ['request_id', 'requestid'] },
  { label: 'Service ID', keys: ['service_id', 'serviceid'] },
  { label: 'Approval Reference', keys: ['approval_ref_number', 'approvalrefnumber', 'approval_number'] },
  { label: 'Payment Mode', keys: ['payment_mode', 'paymentmode', 'pay_mode'] },
  { label: 'Initiating Channel', keys: ['init_channel', 'initchannel', 'initiating_channel', 'payment_channel'] },
  { label: 'Customer Convenience Fee (CCF)', keys: ['customer_convenience_fee', 'ccf', 'conv_fee', 'convenience_fee'] },
  { label: 'Payment Status', keys: ['txn_status', 'txnstatus', 'payment_status', 'status'] },
  { label: 'Bill Amount', keys: ['bill_amount', 'billamount'] },
  { label: 'Total Amount', keys: ['total_amount', 'totalamount', 'amount_paid', 'paid_amount', 'payment_amount'] },
  { label: 'Amount', keys: ['amount'] },
  { label: 'Transaction Date & Time', keys: ['txn_date', 'txndate', 'transaction_date', 'transaction_datetime', 'txn_date_time'] },
  { label: 'Agent ID', keys: ['agent_id', 'agentid'] },
  { label: 'Category', keys: ['bill_type', 'billtype', 'category'] },
];

const SKIP_DYNAMIC_KEYS = new Set([
  'info',
  'raw',
  'errors',
  'success',
  'message',
  'enrichedfromlocal',
]);

export const pickTxnReferenceId = (row) =>
  pickCI(row, [
    'txnReferenceId',
    'txnRefId',
    'txn_ref_id',
    'txn_reference_id',
    'bConnectTxnId',
    'bconnect_txn_id',
  ]) ||
  pickCI(flattenScalars(row), ['txn_reference_id', 'txn_ref_id']);

/**
 * Build ordered label/value rows for transaction query UI (known fields first, then API extras).
 */
export const buildTransactionQueryFields = (row) => {
  const flat = flattenScalars(row);
  const used = new Set();
  const fields = [];

  const addField = (label, rawKey, value) => {
    const nk = normalizeKey(rawKey);
    if (used.has(nk)) return;
    const display = formatFieldValue(nk, value);
    if (display === '—') return;
    used.add(nk);
    fields.push({
      key: nk,
      label,
      value: display,
      isStatus: isStatusKey(nk),
    });
  };

  for (const spec of FIELD_SPECS) {
    let value = '';
    let matchedKey = '';
    for (const k of spec.keys) {
      const hit = flat[k];
      if (hit != null && String(hit).trim() !== '') {
        value = hit;
        matchedKey = k;
        break;
      }
    }
    if (!value) {
      value = pickCI(row, spec.keys) || pickCI(row?.billerResponse || {}, spec.keys);
    }
    if (value) addField(spec.label, matchedKey || spec.keys[0], value);
  }

  const priorityLabels = new Set(fields.map((f) => f.label.toLowerCase()));

  Object.entries(flat)
    .sort(([a], [b]) => a.localeCompare(b))
    .forEach(([nk, value]) => {
      if (used.has(nk) || SKIP_DYNAMIC_KEYS.has(nk)) return;
      if (value == null || String(value).trim() === '') return;
      const label = humanizeKey(nk);
      if (priorityLabels.has(label.toLowerCase())) return;
      addField(label, nk, value);
    });

  return fields;
};

export { fmtVal, flattenScalars, pickCI };
