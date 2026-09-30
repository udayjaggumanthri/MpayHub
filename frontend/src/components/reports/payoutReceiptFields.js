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

const displayValue = (value) => {
  const s = String(value ?? '').trim();
  return s || '—';
};

const senderInfoDisplay = (mobile, name) => {
  const m = String(mobile || '').trim();
  const n = String(name || '').trim();
  if (m && n) return `${m} (${n})`;
  if (m) return `${m} (NA)`;
  if (n) return n;
  return '—';
};

/**
 * Map payout report row to receipt transaction shape.
 */
export const mapPayoutRowToReceiptTransaction = (row = {}) => {
  const rd = row.receipt_details && typeof row.receipt_details === 'object' ? row.receipt_details : {};
  const agent = row.agent_details && typeof row.agent_details === 'object' ? row.agent_details : {};
  return {
    id: row.id,
    transactionId: row.transaction_id || row.transactionId || rd.transaction_id || '',
    receiptNo: rd.receipt_no || row.transaction_id || row.transactionId || '',
    status: (row.status || rd.status || 'PENDING').toUpperCase(),
    transferMode: row.transfer_mode || rd.transfer_mode || '',
    senderInfo: rd.sender_info || row.beneficiary_mobile || '',
    senderName: rd.sender_name || row.beneficiary_name || rd.account_holder_name || '',
    accountNumber: row.account_number || rd.account_number || '',
    bankName: row.bank_name || rd.bank_name || '',
    ifsc: row.ifsc || rd.ifsc || '',
    accountHolderName:
      row.beneficiary_name || rd.account_holder_name || rd.sender_name || '',
    beneficiaryMobile: row.beneficiary_mobile || rd.beneficiary_mobile || '',
    amount: parseFloat(row.transfer_amount || row.principal || rd.amount || 0) || 0,
    charge: parseFloat(row.payout_charge || row.service_charge || rd.charge || 0) || 0,
    totalDebit: parseFloat(row.net_debit || rd.total_debit || 0) || 0,
    bankRefNo: row.rrn || row.reference || rd.bank_ref_no || rd.rrn || '',
    rrn: row.rrn || rd.rrn || '',
    providerTxnId: rd.provider_txn_id || row.provider_txn_id || '',
    providerCode: row.provider_code || rd.provider_code || '',
    transactionDate: row.created_at || rd.transaction_date || '',
    callbackReceivedAt: row.callback_received_at || rd.callback_received_at || '',
    agentName: rd.agent_name || agent.name || '',
    agentCode: rd.agent_code || agent.user_code || agent.display_code || '',
    agentMobile: rd.agent_mobile || agent.mobile || '',
    openingBalance: row.opening_balance ?? rd.opening_balance,
    closingBalance: row.closing_balance ?? rd.closing_balance,
    receiptDetails: rd,
  };
};

export const buildPayoutReceiptRows = (txn) => {
  const agentInfo = [txn.agentCode, txn.agentName].filter(Boolean).join(' · ');
  const rows = [
    {
      label: 'Sender Info',
      value: senderInfoDisplay(txn.senderInfo || txn.beneficiaryMobile, txn.senderName),
    },
    { label: 'Account No.', value: displayValue(txn.accountNumber), mono: true },
    { label: 'Bank Name', value: displayValue(txn.bankName) },
    { label: 'IFSC Code', value: displayValue(txn.ifsc), mono: true },
    { label: 'Amount', value: formatCurrency(txn.amount), highlight: 'amount' },
    { label: 'Account Holder Name', value: displayValue(txn.accountHolderName) },
    {
      label: 'Status',
      value: displayValue(txn.status),
      highlight:
        txn.status === 'SUCCESS' ? 'success' : txn.status === 'FAILED' ? 'danger' : undefined,
    },
    { label: 'Bank Ref. No.', value: displayValue(txn.bankRefNo || txn.rrn), mono: true },
    { label: 'Date', value: formatReceiptDateTime(txn.transactionDate) },
    { label: 'Transaction ID', value: displayValue(txn.transactionId), mono: true },
    { label: 'Agent Info', value: displayValue(agentInfo) },
    { label: 'Agent Mobile', value: displayValue(txn.agentMobile) },
  ];

  if (txn.transferMode) {
    rows.push({ label: 'Transfer Mode', value: displayValue(txn.transferMode) });
  }
  if (txn.charge != null && !Number.isNaN(txn.charge) && txn.charge > 0) {
    rows.push({ label: 'Charge', value: formatCurrency(txn.charge) });
  }
  if (txn.totalDebit != null && !Number.isNaN(txn.totalDebit) && txn.totalDebit > 0) {
    rows.push({ label: 'Total Debit', value: formatCurrency(txn.totalDebit), highlight: 'amount' });
  }
  if (txn.providerTxnId) {
    rows.push({ label: 'Provider Reference', value: displayValue(txn.providerTxnId), mono: true });
  }
  if (txn.callbackReceivedAt) {
    rows.push({ label: 'Bank Confirmed At', value: formatReceiptDateTime(txn.callbackReceivedAt) });
  }
  if (txn.openingBalance != null && txn.openingBalance !== '') {
    rows.push({
      label: 'Opening Balance',
      value: formatCurrency(parseFloat(txn.openingBalance) || 0),
    });
  }
  if (txn.closingBalance != null && txn.closingBalance !== '') {
    rows.push({
      label: 'Closing Balance',
      value: formatCurrency(parseFloat(txn.closingBalance) || 0),
    });
  }

  return rows;
};

export const buildPayoutReceiptSummary = (txn) => {
  if (txn.status === 'SUCCESS') {
    return `Payout of ${formatCurrency(txn.amount)} completed. Total debit ${formatCurrency(
      txn.totalDebit || txn.amount
    )} (including charges).`;
  }
  if (txn.status === 'PENDING') {
    return 'Payout is in progress. Funds are held until the bank confirms the transfer.';
  }
  if (txn.status === 'FAILED') {
    return 'Payout failed. Held funds are released back to the main wallet when applicable.';
  }
  return '';
};

export const buildPayoutReceiptPrintContext = (txn) => {
  const rows = buildPayoutReceiptRows(txn);
  return {
    receiptNo: txn.receiptNo || txn.transactionId,
    receiptDate: formatReceiptDateTime(txn.transactionDate),
    paymentStatus: txn.status || 'PENDING',
    paymentStatusSuccess: txn.status === 'SUCCESS',
    transactionId: txn.transactionId,
    summary: buildPayoutReceiptSummary(txn),
    rows,
  };
};
