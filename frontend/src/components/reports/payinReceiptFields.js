import { format } from 'date-fns';

import { formatCurrency } from '../../utils/formatters';
import { getBrandingLogoUrl } from '../../utils/brandingLogo';

export const MPAYHUB_LOGO_SRC = `${process.env.PUBLIC_URL || ''}/images/logo.png`;

export function getMpayhubLogoSrc() {
  return getBrandingLogoUrl();
}

const formatReceiptDateTime = (value) => {
  if (!value) return '—';
  try {
    const dateObj = value instanceof Date ? value : new Date(value);
    if (Number.isNaN(dateObj.getTime())) return String(value);
    return format(dateObj, 'dd-MM-yyyy HH:mm:ss');
  } catch {
    return String(value);
  }
};

const formatReceiptDate = (value) => {
  if (!value) return '—';
  try {
    const dateObj = value instanceof Date ? value : new Date(value);
    if (Number.isNaN(dateObj.getTime())) return String(value);
    return format(dateObj, 'dd-MM-yyyy');
  } catch {
    return String(value);
  }
};

const displayValue = (value) => {
  const s = String(value ?? '').trim();
  return s || '—';
};

/**
 * Map pay-in report row to receipt transaction shape.
 */
export const mapPayinRowToReceiptTransaction = (row = {}) => {
  const rd = row.receipt_details && typeof row.receipt_details === 'object' ? row.receipt_details : {};
  return {
    id: row.id,
    transactionId: row.service_id || row.transactionId || rd.transaction_id || '',
    receiptNo: rd.receipt_no || row.service_id || '',
    status: (row.status || rd.status || 'PENDING').toUpperCase(),
    collectionRail: row.collection_rail || rd.collection_rail || 'gateway',
    railTypeLabel: row.rail_type_label || rd.rail_type_label || '',
    collectionMethod: row.payment_gateway_name || rd.collection_method || '—',
    paymentMode: row.mode || rd.payment_mode || '—',
    qrAccountName: row.qr_account_name || rd.qr_account_name || '',
    utr: row.utr || rd.utr || '',
    gatewayReference: row.reference || rd.gateway_reference || row.gateway_transaction_id || '',
    customerName: row.customer_name || rd.customer_name || '',
    customerPhone: row.customer_phone || rd.customer_phone || row.customer_id || '',
    customerEmail: row.customer_email || rd.customer_email || '',
    agentName: rd.agent_name || row.agent_details?.name || '',
    agentCode: rd.agent_code || row.agent_details?.user_code || '',
    packageName: row.package_display_name || rd.package_name || '',
    grossAmount: parseFloat(row.principal || rd.gross_amount || 0) || 0,
    charges: parseFloat(row.service_charge || rd.charges || 0) || 0,
    netCredit: parseFloat(row.net_credit || rd.net_credit || 0) || 0,
    submittedAmount: parseFloat(row.submitted_amount || rd.submitted_amount || 0) || 0,
    paymentDate: rd.payment_date || '',
    transactionDate: row.created_at || rd.transaction_date || '',
    reviewedAt: rd.reviewed_at || '',
    failureReason: row.reject_reason || rd.failure_reason || '',
    proofReceiptUrl: row.proof_receipt_url || rd.proof_receipt_url || '',
    hasProofImage: Boolean(rd.has_proof_image || row.proof_receipt_url),
    openingBalance: row.opening_balance,
    closingBalance: row.closing_balance,
    receiptDetails: rd,
  };
};

export const buildPayinReceiptRows = (txn) => {
  const isQr = (txn.collectionRail || '').toLowerCase() === 'qr';
  const rows = [
    { label: 'Transaction ID', value: displayValue(txn.transactionId), mono: true },
    { label: 'Receipt No.', value: displayValue(txn.receiptNo || txn.transactionId), mono: true },
    { label: 'Transaction Date', value: formatReceiptDateTime(txn.transactionDate) },
    { label: 'Status', value: displayValue(txn.status), highlight: txn.status === 'SUCCESS' ? 'success' : txn.status === 'FAILED' ? 'danger' : undefined },
    { label: 'Collection Type', value: displayValue(txn.railTypeLabel || (isQr ? 'Manual QR' : 'Payment Gateway')) },
    { label: isQr ? 'QR Account' : 'Payment Gateway', value: displayValue(txn.collectionMethod) },
    { label: 'Payment Mode', value: displayValue(txn.paymentMode) },
    { label: 'UTR / Bank Reference', value: displayValue(txn.utr || txn.gatewayReference), mono: true },
    { label: 'Customer Name', value: displayValue(txn.customerName) },
    { label: 'Mobile Number', value: displayValue(txn.customerPhone) },
    { label: 'Email', value: displayValue(txn.customerEmail) },
    { label: 'Agent', value: displayValue([txn.agentCode, txn.agentName].filter(Boolean).join(' · ')) },
    { label: 'Package', value: displayValue(txn.packageName) },
    { label: 'Gross Amount', value: formatCurrency(txn.grossAmount), highlight: 'amount' },
    { label: 'Service Charges', value: formatCurrency(txn.charges) },
    { label: 'Net Credit', value: formatCurrency(txn.netCredit), highlight: 'amount' },
  ];

  if (isQr && txn.submittedAmount > 0) {
    rows.push({ label: 'Submitted Amount', value: formatCurrency(txn.submittedAmount) });
  }
  if (isQr && txn.paymentDate) {
    rows.push({ label: 'Payment Date', value: formatReceiptDate(txn.paymentDate) });
  }
  if (txn.reviewedAt) {
    rows.push({ label: 'Reviewed At', value: formatReceiptDateTime(txn.reviewedAt) });
  }
  if (txn.status === 'FAILED' && txn.failureReason) {
    rows.push({ label: 'Rejection Reason', value: displayValue(txn.failureReason), highlight: 'danger' });
  }
  if (txn.openingBalance != null && txn.openingBalance !== '') {
    rows.push({ label: 'Opening Balance', value: formatCurrency(parseFloat(txn.openingBalance) || 0) });
  }
  if (txn.closingBalance != null && txn.closingBalance !== '') {
    rows.push({ label: 'Closing Balance', value: formatCurrency(parseFloat(txn.closingBalance) || 0) });
  }

  return rows;
};

export const buildPayinReceiptSummary = (txn) => {
  if (txn.status === 'SUCCESS') {
    return `Wallet credited with ${formatCurrency(txn.netCredit)} after deductions of ${formatCurrency(txn.charges)} on gross pay-in of ${formatCurrency(txn.grossAmount)}.`;
  }
  if (txn.status === 'PENDING_REVIEW') {
    return 'This manual QR pay-in is pending admin verification. Wallet will be credited after approval.';
  }
  if (txn.status === 'FAILED' && txn.failureReason) {
    return `Transaction failed: ${txn.failureReason}`;
  }
  return '';
};

export const buildPayinReceiptPrintContext = (txn) => {
  const rows = buildPayinReceiptRows(txn);
  const rowMap = Object.fromEntries(rows.map((r) => [r.label, r.value]));
  return {
    receiptNo: rowMap['Receipt No.'] || txn.transactionId,
    receiptDate: formatReceiptDateTime(txn.transactionDate),
    paymentStatus: txn.status || 'PENDING',
    paymentStatusSuccess: txn.status === 'SUCCESS',
    transactionId: txn.transactionId,
    collectionType: rowMap['Collection Type'],
    collectionMethod: rowMap[txn.collectionRail === 'qr' ? 'QR Account' : 'Payment Gateway'],
    paymentMode: rowMap['Payment Mode'],
    utr: rowMap['UTR / Bank Reference'],
    customerName: rowMap['Customer Name'],
    mobileNo: rowMap['Mobile Number'],
    grossAmount: formatCurrency(txn.grossAmount),
    charges: formatCurrency(txn.charges),
    netCredit: formatCurrency(txn.netCredit),
    summary: buildPayinReceiptSummary(txn),
    rows,
  };
};
