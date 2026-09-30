/**
 * Deep-link from Revenue/Commission/Service Fee Tracker → underlying transaction reports.
 */
import { DRILLDOWN_SCOPE_PLATFORM, MODULE_REPORT_PATHS } from './dashboardDrillDown';

export function normalizeRevenueModule(moduleOrSource) {
  const raw = String(moduleOrSource || '').trim().toLowerCase();
  if (!raw || raw === '—' || raw === '-') return '';
  if (raw === 'profit' || raw === 'payin' || raw === 'pay-in' || raw === 'pay_in') return 'payin';
  if (raw === 'bbps') return 'bbps';
  if (raw === 'payout' || raw === 'pay-out' || raw === 'pay_out') return 'payout';
  return raw;
}

/**
 * @param {{
 *   module?: string,
 *   source?: string,
 *   serviceId: string,
 *   openReceipt?: boolean,
 *   platformScope?: boolean,
 * }} opts
 * @returns {string|null} path+query or null if no matching report tab
 */
export function buildUnderlyingTxnReportUrl({
  module,
  source,
  serviceId,
  openReceipt = false,
  platformScope = false,
} = {}) {
  const sid = String(serviceId || '').trim();
  if (!sid || sid === '—') return null;
  const mod = normalizeRevenueModule(module || source);
  const base = MODULE_REPORT_PATHS[mod];
  if (!base) return null;
  const params = new URLSearchParams();
  params.set('service_id', sid);
  params.set('from', 'revenue');
  // Admin deep-links must use platform scope — fees/commissions are often from other users.
  if (platformScope) {
    params.set('scope', DRILLDOWN_SCOPE_PLATFORM);
  }
  if (openReceipt && (mod === 'payin' || mod === 'bbps' || mod === 'payout')) {
    params.set('open_receipt', '1');
  }
  return `${base}?${params.toString()}`;
}

export function canOpenUnderlyingReport(moduleOrSource) {
  const mod = normalizeRevenueModule(moduleOrSource);
  return Boolean(MODULE_REPORT_PATHS[mod]);
}

export function canPrintUnderlyingReceipt(moduleOrSource) {
  const mod = normalizeRevenueModule(moduleOrSource);
  return mod === 'payin' || mod === 'bbps' || mod === 'payout';
}
