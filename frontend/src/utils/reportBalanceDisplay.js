import { formatCurrency } from './formatters';

/** Display passbook balance on report tables; empty → em dash. */
export function formatReportBalance(value) {
  if (value == null || value === '') return '—';
  const n = parseFloat(value);
  if (Number.isNaN(n)) return '—';
  return formatCurrency(n);
}

/** Normalize opening/closing from API row or mapped transaction object. */
export function balanceFromRow(row) {
  if (!row) {
    return { opening: '', closing: '' };
  }
  return {
    opening: row.opening_balance ?? row.openingBalance ?? '',
    closing:
      row.closing_balance ??
      row.closingBalance ??
      row.current_balance ??
      row.currentBalance ??
      '',
  };
}
