/**
 * Admin dashboard → reports drill-down URL contract (no React dependencies).
 */

export const DRILLDOWN_QUERY_KEYS = {
  from: 'from',
  module: 'module',
  status: 'status',
  dateFrom: 'date_from',
  dateTo: 'date_to',
  scope: 'scope',
  serviceId: 'service_id',
  openReceipt: 'open_receipt',
};

export const DRILLDOWN_FROM_DASHBOARD = 'dashboard';
export const DRILLDOWN_SCOPE_PLATFORM = 'platform';

const MODULE_REPORT_PATHS = {
  payin: '/reports/payin',
  payout: '/reports/payout',
  bbps: '/reports/bbps',
};

export const DRILLDOWN_MODULES = ['payin', 'payout', 'bbps'];

const VALID_MODULES = new Set(['payin', 'payout', 'bbps']);
const VALID_STATUSES = new Set(['PENDING', 'SUCCESS', 'FAILED']);

/** Map dashboard FAILED → report filter FAILURE (UI select value). */
export function statusForReportFilter(status) {
  const st = String(status || '').toUpperCase();
  if (st === 'FAILED' || st === 'FAILURE') return 'FAILURE';
  if (VALID_STATUSES.has(st)) return st;
  return 'ALL';
}

/** Map report FAILURE → API FAILED. */
export function statusForReportApi(status) {
  const st = String(status || '').toUpperCase();
  if (st === 'FAILURE') return 'FAILED';
  return st;
}

/**
 * Modules with a non-zero count for a dashboard status (PENDING / SUCCESS / FAILED).
 */
export function modulesWithStatusCount(byModule, statusKey) {
  if (!byModule || !statusKey) return [];
  return DRILLDOWN_MODULES.filter((key) => Number(byModule[key]?.[statusKey] || 0) > 0);
}

function appendParams(path, params) {
  const search = new URLSearchParams();
  Object.entries(params).forEach(([k, v]) => {
    if (v != null && String(v).trim() !== '') search.set(k, String(v).trim());
  });
  const q = search.toString();
  return q ? `${path}?${q}` : path;
}

/**
 * @param {{ module: string, status: string, dateFrom?: string, dateTo?: string }} opts
 */
export function buildModuleReportDrillDownUrl({ module, status, dateFrom, dateTo }) {
  const mod = String(module || '').toLowerCase();
  const base = MODULE_REPORT_PATHS[mod] || MODULE_REPORT_PATHS.payin;
  const filterStatus = statusForReportFilter(status);
  return appendParams(base, {
    [DRILLDOWN_QUERY_KEYS.from]: DRILLDOWN_FROM_DASHBOARD,
    [DRILLDOWN_QUERY_KEYS.scope]: DRILLDOWN_SCOPE_PLATFORM,
    [DRILLDOWN_QUERY_KEYS.status]: filterStatus === 'ALL' ? '' : filterStatus,
    [DRILLDOWN_QUERY_KEYS.dateFrom]: dateFrom || '',
    [DRILLDOWN_QUERY_KEYS.dateTo]: dateTo || '',
  });
}

/**
 * Hub entry when widget module filter is "all" — Reports.jsx shows module picker.
 * @param {{ status: string, dateFrom?: string, dateTo?: string }} opts
 */
export function buildAllModulesDrillDownUrl({ status, dateFrom, dateTo }) {
  const filterStatus = statusForReportFilter(status);
  return appendParams(MODULE_REPORT_PATHS.payin, {
    [DRILLDOWN_QUERY_KEYS.from]: DRILLDOWN_FROM_DASHBOARD,
    [DRILLDOWN_QUERY_KEYS.module]: 'all',
    [DRILLDOWN_QUERY_KEYS.scope]: DRILLDOWN_SCOPE_PLATFORM,
    [DRILLDOWN_QUERY_KEYS.status]: filterStatus === 'ALL' ? '' : filterStatus,
    [DRILLDOWN_QUERY_KEYS.dateFrom]: dateFrom || '',
    [DRILLDOWN_QUERY_KEYS.dateTo]: dateTo || '',
  });
}

/**
 * @param {URLSearchParams | string} raw
 * @returns {{
 *   fromDashboard: boolean,
 *   fromRevenue: boolean,
 *   moduleAll: boolean,
 *   scope: string,
 *   openReceipt: boolean,
 *   filters: { status: string, dateFrom: string, dateTo: string, serviceId: string },
 *   hasDrillDown: boolean,
 * }}
 */
export function parseDrillDownSearchParams(raw) {
  const params = typeof raw === 'string' ? new URLSearchParams(raw) : raw;
  const from = (params.get(DRILLDOWN_QUERY_KEYS.from) || '').trim();
  const module = (params.get(DRILLDOWN_QUERY_KEYS.module) || '').trim().toLowerCase();
  const scope = (params.get(DRILLDOWN_QUERY_KEYS.scope) || '').trim().toLowerCase();
  const statusRaw = (params.get(DRILLDOWN_QUERY_KEYS.status) || '').trim().toUpperCase();
  const dateFrom = (params.get(DRILLDOWN_QUERY_KEYS.dateFrom) || '').trim();
  const dateTo = (params.get(DRILLDOWN_QUERY_KEYS.dateTo) || '').trim();
  const serviceId = (params.get(DRILLDOWN_QUERY_KEYS.serviceId) || '').trim();
  const openReceipt = ['1', 'true', 'yes'].includes(
    (params.get(DRILLDOWN_QUERY_KEYS.openReceipt) || '').trim().toLowerCase()
  );

  let status = 'ALL';
  if (statusRaw === 'FAILURE' || statusRaw === 'FAILED') status = 'FAILURE';
  else if (VALID_STATUSES.has(statusRaw)) status = statusRaw;

  const hasDrillDown = Boolean(
    from === DRILLDOWN_FROM_DASHBOARD ||
      from === 'revenue' ||
      scope === DRILLDOWN_SCOPE_PLATFORM ||
      status !== 'ALL' ||
      dateFrom ||
      dateTo ||
      serviceId
  );

  return {
    fromDashboard: from === DRILLDOWN_FROM_DASHBOARD,
    fromRevenue: from === 'revenue',
    moduleAll: module === 'all',
    scope: scope === DRILLDOWN_SCOPE_PLATFORM ? DRILLDOWN_SCOPE_PLATFORM : '',
    openReceipt,
    filters: { status, dateFrom, dateTo, serviceId },
    hasDrillDown,
  };
}

export function drillDownAriaLabel({ moduleLabel, status, count, periodLabel }) {
  const st = String(status || '').toLowerCase();
  const n = Number(count) || 0;
  const mod = moduleLabel ? `${moduleLabel} ` : '';
  const period = periodLabel ? ` for ${periodLabel}` : '';
  return `View ${n} ${st} ${mod}transaction${n === 1 ? '' : 's'}${period}`;
}

export { MODULE_REPORT_PATHS, VALID_MODULES };
