import React, { useState, useEffect, useCallback, useRef, useMemo } from 'react';
import { FiDownload, FiX, FiExternalLink, FiPrinter } from 'react-icons/fi';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { useAuth } from '../../context/AuthContext';
import { reportsAPI } from '../../services/api';
import { canUseTeamReportScope, isAdminUser } from '../../utils/rolePermissions';
import {
  buildUnderlyingTxnReportUrl,
  canOpenUnderlyingReport,
  canPrintUnderlyingReceipt,
} from '../../utils/reportDeepLink';
import { formatCurrency, formatDateTime } from '../../utils/formatters';
import ReportDateRange from '../common/ReportDateRange';
import ReportPagination from '../common/ReportPagination';
import Card from '../common/Card';
import Button from '../common/Button';
import { countActiveReportFilters } from '../../utils/reportFilters';
import {
  CollapsibleReportFilters,
  FILTER_INPUT_CLASS,
  FILTER_SELECT_CLASS,
  ReportFilterDateRow,
  ReportFilterField,
  ReportFilterGrid,
} from '../common/ReportFilterPanel';

const DEFAULT_PAGE_SIZE = 25;

const EMPTY_FILTERS = {
  dateFrom: '',
  dateTo: '',
  mobile: '',
  agentRole: '',
  serviceId: '',
  module: '',
  entryKind: '',
};

const MODULE_OPTIONS = [
  { value: '', label: 'All modules' },
  { value: 'payin', label: 'Pay-in' },
  { value: 'bbps', label: 'BBPS' },
  { value: 'payout', label: 'Payout' },
  { value: 'bank_verification', label: 'Bank verify' },
  { value: 'aeps', label: 'AEPS' },
  { value: 'cms', label: 'CMS' },
];

const Metric = ({ label, value }) => (
  <div className="rounded-xl border border-slate-200 bg-white px-3 py-2.5 shadow-sm dark:border-slate-700 dark:bg-slate-900">
    <p className="text-[10px] font-semibold uppercase tracking-wide text-slate-500 dark:text-slate-400">
      {label}
    </p>
    <p className="mt-0.5 text-lg font-bold tabular-nums text-slate-900 dark:text-slate-100 sm:text-xl">
      {value}
    </p>
  </div>
);

const StatusChip = ({ status }) => (
  <span className="inline-flex rounded-full bg-emerald-100 px-2 py-0.5 text-[11px] font-bold uppercase text-emerald-800 dark:bg-emerald-900/40 dark:text-emerald-200">
    {status || 'SUCCESS'}
  </span>
);

const typeLabel = (kind) => {
  if (kind === 'service_fee') return 'Service fee';
  if (kind === 'commission') return 'Commission';
  return kind || '—';
};

const moduleLabel = (mod) => {
  const hit = MODULE_OPTIONS.find((m) => m.value === String(mod || '').toLowerCase());
  return hit?.label || mod || '—';
};

const CommissionReport = () => {
  const { user } = useAuth();
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const isOperator = isAdminUser(user);
  const userId = user?.id ?? user?.user_id;
  const fetchIdRef = useRef(0);
  const [rows, setRows] = useState([]);
  const [loading, setLoading] = useState(true);
  const [hasLoadedOnce, setHasLoadedOnce] = useState(false);
  const hasLoadedOnceRef = useRef(false);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(DEFAULT_PAGE_SIZE);
  const [total, setTotal] = useState(0);
  const [summary, setSummary] = useState(null);
  const [reportScope, setReportScope] = useState('self');
  const initialFromUrl = useMemo(() => {
    const dateFrom = (searchParams.get('date_from') || '').trim();
    const dateTo = (searchParams.get('date_to') || '').trim();
    const serviceId = (searchParams.get('service_id') || '').trim();
    if (!dateFrom && !dateTo && !serviceId) return EMPTY_FILTERS;
    return { ...EMPTY_FILTERS, dateFrom, dateTo, serviceId };
  }, [searchParams]);
  const [filters, setFilters] = useState(initialFromUrl);
  const [appliedFilters, setAppliedFilters] = useState(initialFromUrl);
  const [showFilters, setShowFilters] = useState(
    () => Boolean(initialFromUrl.dateFrom || initialFromUrl.dateTo || initialFromUrl.serviceId)
  );
  const [exportBusy, setExportBusy] = useState(false);
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [drawerLoading, setDrawerLoading] = useState(false);
  const [breakdown, setBreakdown] = useState(null);
  const [selectedRef, setSelectedRef] = useState('');
  const [selectedModule, setSelectedModule] = useState('');

  const buildParams = useCallback(
    (extra = {}) => {
      const params = { ...extra };
      if (reportScope === 'team' && canUseTeamReportScope(user?.role)) params.scope = 'team';
      if (appliedFilters.dateFrom) params.date_from = appliedFilters.dateFrom;
      if (appliedFilters.dateTo) params.date_to = appliedFilters.dateTo;
      if (appliedFilters.mobile.trim()) params.mobile = appliedFilters.mobile.trim();
      if (appliedFilters.agentRole.trim()) params.agent_role = appliedFilters.agentRole.trim();
      if (appliedFilters.serviceId.trim()) params.service_id = appliedFilters.serviceId.trim();
      if (appliedFilters.module) params.module = appliedFilters.module;
      if (appliedFilters.entryKind) params.type = appliedFilters.entryKind;
      return params;
    },
    [appliedFilters, reportScope, user?.role]
  );

  const mapLedgerRows = (rawLedger) =>
    (rawLedger || []).map((row) => {
      const m = row.meta || {};
      return {
        id: `ledger-${row.id}`,
        date: row.created_at,
        reference: row.reference_service_id || '—',
        module: row.module || row.source || '—',
        entryKind: row.entry_kind || 'commission',
        fromUser: row.source_name_snapshot || m.source_name || '—',
        fromRole: row.source_role || m.source_role || '—',
        customerCharge: parseFloat(row.customer_charge) || 0,
        myShare: parseFloat(row.amount) || 0,
        status: 'SUCCESS',
        sliceDisplay: row.slice_display || row.slice_key || m.slice || '',
      };
    });

  const loadReport = useCallback(async () => {
    if (!userId) return;

    const runId = ++fetchIdRef.current;
    if (hasLoadedOnceRef.current) setIsRefreshing(true);
    else setLoading(true);

    try {
      const listParams = buildParams({ page, page_size: pageSize });
      const summaryParams = buildParams();

      const [summaryRes, listRes] = await Promise.all([
        reportsAPI.getRevenueSummary(summaryParams),
        (async () => {
          const revenue = await reportsAPI.getRevenueReport(listParams);
          if (revenue.success) return revenue;
          return reportsAPI.getCommissionReport(listParams);
        })(),
      ]);

      if (runId !== fetchIdRef.current) return;

      if (summaryRes.success) {
        setSummary(summaryRes.data || null);
      } else {
        setSummary(null);
      }

      if (!listRes.success) {
        setRows([]);
        setTotal(0);
        return;
      }

      setTotal(Number(listRes.data?.total) || 0);
      const rawLedger = listRes.data?.ledger || [];
      if (rawLedger.length > 0) {
        setRows(mapLedgerRows(rawLedger));
        return;
      }

      const raw = listRes.data?.transactions || [];
      setRows(
        raw.map((row) => ({
          id: row.id,
          date: row.created_at,
          reference:
            row.reference != null && row.reference !== '' ? String(row.reference) : String(row.id),
          module: '—',
          entryKind: 'commission',
          fromUser: row.description || '—',
          fromRole: '—',
          customerCharge: 0,
          myShare: parseFloat(row.amount) || 0,
          status: 'SUCCESS',
          sliceDisplay: '',
        }))
      );
    } catch (error) {
      if (runId !== fetchIdRef.current) return;
      console.error('Error loading revenue report:', error);
      setRows([]);
      setTotal(0);
      setSummary(null);
    } finally {
      if (runId !== fetchIdRef.current) return;
      setLoading(false);
      setIsRefreshing(false);
      if (!hasLoadedOnceRef.current) {
        hasLoadedOnceRef.current = true;
        setHasLoadedOnce(true);
      }
    }
  }, [userId, buildParams, page, pageSize]);

  useEffect(() => {
    loadReport();
  }, [loadReport]);

  const openBreakdown = async (row) => {
    const ref = String(row.reference || '').trim();
    if (!ref || ref === '—') return;
    setSelectedRef(ref);
    setSelectedModule(row.module || '');
    setDrawerOpen(true);
    setDrawerLoading(true);
    setBreakdown(null);
    const res = await reportsAPI.getRevenueBreakdown(ref);
    if (res.success) {
      setBreakdown(res.data);
    } else {
      setBreakdown({ error: res.message || 'Unable to load breakdown' });
    }
    setDrawerLoading(false);
  };

  const goToUnderlyingReport = (openReceipt = false) => {
    const mod =
      breakdown?.module ||
      selectedModule ||
      breakdown?.slices?.[0]?.module ||
      breakdown?.slices?.[0]?.source ||
      '';
    const url = buildUnderlyingTxnReportUrl({
      module: mod,
      serviceId: selectedRef || breakdown?.reference_service_id,
      openReceipt,
    });
    if (!url) return;
    navigate(url);
  };

  const exportCsv = async () => {
    setExportBusy(true);
    const params = buildParams();
    const res = await reportsAPI.downloadReportCsv('/reports/revenue/export.csv', params);
    if (res.success && res.blob) {
      const url = window.URL.createObjectURL(res.blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = 'revenue_report.csv';
      a.click();
      window.URL.revokeObjectURL(url);
    }
    setExportBusy(false);
  };

  const byModuleEntries = useMemo(() => {
    const bm = summary?.by_module || {};
    return Object.entries(bm).sort((a, b) => String(a[0]).localeCompare(String(b[0])));
  }, [summary]);

  const activeFilterCount = countActiveReportFilters({
    dateFrom: appliedFilters.dateFrom,
    dateTo: appliedFilters.dateTo,
    mobile: appliedFilters.mobile,
    agentRole: appliedFilters.agentRole,
    serviceId: appliedFilters.serviceId,
    module: appliedFilters.module,
    entryKind: appliedFilters.entryKind,
  });

  return (
    <div className="mx-auto w-full max-w-7xl space-y-4">
      <header className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
        <div className="min-w-0">
          <h2 className="text-xl font-bold text-slate-900 dark:text-slate-100 sm:text-2xl">
            Revenue &amp; Commission
          </h2>
          <p className="mt-0.5 text-sm text-slate-500 dark:text-slate-400">
            Earnings and service fees credited to your main wallet
          </p>
        </div>
        <Button
          size="sm"
          variant="secondary"
          loading={exportBusy}
          onClick={exportCsv}
          className="shrink-0 self-start sm:self-auto"
        >
          <FiDownload className="mr-1.5 inline h-4 w-4" aria-hidden />
          Download CSV
        </Button>
      </header>

      <CollapsibleReportFilters
        open={showFilters}
        onOpenChange={setShowFilters}
        activeCount={activeFilterCount}
        applying={isRefreshing}
        onApply={() => {
          setPage(1);
          setAppliedFilters({ ...filters });
        }}
        onClear={() => {
          setFilters(EMPTY_FILTERS);
          setPage(1);
          setAppliedFilters(EMPTY_FILTERS);
        }}
      >
        <ReportFilterGrid>
          <ReportFilterField label="Module" htmlFor="revenue-module">
            <select
              id="revenue-module"
              value={filters.module}
              onChange={(e) => setFilters({ ...filters, module: e.target.value })}
              className={FILTER_SELECT_CLASS}
            >
              {MODULE_OPTIONS.map((o) => (
                <option key={o.value || 'all'} value={o.value}>
                  {o.label}
                </option>
              ))}
            </select>
          </ReportFilterField>
          <ReportFilterField label="Type" htmlFor="revenue-type">
            <select
              id="revenue-type"
              value={filters.entryKind}
              onChange={(e) => setFilters({ ...filters, entryKind: e.target.value })}
              className={FILTER_SELECT_CLASS}
            >
              <option value="">All types</option>
              <option value="commission">Commission</option>
              <option value="service_fee">Service fee</option>
            </select>
          </ReportFilterField>
          <ReportFilterField label="Source mobile" htmlFor="revenue-mobile">
            <input
              id="revenue-mobile"
              type="text"
              inputMode="tel"
              value={filters.mobile}
              onChange={(e) => setFilters({ ...filters, mobile: e.target.value })}
              placeholder="Mobile number"
              className={FILTER_INPUT_CLASS}
            />
          </ReportFilterField>
          <ReportFilterField label="Source role" htmlFor="revenue-role">
            <input
              id="revenue-role"
              type="text"
              value={filters.agentRole}
              onChange={(e) => setFilters({ ...filters, agentRole: e.target.value })}
              placeholder="e.g. Retailer"
              className={FILTER_INPUT_CLASS}
            />
          </ReportFilterField>
          <ReportFilterField label="Reference / service ID" htmlFor="revenue-ref">
            <input
              id="revenue-ref"
              type="text"
              value={filters.serviceId}
              onChange={(e) => setFilters({ ...filters, serviceId: e.target.value })}
              placeholder="Service ID"
              className={FILTER_INPUT_CLASS}
            />
          </ReportFilterField>
        </ReportFilterGrid>
        <ReportFilterDateRow>
          <ReportDateRange
            idPrefix="revenue"
            dateFrom={filters.dateFrom}
            dateTo={filters.dateTo}
            fromLabel="Date from"
            toLabel="Date to"
            compact
            onChange={({ dateFrom, dateTo }) =>
              setFilters((prev) => ({ ...prev, dateFrom, dateTo }))
            }
          />
        </ReportFilterDateRow>
      </CollapsibleReportFilters>

      {canUseTeamReportScope(user?.role) && (
        <div className="flex flex-wrap gap-2">
          <button
            type="button"
            onClick={() => {
              setReportScope('self');
              setPage(1);
            }}
            className={`px-4 py-2 rounded-lg text-sm font-semibold border ${
              reportScope === 'self'
                ? 'bg-blue-600 text-white border-blue-600'
                : 'bg-white dark:bg-slate-900 text-gray-700 dark:text-slate-300 border-gray-300 dark:border-slate-600'
            }`}
          >
            All my commission
          </button>
          <button
            type="button"
            onClick={() => {
              setReportScope('team');
              setPage(1);
            }}
            className={`px-4 py-2 rounded-lg text-sm font-semibold border ${
              reportScope === 'team'
                ? 'bg-blue-600 text-white border-blue-600'
                : 'bg-white dark:bg-slate-900 text-gray-700 dark:text-slate-300 border-gray-300 dark:border-slate-600'
            }`}
          >
            From downline
          </button>
        </div>
      )}

      <div className="grid grid-cols-2 gap-2 sm:grid-cols-3 lg:grid-cols-4">
        <Metric
          label="Total earned"
          value={
            summary?.total_earned != null ? formatCurrency(parseFloat(summary.total_earned) || 0) : '—'
          }
        />
        <Metric
          label="Service fees"
          value={
            summary?.service_fees != null ? formatCurrency(parseFloat(summary.service_fees) || 0) : '—'
          }
        />
        <Metric
          label="Commission"
          value={
            summary?.commission != null ? formatCurrency(parseFloat(summary.commission) || 0) : '—'
          }
        />
        <Metric label="Rows" value={total || summary?.ledger_count || '—'} />
      </div>

      {byModuleEntries.length > 0 && (
        <div className="flex flex-wrap gap-1.5">
          {byModuleEntries.map(([mod, info]) => (
            <span
              key={mod}
              className="inline-flex items-center gap-1.5 rounded-full border border-slate-200 bg-slate-50 px-2.5 py-1 text-xs dark:border-slate-700 dark:bg-slate-800/60"
            >
              <span className="font-semibold text-slate-800 dark:text-slate-100">
                {moduleLabel(mod)}
              </span>
              <span className="tabular-nums text-slate-500 dark:text-slate-400">
                {formatCurrency(parseFloat(info?.total) || 0)}
              </span>
              {info?.count != null && (
                <span className="tabular-nums text-slate-400 dark:text-slate-500">({info.count})</span>
              )}
            </span>
          ))}
        </div>
      )}

      <Card
        title="Ledger"
        shadow="sm"
        className="overflow-hidden"
        subtitle={
          isOperator
            ? 'DATE & TIME · REFERENCE · MODULE · TYPE · SOURCE USER · CUSTOMER CHARGE · MY SHARE · STATUS'
            : 'DATE & TIME · REFERENCE · MODULE · TYPE · SOURCE USER · MY EARNINGS · STATUS'
        }
      >
        {loading && !hasLoadedOnce ? (
          <div className="py-12 text-center text-sm text-slate-500">Loading…</div>
        ) : hasLoadedOnce && rows.length === 0 && !isRefreshing ? (
          <div className="py-12 text-center text-sm text-slate-500">No revenue records found</div>
        ) : (
          <div className={isRefreshing ? 'opacity-60 pointer-events-none' : ''}>
            <div className="-mx-2 overflow-x-auto sm:mx-0">
              <table className={`w-full border-collapse ${isOperator ? 'min-w-[900px]' : 'min-w-[760px]'}`}>
                <thead>
                  <tr className="bg-gray-50 dark:bg-slate-800/50 border-b border-gray-200 dark:border-slate-700">
                    <th className="px-3 py-3 text-left text-xs font-semibold uppercase tracking-wide text-gray-700 dark:text-slate-300">
                      Date &amp; time
                    </th>
                    <th className="px-3 py-3 text-left text-xs font-semibold uppercase tracking-wide text-gray-700 dark:text-slate-300">
                      Reference
                    </th>
                    <th className="px-3 py-3 text-left text-xs font-semibold uppercase tracking-wide text-gray-700 dark:text-slate-300">
                      Module
                    </th>
                    <th className="px-3 py-3 text-left text-xs font-semibold uppercase tracking-wide text-gray-700 dark:text-slate-300">
                      Type
                    </th>
                    <th className="px-3 py-3 text-left text-xs font-semibold uppercase tracking-wide text-gray-700 dark:text-slate-300">
                      Source user
                    </th>
                    {isOperator ? (
                      <th className="px-3 py-3 text-right text-xs font-semibold uppercase tracking-wide text-gray-700 dark:text-slate-300">
                        Customer charge
                      </th>
                    ) : null}
                    <th className="px-3 py-3 text-right text-xs font-semibold uppercase tracking-wide text-gray-700 dark:text-slate-300">
                      {isOperator ? 'My share' : 'My earnings'}
                    </th>
                    <th className="px-3 py-3 text-left text-xs font-semibold uppercase tracking-wide text-gray-700 dark:text-slate-300">
                      Status
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {rows.map((row) => (
                    <tr
                      key={row.id}
                      onClick={() => openBreakdown(row)}
                      className="border-b border-gray-200 dark:border-slate-700 hover:bg-blue-50/60 dark:hover:bg-slate-800 cursor-pointer"
                    >
                      <td className="px-3 py-3 text-sm text-gray-700 dark:text-slate-300 whitespace-nowrap">
                        {formatDateTime(row.date)}
                      </td>
                      <td className="px-3 py-3 text-sm font-mono text-gray-900 dark:text-slate-100">
                        {row.reference}
                      </td>
                      <td className="px-3 py-3 text-sm text-gray-700 dark:text-slate-300">
                        {moduleLabel(row.module)}
                      </td>
                      <td className="px-3 py-3 text-sm text-gray-700 dark:text-slate-300">
                        {typeLabel(row.entryKind)}
                      </td>
                      <td className="px-3 py-3 text-sm text-gray-900 dark:text-slate-100">
                        <span className="font-medium">{row.fromUser}</span>
                        {row.fromRole && row.fromRole !== '—' && (
                          <span className="ml-1 text-xs text-slate-500">({row.fromRole})</span>
                        )}
                      </td>
                      {isOperator ? (
                        <td className="px-3 py-3 text-sm text-right tabular-nums text-gray-700 dark:text-slate-300">
                          {row.customerCharge > 0 ? formatCurrency(row.customerCharge) : '—'}
                        </td>
                      ) : null}
                      <td className="px-3 py-3 text-sm text-right font-semibold tabular-nums text-emerald-600 dark:text-emerald-400">
                        {formatCurrency(row.myShare || 0)}
                      </td>
                      <td className="px-3 py-3">
                        <StatusChip status={row.status} />
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <ReportPagination
              page={page}
              pageSize={pageSize}
              total={total}
              loading={isRefreshing}
              onPageChange={setPage}
              onPageSizeChange={(size) => {
                setPageSize(size);
                setPage(1);
              }}
            />
          </div>
        )}
      </Card>

      {drawerOpen && (
        <div className="fixed inset-0 z-50 flex justify-end">
          <button
            type="button"
            className="absolute inset-0 bg-slate-900/40"
            aria-label="Close breakdown"
            onClick={() => setDrawerOpen(false)}
          />
          <aside className="relative z-10 flex h-full w-full max-w-md flex-col border-l border-slate-200 bg-white shadow-xl dark:border-slate-700 dark:bg-slate-900">
            <div className="flex items-start justify-between gap-3 border-b border-slate-200 px-4 py-4 dark:border-slate-700">
              <div className="min-w-0">
                <h3 className="text-lg font-bold text-slate-900 dark:text-slate-100">
                  {breakdown?.full_split === false || (!isOperator && breakdown && !breakdown.error)
                    ? 'Earnings detail'
                    : 'Transaction split'}
                </h3>
                <p className="mt-0.5 truncate font-mono text-xs text-slate-500">{selectedRef}</p>
              </div>
              <button
                type="button"
                onClick={() => setDrawerOpen(false)}
                className="rounded-lg p-2 text-slate-500 hover:bg-slate-100 dark:hover:bg-slate-800"
              >
                <FiX size={18} />
              </button>
            </div>
            <div className="flex-1 overflow-y-auto p-4">
              {drawerLoading ? (
                <p className="py-8 text-center text-sm text-slate-500">Loading breakdown…</p>
              ) : breakdown?.error ? (
                <p className="py-8 text-center text-sm text-red-600 dark:text-red-400">
                  {breakdown.error}
                </p>
              ) : breakdown?.full_split === false || (!isOperator && breakdown && !breakdown.slices?.length) ? (
                <div className="space-y-4">
                  <div className="rounded-xl border border-emerald-200 bg-emerald-50 p-3 dark:border-emerald-900 dark:bg-emerald-950/40">
                    <p className="text-[10px] font-semibold uppercase tracking-wide text-emerald-700 dark:text-emerald-300">
                      Credited to you
                    </p>
                    <p className="mt-1 text-2xl font-bold tabular-nums text-emerald-900 dark:text-emerald-100">
                      {formatCurrency(parseFloat(breakdown.my_share) || 0)}
                    </p>
                    <p className="mt-1 text-xs text-emerald-800/80 dark:text-emerald-300/80">
                      {typeLabel(breakdown.entry_kind)} · {moduleLabel(breakdown.module || breakdown.source)}
                    </p>
                  </div>
                </div>
              ) : breakdown ? (
                <div className="space-y-4">
                  <div className="rounded-xl border border-slate-200 bg-slate-50 p-3 dark:border-slate-700 dark:bg-slate-800/60">
                    <p className="text-[10px] font-semibold uppercase tracking-wide text-slate-500">
                      Customer charge
                    </p>
                    <p className="mt-1 text-2xl font-bold tabular-nums text-slate-900 dark:text-slate-100">
                      {formatCurrency(parseFloat(breakdown.customer_charge) || 0)}
                    </p>
                    <p className="mt-1 text-xs text-slate-500">
                      {breakdown.slice_count ?? breakdown.slices?.length ?? 0} slice
                      {(breakdown.slice_count ?? breakdown.slices?.length ?? 0) === 1 ? '' : 's'}
                    </p>
                  </div>
                  <ul className="space-y-2">
                    {(breakdown.slices || []).map((s) => (
                      <li
                        key={s.id || `${s.slice_key}-${s.beneficiary_user_id}`}
                        className="rounded-lg border border-slate-200 p-3 dark:border-slate-700"
                      >
                        <div className="flex items-start justify-between gap-2">
                          <div className="min-w-0">
                            <p className="text-sm font-semibold text-slate-900 dark:text-slate-100">
                              {s.slice_key || typeLabel(s.entry_kind)}
                            </p>
                            <p className="text-xs text-slate-500 dark:text-slate-400">
                              {[s.beneficiary_code, s.beneficiary_role, s.source_name]
                                .filter(Boolean)
                                .join(' · ') || '—'}
                            </p>
                            <p className="mt-0.5 text-[11px] uppercase tracking-wide text-slate-400">
                              {typeLabel(s.entry_kind)} · {moduleLabel(s.module || s.source)}
                            </p>
                          </div>
                          <p className="shrink-0 text-sm font-bold tabular-nums text-emerald-600 dark:text-emerald-400">
                            {formatCurrency(parseFloat(s.amount) || 0)}
                          </p>
                        </div>
                      </li>
                    ))}
                  </ul>
                </div>
              ) : (
                <p className="py-8 text-center text-sm text-slate-500">No data</p>
              )}
            </div>
            {breakdown && !breakdown.error ? (
              <div className="flex flex-col gap-2 border-t border-slate-200 p-4 dark:border-slate-700">
                {canOpenUnderlyingReport(
                  breakdown.module ||
                    selectedModule ||
                    breakdown?.slices?.[0]?.module ||
                    breakdown?.slices?.[0]?.source
                ) ? (
                  <Button
                    variant="primary"
                    className="w-full justify-center"
                    icon={FiExternalLink}
                    iconPosition="left"
                    onClick={() => goToUnderlyingReport(false)}
                  >
                    Open in report
                  </Button>
                ) : (
                  <p className="text-center text-xs text-slate-500">
                    No linked Pay-in / Payout / BBPS report for this module.
                  </p>
                )}
                {canPrintUnderlyingReceipt(
                  breakdown.module ||
                    selectedModule ||
                    breakdown?.slices?.[0]?.module ||
                    breakdown?.slices?.[0]?.source
                ) ? (
                  <Button
                    variant="outline"
                    className="w-full justify-center"
                    icon={FiPrinter}
                    iconPosition="left"
                    onClick={() => goToUnderlyingReport(true)}
                  >
                    View / print receipt
                  </Button>
                ) : null}
              </div>
            ) : null}
          </aside>
        </div>
      )}
    </div>
  );
};

export default CommissionReport;
