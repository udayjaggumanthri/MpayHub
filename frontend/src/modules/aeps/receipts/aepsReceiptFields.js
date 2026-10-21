import { getBrandingLogoUrl } from '../../../utils/brandingLogo';

export const MPAYHUB_LOGO_SRC = `${process.env.PUBLIC_URL || ''}/images/logo.png`;

export function getMpayhubLogoSrc() {
  return getBrandingLogoUrl();
}

const PRODUCT_LABELS = {
  CW: 'Cash Withdrawal',
  BE: 'Balance Enquiry',
  MS: 'Mini Statement',
  AP: 'Aadhaar Pay',
  CD: 'Cash Deposit',
  CD_OTP: 'Cash Deposit (OTP)',
  '2FA': 'Daily 2FA',
};

export const aepsProductLabel = (product) =>
  PRODUCT_LABELS[String(product || '').toUpperCase()] || product || 'AEPS';

const displayValue = (value) => {
  const s = String(value ?? '').trim();
  return s || '—';
};

export const formatAepsAmount = (raw) => {
  if (raw == null || raw === '') return '—';
  const n = Number(String(raw).replace(/,/g, '').trim());
  if (!Number.isFinite(n)) return displayValue(raw);
  return `₹${n.toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
};

export const formatAepsDateTime = (value) => {
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
};

export const aepsStatusTone = (status) => {
  const s = String(status || '').toLowerCase();
  if (s === 'success' || s === 'reconciled') return 'success';
  if (s === 'failed') return 'danger';
  if (s === 'pending' || s === 'timeout' || s === 'initiated') return 'pending';
  return 'neutral';
};

export const aepsAckAllowed = (txn) => {
  if (!txn) return false;
  if (typeof txn.ack_allowed === 'boolean') return txn.ack_allowed;
  const product = String(txn.product || '').toUpperCase();
  if (['BE', 'MS', '2FA'].includes(product)) return false;
  return txn.status === 'success' && !txn.acknowledged;
};

export const aepsNeedsStatusCheck = (txn) => {
  if (!txn?.merchant_tran_id) return false;
  const product = String(txn.product || '').toUpperCase();
  if (!['CW', 'BE', 'MS', 'AP', 'CD', 'CD_OTP'].includes(product)) return false;
  // OTP mid-flow before deposit submit — status check is not useful yet
  if (txn.cd_otp_mode && ['generate', 'otp_sent', 'otp_validated', 'generate_failed'].includes(String(txn.cd_otp_step || ''))) {
    if (txn.status === 'pending' && !txn.fp_transaction_id && txn.cd_otp_step !== 'completed') {
      return false;
    }
  }
  return true;
};

/** Normalize API / result wrapper into a flat txn object. */
export const normalizeAepsTxn = (result) => {
  if (!result) return null;
  if (result.transaction) return result.transaction;
  return result;
};

export const aepsBalanceLabel = (txn) => {
  if (!txn) return null;
  const data = txn.provider_data || txn.provider_meta?.data || {};
  const candidates = [
    txn.balance_amount,
    data.balanceAmount,
    data.bankAccountBalance,
    data.miniStatementBalance,
  ];
  for (const raw of candidates) {
    if (raw == null || raw === '') continue;
    const n = Number(String(raw).replace(/,/g, '').trim());
    if (Number.isFinite(n) && n >= 0) {
      return `₹${n.toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
    }
  }
  return null;
};

/** Off-us Fingpay lines arrive as string chunks: "13/10/2026  Dr  89  Narration..." */
const OFFUS_ROW_RE = /(\d{2}\/\d{2}\/\d{4})\s+(Dr|Cr)\s+(\d+(?:\.\d+)?)\s*/gi;
const OFFUS_TRAILING_BALANCE_RE = /Balance\s+[\d.,]+\s*$/i;

const normalizeStatementRow = (row) => {
  if (!row || typeof row !== 'object') {
    return { date: '', txnType: '', amount: '', narration: '' };
  }
  return {
    date: String(row.date || row.txnDate || row.transactionDate || '').trim(),
    txnType: String(row.txnType || row.type || row.debitCredit || '').trim(),
    amount: String(row.amount || row.txnAmount || row.transactionAmount || '').trim(),
    narration: String(row.narration || row.remarks || row.remark || row.description || '').trim(),
  };
};

export const parseOffusStatementText = (text) => {
  const blob = String(text || '')
    .replace(OFFUS_TRAILING_BALANCE_RE, '')
    .trim();
  if (!blob) return [];

  const matches = [...blob.matchAll(OFFUS_ROW_RE)];
  if (!matches.length) {
    return [{ date: '', txnType: '', amount: '', narration: blob.slice(0, 500) }];
  }

  return matches.map((match, i) => {
    const narrStart = match.index + match[0].length;
    const narrEnd = i + 1 < matches.length ? matches[i + 1].index : blob.length;
    return {
      date: match[1],
      txnType: `${match[2].slice(0, 1).toUpperCase()}${match[2].slice(1).toLowerCase()}`,
      amount: String(match[3] || '').trim(),
      narration: blob.slice(narrStart, narrEnd).trim(),
    };
  });
};

export const normalizeMiniStatementLines = (raw) => {
  if (!Array.isArray(raw) || !raw.length) return [];

  if (raw.every((item) => item && typeof item === 'object' && !Array.isArray(item))) {
    return raw.map(normalizeStatementRow);
  }

  if (raw.every((item) => typeof item === 'string')) {
    return parseOffusStatementText(raw.join(''));
  }

  const rows = raw.filter((item) => item && typeof item === 'object' && !Array.isArray(item)).map(normalizeStatementRow);
  const strings = raw.filter((item) => typeof item === 'string');
  if (strings.length) rows.push(...parseOffusStatementText(strings.join('')));
  return rows;
};

export const aepsStatementRows = (txn) => {
  const data = txn?.provider_data || txn?.provider_meta?.data || {};
  const offusFlag = Boolean(data.miniOffusFlag);
  const ordered = offusFlag
    ? [
        txn?.mini_statement,
        data.miniOffusStatementStructureModel,
        data.miniStatementStructureModel,
        data.miniStatement,
        data.statement,
      ]
    : [
        txn?.mini_statement,
        data.miniStatementStructureModel,
        data.miniOffusStatementStructureModel,
        data.miniStatement,
        data.statement,
      ];

  for (const candidate of ordered) {
    if (!Array.isArray(candidate) || !candidate.length) continue;
    const rows = normalizeMiniStatementLines(candidate);
    if (rows.length) return rows;
  }
  return [];
};

/** Split agent-facing message vs support context line. */
export const splitAepsMessage = (raw) => {
  const full = String(raw || '').trim();
  if (!full) return { headline: '', support: '' };
  const idx = full.toLowerCase().indexOf('support context:');
  if (idx === -1) return { headline: full, support: '' };
  return {
    headline: full.slice(0, idx).trim(),
    support: full.slice(idx).replace(/^support context:\s*/i, '').trim(),
  };
};

export const aepsBankLabel = (txn) => {
  const name = String(txn?.bank_name || '').trim();
  const iin = String(txn?.bank_iin || '').trim();
  if (name && iin && name !== iin) return `${name} (${iin})`;
  if (name) return name;
  if (iin) return iin;
  return '—';
};

export const buildAepsReceiptRows = (txn, { includeBalance = false } = {}) => {
  if (!txn) return [];
  const bal = aepsBalanceLabel(txn);
  const product = String(txn.product || '').toUpperCase();
  const isEnquiry = product === 'BE' || product === 'MS';
  // Enquiry receipts already show balance as a hero — skip the duplicate grid cell.
  const showBalanceInGrid = includeBalance || (!isEnquiry && Boolean(bal));
  return [
    { label: 'Product', value: displayValue(txn.product_label || aepsProductLabel(txn.product)) },
    { label: 'Status', value: displayValue(txn.status), highlight: aepsStatusTone(txn.status) },
    ...(isEnquiry
      ? []
      : [{ label: 'Amount', value: formatAepsAmount(txn.amount), highlight: 'amount' }]),
    { label: 'Bank RRN', value: displayValue(txn.bank_rrn), mono: true },
    { label: 'Txn ID', value: displayValue(txn.merchant_tran_id), mono: true },
    { label: 'Network ref', value: displayValue(txn.fp_transaction_id), mono: true },
    { label: 'Bank', value: aepsBankLabel(txn) },
    { label: 'Aadhaar', value: displayValue(txn.masked_aadhaar), mono: true },
    { label: 'Mobile', value: displayValue(txn.customer_mobile) },
    { label: 'Response code', value: displayValue(txn.response_code), mono: true },
    ...(showBalanceInGrid ? [{ label: 'Available balance', value: bal, highlight: 'success' }] : []),
    { label: 'When', value: formatAepsDateTime(txn.created_at) },
  ];
};

export const buildAepsReceiptPrintContext = (txn) => {
  const tone = aepsStatusTone(txn?.status);
  const { headline } = splitAepsMessage(txn?.response_message);
  return {
    title: 'AEPS Receipt',
    productLabel: txn?.product_label || aepsProductLabel(txn?.product),
    status: displayValue(txn?.status),
    statusTone: tone,
    amount: formatAepsAmount(txn?.amount),
    rrn: displayValue(txn?.bank_rrn),
    merchantTranId: displayValue(txn?.merchant_tran_id),
    fpId: displayValue(txn?.fp_transaction_id),
    bank: aepsBankLabel(txn),
    aadhaar: displayValue(txn?.masked_aadhaar),
    mobile: displayValue(txn?.customer_mobile),
    balance: aepsBalanceLabel(txn) || '—',
    when: formatAepsDateTime(txn?.created_at),
    response: displayValue(headline || txn?.response_message),
    statementRows: aepsStatementRows(txn),
  };
};
