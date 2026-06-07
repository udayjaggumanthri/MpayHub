import { format } from 'date-fns';

import { formatCurrency } from '../../utils/formatters';
import { normalizeCategorySlug } from '../../constants/bbpsCanonicalCategories';

export const MPAYHUB_LOGO_SRC = `${process.env.PUBLIC_URL || ''}/images/logo.svg`;

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

const toReceiptDetails = (row) => {
  const rd = row?.receiptDetails || row?.receipt_details;
  return rd && typeof rd === 'object' ? rd : {};
};

export const pickFromInputParams = (row, patterns = []) => {
  const rows = toInputParamRows(row);
  for (const item of rows) {
    const key = String(item?.paramName || item?.param_name || '').toLowerCase();
    const value = String(item?.paramValue || item?.param_value || '').trim();
    if (!key || !value) continue;
    if (patterns.some((rx) => rx.test(key))) return value;
  }
  return '';
};

export const pickFromCustomerDetails = (row, patterns = []) => {
  const details = toCustomerDetails(row);
  for (const [k, v] of Object.entries(details)) {
    const key = String(k || '').toLowerCase();
    const value = String(v || '').trim();
    if (!key || !value) continue;
    if (patterns.some((rx) => rx.test(key))) return value;
  }
  return '';
};

const pickFromCustomerInfo = (row, patterns = []) => {
  const info = row?.customerInfo || row?.customer_info;
  if (!info || typeof info !== 'object') return '';
  for (const [k, v] of Object.entries(info)) {
    const key = String(k || '').toLowerCase();
    const value = String(v || '').trim();
    if (!key || !value) continue;
    if (patterns.some((rx) => rx.test(key))) return value;
  }
  return '';
};

const pickDetail = (row, patterns = []) =>
  pickFromCustomerDetails(row, patterns) ||
  pickFromInputParams(row, patterns) ||
  pickFromCustomerInfo(row, patterns);

const pickReceipt = (row, key) => {
  const rd = toReceiptDetails(row);
  return String(rd[key] ?? '').trim();
};

const displayValue = (value, { optional = false } = {}) => {
  const s = String(value ?? '').trim();
  if (!s || s.toUpperCase() === 'N/A' || s.toUpperCase() === 'NA') {
    return optional ? '—' : 'N/A';
  }
  return s;
};

const formatReceiptDate = (value) => {
  if (!value) return '';
  try {
    const dateObj = value instanceof Date ? value : new Date(value);
    if (Number.isNaN(dateObj.getTime())) {
      const raw = String(value).trim();
      return raw || '';
    }
    return format(dateObj, 'dd-MM-yyyy');
  } catch {
    return String(value).trim();
  }
};

const formatReceiptDateTime = (value) => {
  if (!value) return 'N/A';
  try {
    const dateObj = value instanceof Date ? value : new Date(value);
    if (Number.isNaN(dateObj.getTime())) return String(value);
    return format(dateObj, 'yyyy-MM-dd HH:mm:ss');
  } catch {
    return String(value);
  }
};

const resolveBillerName = (txn) => {
  const billerId = String(txn?.billerId || '').trim();
  const fromReceipt = pickReceipt(txn, 'biller_name');
  const billerName = String(txn?.billerName || '').trim();
  const biller = String(txn?.biller || '').trim();
  if (fromReceipt) return fromReceipt;
  if (billerName && billerName !== billerId) return billerName;
  if (biller && biller !== billerId) return biller;
  return billerId || biller || 'N/A';
};

const resolveBillNumber = (txn, identity) => {
  const fromReceipt = pickReceipt(txn, 'bill_number');
  if (fromReceipt) return fromReceipt;
  const fromDetail = pickDetail(txn, [/bill.?number/, /consumer.?number/, /customer.?ref/]);
  if (fromDetail) return fromDetail;
  const cat = String(txn?.billType || '').toLowerCase();
  const catNorm = normalizeCategorySlug(cat);
  if (catNorm === 'fastag' || cat.includes('fastag')) {
    return identity?.value || pickDetail(txn, [/vehicle/, /registration/, /\bvrn\b/]) || '';
  }
  return '';
};

/**
 * Map API payment object (list/detail) to receipt transaction shape.
 */
export const mapApiPaymentToReceiptTransaction = (p = {}) => {
  const rd = p.receipt_details && typeof p.receipt_details === 'object' ? p.receipt_details : {};
  const billerId = p.biller_id || null;
  const billerName = rd.biller_name || p.biller_name || p.biller || 'N/A';

  return {
    id: p.id,
    serviceId: p.service_id || p.id,
    requestId: p.request_id || null,
    bConnectTxnId: p.bconnect_txn_id || p.request_id || p.service_id || null,
    approvalRefNumber: p.approval_ref_number || null,
    amount: parseFloat(p.amount || 0),
    charge: parseFloat(p.charge || p.service_charge || 0),
    ccfAmount: parseFloat(p.ccf_amount || p.charge || p.service_charge || 0),
    totalDeducted: parseFloat(
      p.total_deducted || parseFloat(p.amount || 0) + parseFloat(p.charge || p.service_charge || 0)
    ),
    billType: p.bill_type || p.category || 'Bill Payment',
    biller: billerName,
    billerName,
    billerId,
    customerId: p.customer_id || null,
    customerName: rd.customer_name || p.customer_name || '',
    billDate: rd.bill_date || '',
    billPeriod: rd.bill_period || '',
    dueDate: rd.due_date || '',
    billNumber: rd.bill_number || '',
    paymentMode: rd.payment_mode || p.payment_mode || '',
    initChannel: rd.init_channel || p.init_channel || '',
    remitterName: rd.remitter_name || '',
    inputParams: Array.isArray(p.input_params) ? p.input_params : [],
    customerDetails: p.customer_details && typeof p.customer_details === 'object' ? p.customer_details : {},
    customerInfo: p.customer_info && typeof p.customer_info === 'object' ? p.customer_info : {},
    receiptDetails: rd,
    date: p.created_at || p.transaction_date,
    status: (p.status || 'PENDING').toUpperCase(),
    cardLast4: p.card_last4 || null,
    mobile: p.mobile || null,
    failureReason: p.failure_reason || '',
    statusHistory: Array.isArray(p.status_history) ? p.status_history : [],
  };
};

/**
 * Build label/value rows for the enterprise BBPS receipt grid (reference layout).
 */
export const buildBbpsReceiptRows = (txn, identity = { label: 'Customer Number', value: 'N/A' }) => {
  const amount = Number(txn?.amount || 0);
  const ccf = Number(txn?.ccfAmount ?? txn?.charge ?? 0);
  const total = Number(txn?.totalDeducted ?? amount + (txn?.charge || 0));
  const status = String(txn?.status || 'N/A');
  const statusLower = status.toLowerCase();

  const customerName = displayValue(
    pickReceipt(txn, 'customer_name') ||
      txn?.customerName ||
      pickDetail(txn, [/customer.?name/, /^name$/, /consumer.?name/, /account.?holder/]) ||
      txn?.remitterName ||
      pickReceipt(txn, 'remitter_name'),
    { optional: true }
  );

  const billDateRaw =
    pickReceipt(txn, 'bill_date') || txn?.billDate || pickDetail(txn, [/bill.?date/]);
  const billPeriodRaw =
    pickReceipt(txn, 'bill_period') || txn?.billPeriod || pickDetail(txn, [/bill.?period/]);
  const dueDateRaw = pickReceipt(txn, 'due_date') || txn?.dueDate || pickDetail(txn, [/due.?date/]);
  const billNumberRaw = resolveBillNumber(txn, identity);

  const paymentMode =
    pickReceipt(txn, 'payment_mode') ||
    txn?.paymentMode ||
    pickDetail(txn, [/payment.?mode/]) ||
    '';
  const initChannel =
    pickReceipt(txn, 'init_channel') ||
    txn?.initChannel ||
    pickDetail(txn, [/init.?channel/, /initiating.?channel/]) ||
    '';

  const identityValue = identity?.value || txn?.customerId || pickDetail(txn, [/customer/, /mobile/, /consumer/]);

  return [
    { label: 'Biller ID', value: displayValue(txn?.billerId) },
    { label: 'Customer Name', value: customerName },
    {
      label: identity?.label || 'Customer Number',
      value: displayValue(identityValue),
    },
    {
      label: 'Bill Date',
      value: billDateRaw ? formatReceiptDate(billDateRaw) : displayValue('', { optional: true }),
    },
    { label: 'Bill Period', value: displayValue(billPeriodRaw, { optional: true }) },
    {
      label: 'Due Date',
      value: dueDateRaw ? formatReceiptDate(dueDateRaw) : displayValue('', { optional: true }),
    },
    { label: 'Customer Convenience Fees', value: formatCurrency(ccf), highlight: 'amount' },
    { label: 'Total amount', value: formatCurrency(total) },
    { label: 'Biller Name', value: resolveBillerName(txn) },
    { label: 'Bill Number', value: displayValue(billNumberRaw, { optional: true }) },
    { label: 'Approval Number', value: displayValue(txn?.approvalRefNumber) },
    {
      label: 'Transaction Date and Time',
      value: formatReceiptDateTime(txn?.date),
    },
    { label: 'Amount', value: formatCurrency(amount), highlight: statusLower === 'success' ? 'success' : undefined },
    { label: 'CCF', value: formatCurrency(ccf) },
    {
      label: 'B-Connect Txn ID',
      value: txn?.bConnectTxnId || txn?.serviceId || txn?.id || 'N/A',
      mono: true,
    },
    { label: 'Payment Mode', value: displayValue(paymentMode) },
    {
      label: 'Transaction Status',
      value: statusLower,
      highlight: statusLower === 'success' ? 'success' : statusLower === 'failed' || statusLower === 'failure' ? 'danger' : undefined,
    },
    { label: 'Initiating Channel', value: displayValue(initChannel) },
  ];
};

const formatPrintRupee = (amount) => {
  const val = Number(amount || 0);
  return `Rs. ${val.toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
};

const formatPrintReceiptDate = (value) => {
  if (!value) return '—';
  try {
    const dateObj = value instanceof Date ? value : new Date(value);
    if (Number.isNaN(dateObj.getTime())) return String(value).trim() || '—';
    return format(dateObj, 'd MMMM yyyy');
  } catch {
    return String(value).trim() || '—';
  }
};

const resolveCustomerName = (txn) => {
  const raw =
    pickReceipt(txn, 'customer_name') ||
    txn?.customerName ||
    pickDetail(txn, [/customer.?name/, /^name$/, /consumer.?name/]) ||
    txn?.remitterName ||
    pickReceipt(txn, 'remitter_name');
  return displayValue(raw, { optional: true });
};

const resolveMobile = (txn) => {
  const raw =
    txn?.mobile ||
    pickDetail(txn, [/mobile/, /phone/, /msisdn/]) ||
    pickFromCustomerInfo(txn, [/mobile/]);
  return displayValue(raw, { optional: true });
};

/**
 * Structured context for print / PDF receipt (reference Payment Receipt layout).
 */
export const buildBbpsReceiptPrintContext = (txn, identity = { label: 'Customer Number', value: '' }) => {
  const amount = Number(txn?.amount || 0);
  const ccf = Number(txn?.ccfAmount ?? txn?.charge ?? 0);
  const total = Number(txn?.totalDeducted ?? amount + ccf);
  const status = String(txn?.status || '').toUpperCase();
  const isSuccess = status === 'SUCCESS';
  const billNumber = displayValue(resolveBillNumber(txn, identity) || identity?.value, { optional: true });

  const paymentMode =
    pickReceipt(txn, 'payment_mode') ||
    txn?.paymentMode ||
    pickDetail(txn, [/payment.?mode/]) ||
    'Cash';

  return {
    receiptDate: formatPrintReceiptDate(txn?.date),
    receiptNo: txn?.serviceId || txn?.id || '—',
    customerName: resolveCustomerName(txn),
    mobileNo: resolveMobile(txn),
    billNumber,
    billNumberLabel: 'Bill Number',
    paymentStatus: isSuccess ? 'Paid' : status.charAt(0) + status.slice(1).toLowerCase(),
    paymentStatusSuccess: isSuccess,
    paymentMode: displayValue(paymentMode),
    bConnectTxnId: txn?.bConnectTxnId || txn?.serviceId || txn?.id || '—',
    billerName: resolveBillerName(txn),
    billAmount: formatPrintRupee(amount),
    ccfAmount: formatPrintRupee(ccf),
    totalAmount: formatPrintRupee(total),
    grandTotal: formatPrintRupee(total),
  };
};

export const buildBbpsReceiptSummary = (txn, identity = { label: 'Customer Number', value: 'N/A' }) => {
  const status = String(txn?.status || '').toUpperCase();
  if (status !== 'SUCCESS') {
    const reason = String(txn?.failureReason || '').trim();
    return reason
      ? `Transaction ${status}. ${reason}`
      : `Transaction status: ${status}.`;
  }

  const amount = Number(txn?.amount || 0);
  const biller = resolveBillerName(txn);
  const ref = identity?.value || txn?.customerId || pickDetail(txn, [/customer/, /mobile/, /vehicle/]) || '';

  return `Your payment of ${formatCurrency(amount)} to ${biller}${ref ? ` for ${ref}` : ''} was successful. Thank you for using mPayHub.`;
};
