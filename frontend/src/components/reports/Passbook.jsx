import React, { useState, useEffect, useCallback, useRef } from 'react';
import { useAuth } from '../../context/AuthContext';
import { FiDownload } from 'react-icons/fi';
import { passbookAPI, reportsAPI } from '../../services/api';
import { canUseTeamReportScope } from '../../utils/rolePermissions';
import { formatCurrency, formatDateTime } from '../../utils/formatters';
import { formatReportBalance } from '../../utils/reportBalanceDisplay';
import { reportPeriodFilterDates } from '../../utils/reportPeriodRange';
import ReportDateRange from '../common/ReportDateRange';
import ReportPagination from '../common/ReportPagination';
import ReportSummaryPeriodToggle from '../common/ReportSummaryPeriodToggle';
import { countActiveReportFilters } from '../../utils/reportFilters';
import {
  CollapsibleReportFilters,
  FILTER_INPUT_CLASS,
  ReportFilterDateRow,
  ReportFilterField,
  ReportFilterGrid,
} from '../common/ReportFilterPanel';

const DEFAULT_PAGE_SIZE = 25;

const EMPTY_PASSBOOK_FILTERS = {
  search: '',
  dateFrom: '',
  dateTo: '',
  mobile: '',
  amountMin: '',
  amountMax: '',
  includeLegacy: false,
};

const Passbook = () => {
  const { user } = useAuth();
  const userId = user?.id ?? user?.user_id;
  const fetchIdRef = useRef(0);
  const [reportScope, setReportScope] = useState('self');
  const [entries, setEntries] = useState([]);
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(DEFAULT_PAGE_SIZE);
  const [total, setTotal] = useState(0);
  const [summaryPeriod, setSummaryPeriod] = useState('day');
  const [filters, setFilters] = useState({ ...EMPTY_PASSBOOK_FILTERS });
  const [appliedFilters, setAppliedFilters] = useState({ ...EMPTY_PASSBOOK_FILTERS });
  const [loading, setLoading] = useState(true);
  const [hasLoadedOnce, setHasLoadedOnce] = useState(false);
  const hasLoadedOnceRef = useRef(false);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [showFilters, setShowFilters] = useState(false);

  const loadPassbook = useCallback(async () => {
    if (!userId) return;

    const runId = ++fetchIdRef.current;
    if (hasLoadedOnceRef.current) setIsRefreshing(true);
    else setLoading(true);
    try {
      const params = { page, page_size: pageSize };
      if (reportScope === 'team' && canUseTeamReportScope(user?.role)) {
        params.scope = 'team';
      }
      const q = appliedFilters.search.trim();
      if (q) params.search = q;
      if (appliedFilters.dateFrom) params.date_from = appliedFilters.dateFrom;
      if (appliedFilters.dateTo) params.date_to = appliedFilters.dateTo;
      if (appliedFilters.mobile.trim()) params.mobile = appliedFilters.mobile.trim();
      if (appliedFilters.amountMin) params.amount_min = appliedFilters.amountMin;
      if (appliedFilters.amountMax) params.amount_max = appliedFilters.amountMax;
      if (appliedFilters.includeLegacy) params.include_legacy = true;

      const result = await passbookAPI.getPassbookEntries(params);
      if (runId !== fetchIdRef.current) return;
      if (!result.success) {
        setEntries([]);
        setTotal(0);
        return;
      }

      setTotal(Number(result.data?.total) || 0);

      const raw = result.data?.entries || [];
      const sortedEntries = raw.map((row) => ({
        id: row.id,
        date: row.created_at,
        service: row.service,
        serviceId: row.service_id,
        description: row.description,
        debitAmount: parseFloat(row.debit_amount) || 0,
        creditAmount: parseFloat(row.credit_amount) || 0,
        openingBalance: parseFloat(row.opening_balance) || 0,
        closingBalance: parseFloat(row.closing_balance) || 0,
        cl: row.wallet_type || '—',
        ownerUserId: row.owner_user_id || '',
        serviceCharge: parseFloat(row.service_charge) || 0,
        principalAmount:
          row.principal_amount != null ? parseFloat(row.principal_amount) : null,
      }));

      setEntries(sortedEntries);
    } catch (error) {
      if (runId !== fetchIdRef.current) return;
      console.error('Error loading passbook:', error);
      setEntries([]);
      setTotal(0);
    } finally {
      if (runId !== fetchIdRef.current) return;
      setLoading(false);
      setIsRefreshing(false);
      if (!hasLoadedOnceRef.current) {
        hasLoadedOnceRef.current = true;
        setHasLoadedOnce(true);
      }
    }
  }, [userId, user?.role, appliedFilters, reportScope, page, pageSize]);

  useEffect(() => {
    loadPassbook();
  }, [loadPassbook]);

  const changeSummaryPeriod = (period) => {
    if (!period || period === summaryPeriod) return;
    setSummaryPeriod(period);
    const dates = reportPeriodFilterDates(period);
    setFilters((prev) => ({ ...prev, ...dates }));
    setAppliedFilters((prev) => ({ ...prev, ...dates }));
    setPage(1);
  };

  const clearFilters = () => {
    setSummaryPeriod('day');
    const cleared = { ...EMPTY_PASSBOOK_FILTERS };
    setFilters(cleared);
    setAppliedFilters(cleared);
    setPage(1);
  };

  return (
    <div className="space-y-4">
      <div className="bg-white dark:bg-slate-900 rounded-xl shadow-sm p-4 sm:p-5 border border-gray-200 dark:border-slate-700">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between mb-3">
          <h2 className="text-xl sm:text-2xl font-bold text-gray-900 dark:text-slate-100">Passbook</h2>
        </div>

        <CollapsibleReportFilters
          open={showFilters}
          onOpenChange={setShowFilters}
          activeCount={countActiveReportFilters(appliedFilters)}
          applying={isRefreshing}
          toolbarEnd={
            <button
              type="button"
              onClick={async () => {
                const params = { page: 1, page_size: 5000 };
                if (reportScope === 'team' && canUseTeamReportScope(user?.role)) params.scope = 'team';
                const q = appliedFilters.search.trim();
                if (q) params.search = q;
                if (appliedFilters.dateFrom) params.date_from = appliedFilters.dateFrom;
                if (appliedFilters.dateTo) params.date_to = appliedFilters.dateTo;
                if (appliedFilters.mobile.trim()) params.mobile = appliedFilters.mobile.trim();
                if (appliedFilters.amountMin) params.amount_min = appliedFilters.amountMin;
                if (appliedFilters.amountMax) params.amount_max = appliedFilters.amountMax;
                if (appliedFilters.includeLegacy) params.include_legacy = true;
                const res = await reportsAPI.downloadReportCsv('/reports/passbook/export.csv', params);
                if (!res.success || !res.blob) return;
                const url = window.URL.createObjectURL(res.blob);
                const a = document.createElement('a');
                a.href = url;
                a.download = 'passbook_report.csv';
                a.click();
                window.URL.revokeObjectURL(url);
              }}
              className="inline-flex min-h-[40px] items-center gap-2 rounded-lg border border-gray-300 dark:border-slate-600 bg-white dark:bg-slate-900 px-3.5 py-2 text-sm font-semibold text-gray-800 dark:text-slate-200 shadow-sm hover:bg-gray-50 dark:hover:bg-slate-800"
            >
              <FiDownload className="h-4 w-4" aria-hidden />
              Download CSV
            </button>
          }
          onApply={() => {
            setPage(1);
            setAppliedFilters({ ...filters });
          }}
          onClear={clearFilters}
        >
          <ReportFilterGrid>
            <ReportFilterField label="Search anywhere" htmlFor="passbook-search" span={2}>
              <input
                id="passbook-search"
                type="text"
                value={filters.search}
                onChange={(e) => setFilters({ ...filters, search: e.target.value })}
                placeholder="Service ID or description"
                className={FILTER_INPUT_CLASS}
              />
            </ReportFilterField>
            <ReportFilterField label="Mobile" htmlFor="passbook-mobile">
              <input
                id="passbook-mobile"
                type="text"
                inputMode="tel"
                value={filters.mobile}
                onChange={(e) => setFilters({ ...filters, mobile: e.target.value })}
                placeholder="Mobile number"
                className={FILTER_INPUT_CLASS}
              />
            </ReportFilterField>
            <ReportFilterField label="Amount min" htmlFor="passbook-amount-min">
              <input
                id="passbook-amount-min"
                type="text"
                inputMode="decimal"
                value={filters.amountMin}
                onChange={(e) => setFilters({ ...filters, amountMin: e.target.value })}
                placeholder="Min"
                className={FILTER_INPUT_CLASS}
              />
            </ReportFilterField>
            <ReportFilterField label="Amount max" htmlFor="passbook-amount-max">
              <input
                id="passbook-amount-max"
                type="text"
                inputMode="decimal"
                value={filters.amountMax}
                onChange={(e) => setFilters({ ...filters, amountMax: e.target.value })}
                placeholder="Max"
                className={FILTER_INPUT_CLASS}
              />
            </ReportFilterField>
          </ReportFilterGrid>
          <ReportFilterDateRow>
            <ReportDateRange
              idPrefix="passbook"
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
          <div className="mt-3 flex items-center gap-2">
            <input
              id="passbook-include-legacy"
              type="checkbox"
              checked={Boolean(filters.includeLegacy)}
              onChange={(e) => setFilters({ ...filters, includeLegacy: e.target.checked })}
              className="h-4 w-4 rounded border-slate-300 text-blue-600 focus:ring-blue-500"
            />
            <label htmlFor="passbook-include-legacy" className="text-sm text-slate-700 dark:text-slate-300">
              Include legacy wallets
            </label>
          </div>
        </CollapsibleReportFilters>

        {canUseTeamReportScope(user?.role) && (
          <div className="flex flex-wrap gap-2 mb-4">
            <button
              type="button"
              onClick={() => setReportScope('self')}
              className={`px-4 py-2 rounded-lg text-sm font-semibold border ${
                reportScope === 'self'
                  ? 'bg-blue-600 text-white border-blue-600'
                  : 'bg-white dark:bg-slate-900 text-gray-700 dark:text-slate-300 border-gray-300 dark:border-slate-600'
              }`}
            >
              My wallets
            </button>
            <button
              type="button"
              onClick={() => setReportScope('team')}
              className={`px-4 py-2 rounded-lg text-sm font-semibold border ${
                reportScope === 'team'
                  ? 'bg-blue-600 text-white border-blue-600'
                  : 'bg-white dark:bg-slate-900 text-gray-700 dark:text-slate-300 border-gray-300 dark:border-slate-600'
              }`}
            >
              Team passbooks
            </button>
          </div>
        )}

        <div className="mb-4">
          <ReportSummaryPeriodToggle
            period={summaryPeriod}
            onChange={changeSummaryPeriod}
            refreshing={isRefreshing && hasLoadedOnce}
          />
        </div>

        {/* Passbook Table */}
        {loading && !hasLoadedOnce ? (
          <div className="text-center py-12">
            <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto"></div>
            <p className="mt-4 text-gray-600 dark:text-slate-400">Loading passbook...</p>
          </div>
        ) : hasLoadedOnce && entries.length === 0 && !isRefreshing ? (
          <div className="text-center py-12 text-gray-500 dark:text-slate-400">No passbook entries found</div>
        ) : (
          <div className={isRefreshing ? 'opacity-60 pointer-events-none' : ''}>
          <div className="-mx-2 overflow-x-auto sm:mx-0">
            <table className="w-full min-w-[1100px] border-collapse whitespace-nowrap">
              <thead>
                <tr className="bg-gray-50 dark:bg-slate-800/50 border-b border-gray-200 dark:border-slate-700">
                  <th className="px-4 py-3 text-left text-sm font-semibold text-gray-700 dark:text-slate-300">S.No</th>
                  <th className="px-4 py-3 text-left text-sm font-semibold text-gray-700 dark:text-slate-300">DATE & TIME</th>
                  <th className="px-4 py-3 text-left text-sm font-semibold text-gray-700 dark:text-slate-300">SERVICE</th>
                  <th className="px-4 py-3 text-left text-sm font-semibold text-gray-700 dark:text-slate-300">SERVICE ID</th>
                  <th className="px-4 py-3 text-left text-sm font-semibold text-gray-700 dark:text-slate-300">DESCRIPTION</th>
                  <th className="px-4 py-3 text-left text-sm font-semibold text-gray-700 dark:text-slate-300">USER ID</th>
                  <th className="px-4 py-3 text-right text-sm font-semibold text-gray-700 dark:text-slate-300">CHARGE</th>
                  <th className="px-4 py-3 text-right text-sm font-semibold text-gray-700 dark:text-slate-300">DEBIT AMOUNT</th>
                  <th className="px-4 py-3 text-right text-sm font-semibold text-gray-700 dark:text-slate-300">CREDIT AMOUNT</th>
                  <th className="px-4 py-3 text-left text-sm font-semibold text-gray-700 dark:text-slate-300">CL</th>
                  <th className="px-4 py-3 text-right text-sm font-semibold text-gray-700 dark:text-slate-300">OPENING BALANCE</th>
                  <th className="px-4 py-3 text-right text-sm font-semibold text-gray-700 dark:text-slate-300">CLOSING BALANCE</th>
                </tr>
              </thead>
              <tbody>
                {entries.map((entry, index) => (
                  <tr key={entry.id || index} className="border-b border-gray-200 dark:border-slate-700 hover:bg-gray-50 dark:hover:bg-slate-800">
                    <td className="px-4 py-2.5 text-sm text-gray-600 dark:text-slate-400">{(page - 1) * pageSize + index + 1}</td>
                    <td className="px-4 py-2.5 text-sm text-gray-700 dark:text-slate-300">{formatDateTime(entry.date)}</td>
                    <td className="px-4 py-2.5 text-sm text-gray-900 dark:text-slate-100 font-medium">{entry.service || '-'}</td>
                    <td className="px-4 py-2.5 text-sm text-gray-700 dark:text-slate-300">{entry.serviceId || '-'}</td>
                    <td className="px-4 py-2.5 text-sm text-gray-700 dark:text-slate-300">{entry.description || '-'}</td>
                    <td className="px-4 py-2.5 text-sm text-gray-600 dark:text-slate-400">{entry.ownerUserId || '—'}</td>
                    <td className="px-4 py-2.5 text-sm text-gray-700 dark:text-slate-300 text-right">
                      {entry.serviceCharge > 0 ? formatCurrency(entry.serviceCharge) : '—'}
                    </td>
                    <td className="px-4 py-2.5 text-sm text-red-600 dark:text-red-400 text-right font-medium">
                      {entry.debitAmount > 0 ? formatCurrency(entry.debitAmount) : '-'}
                    </td>
                    <td className="px-4 py-2.5 text-sm text-green-600 dark:text-green-400 text-right font-medium">
                      {entry.creditAmount > 0 ? formatCurrency(entry.creditAmount) : '-'}
                    </td>
                    <td className="px-4 py-2.5 text-sm text-gray-700 dark:text-slate-300">{entry.cl || '-'}</td>
                    <td className="px-4 py-2.5 text-sm text-gray-900 dark:text-slate-100 text-right">
                      {formatReportBalance(entry.openingBalance)}
                    </td>
                    <td className="px-4 py-2.5 text-sm text-gray-900 dark:text-slate-100 text-right font-semibold">
                      {formatReportBalance(entry.closingBalance)}
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
      </div>
    </div>
  );
};

export default Passbook;
