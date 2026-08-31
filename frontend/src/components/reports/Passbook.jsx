import React, { useState, useEffect, useCallback, useRef } from 'react';
import { useAuth } from '../../context/AuthContext';
import { FiDownload } from 'react-icons/fi';
import { passbookAPI, reportsAPI } from '../../services/api';
import { canUseTeamReportScope } from '../../utils/rolePermissions';
import { formatCurrency, formatDateTime } from '../../utils/formatters';
import { formatReportBalance } from '../../utils/reportBalanceDisplay';
import ReportDateRange from '../common/ReportDateRange';
import ReportPagination from '../common/ReportPagination';
import { countActiveReportFilters } from '../../utils/reportFilters';
import {
  CollapsibleReportFilters,
  FILTER_INPUT_CLASS,
  ReportFilterDateRow,
  ReportFilterField,
  ReportFilterGrid,
} from '../common/ReportFilterPanel';

const DEFAULT_PAGE_SIZE = 25;

const Passbook = () => {
  const { user } = useAuth();
  const userId = user?.id ?? user?.user_id;
  const fetchIdRef = useRef(0);
  const [reportScope, setReportScope] = useState('self');
  const [entries, setEntries] = useState([]);
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(DEFAULT_PAGE_SIZE);
  const [total, setTotal] = useState(0);
  const [filters, setFilters] = useState({
    search: '',
    dateFrom: '',
    dateTo: '',
    mobile: '',
    amountMin: '',
    amountMax: '',
  });
  const [appliedFilters, setAppliedFilters] = useState({
    search: '',
    dateFrom: '',
    dateTo: '',
    mobile: '',
    amountMin: '',
    amountMax: '',
  });
  const [loading, setLoading] = useState(true);
  const [hasLoadedOnce, setHasLoadedOnce] = useState(false);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [showFilters, setShowFilters] = useState(false);
  const [summary, setSummary] = useState({
    openingBalance: 0,
    creditAmount: 0,
    debitAmount: 0,
    availableBalance: 0,
  });

  const loadPassbook = useCallback(async () => {
    if (!userId) return;

    const runId = ++fetchIdRef.current;
    if (hasLoadedOnce) setIsRefreshing(true);
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

      const result = await passbookAPI.getPassbookEntries(params);
      if (runId !== fetchIdRef.current) return;
      if (!result.success) {
        setEntries([]);
        setTotal(0);
        setSummary({
          openingBalance: 0,
          creditAmount: 0,
          debitAmount: 0,
          availableBalance: 0,
        });
        return;
      }

      setTotal(Number(result.data?.total) || 0);

      const ps = result.data?.period_summary;
      if (ps) {
        setSummary({
          openingBalance: parseFloat(ps.opening_balance) || 0,
          creditAmount: parseFloat(ps.total_credits) || 0,
          debitAmount: parseFloat(ps.total_debits) || 0,
          availableBalance: parseFloat(ps.closing_balance) || 0,
        });
      }

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

      if (!ps) {
        if (sortedEntries.length > 0) {
          const creditTotal = sortedEntries.reduce((sum, entry) => sum + (entry.creditAmount || 0), 0);
          const debitTotal = sortedEntries.reduce((sum, entry) => sum + (entry.debitAmount || 0), 0);
          const oldest = sortedEntries[sortedEntries.length - 1];
          const newest = sortedEntries[0];

          setSummary({
            openingBalance: oldest.openingBalance || 0,
            creditAmount: creditTotal,
            debitAmount: debitTotal,
            availableBalance: newest.closingBalance || 0,
          });
        } else {
          setSummary({
            openingBalance: 0,
            creditAmount: 0,
            debitAmount: 0,
            availableBalance: 0,
          });
        }
      }
    } catch (error) {
      if (runId !== fetchIdRef.current) return;
      console.error('Error loading passbook:', error);
      setEntries([]);
      setTotal(0);
      setSummary({
        openingBalance: 0,
        creditAmount: 0,
        debitAmount: 0,
        availableBalance: 0,
      });
    } finally {
      if (runId !== fetchIdRef.current) return;
      setLoading(false);
      setIsRefreshing(false);
      setHasLoadedOnce(true);
    }
  }, [userId, user?.role, appliedFilters, reportScope, page, pageSize, hasLoadedOnce]);

  useEffect(() => {
    loadPassbook();
  }, [loadPassbook]);

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
          onClear={() => {
            const cleared = {
              search: '',
              dateFrom: '',
              dateTo: '',
              mobile: '',
              amountMin: '',
              amountMax: '',
            };
            setFilters(cleared);
            setPage(1);
            setAppliedFilters(cleared);
          }}
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

        {/* Summary Cards */}
        <div className="grid grid-cols-1 md:grid-cols-4 gap-3 mb-4">
          <div className="bg-blue-50 dark:bg-blue-950/40 border-2 border-blue-200 dark:border-blue-800 rounded-lg p-4">
            <p className="text-sm text-gray-600 dark:text-slate-400 mb-1">OPENING BALANCE</p>
            <p className="text-2xl font-bold text-blue-600 dark:text-blue-400">{formatCurrency(summary.openingBalance)}</p>
          </div>
          <div className="bg-green-50 dark:bg-green-950/40 border-2 border-green-200 dark:border-green-800 rounded-lg p-4">
            <p className="text-sm text-gray-600 dark:text-slate-400 mb-1">CREDIT AMOUNT</p>
            <p className="text-2xl font-bold text-green-600 dark:text-green-400">{formatCurrency(summary.creditAmount)}</p>
          </div>
          <div className="bg-red-50 dark:bg-red-950/40 border-2 border-red-200 dark:border-red-800 rounded-lg p-4">
            <p className="text-sm text-gray-600 dark:text-slate-400 mb-1">DEBIT AMOUNT</p>
            <p className="text-2xl font-bold text-red-600 dark:text-red-400">{formatCurrency(summary.debitAmount)}</p>
          </div>
          <div className="bg-purple-50 dark:bg-purple-950/40 border-2 border-purple-200 dark:border-purple-800 rounded-lg p-4">
            <p className="text-sm text-gray-600 dark:text-slate-400 mb-1">AVAILABLE BALANCE</p>
            <p className="text-2xl font-bold text-purple-600 dark:text-purple-400">{formatCurrency(summary.availableBalance)}</p>
          </div>
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
          <div className="overflow-x-auto">
            <table className="w-full border-collapse">
              <thead>
                <tr className="bg-gray-50 dark:bg-slate-800/50 border-b border-gray-200 dark:border-slate-700">
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
                    <td className="px-4 py-3 text-sm text-gray-700 dark:text-slate-300">{formatDateTime(entry.date)}</td>
                    <td className="px-4 py-3 text-sm text-gray-900 dark:text-slate-100 font-medium">{entry.service || '-'}</td>
                    <td className="px-4 py-3 text-sm text-gray-700 dark:text-slate-300">{entry.serviceId || '-'}</td>
                    <td className="px-4 py-3 text-sm text-gray-700 dark:text-slate-300 max-w-md">{entry.description || '-'}</td>
                    <td className="px-4 py-3 text-sm text-gray-600 dark:text-slate-400">{entry.ownerUserId || '—'}</td>
                    <td className="px-4 py-3 text-sm text-gray-700 dark:text-slate-300 text-right">
                      {entry.serviceCharge > 0 ? formatCurrency(entry.serviceCharge) : '—'}
                    </td>
                    <td className="px-4 py-3 text-sm text-red-600 dark:text-red-400 text-right font-medium">
                      {entry.debitAmount > 0 ? formatCurrency(entry.debitAmount) : '-'}
                    </td>
                    <td className="px-4 py-3 text-sm text-green-600 dark:text-green-400 text-right font-medium">
                      {entry.creditAmount > 0 ? formatCurrency(entry.creditAmount) : '-'}
                    </td>
                    <td className="px-4 py-3 text-sm text-gray-700 dark:text-slate-300">{entry.cl || '-'}</td>
                    <td className="px-4 py-3 text-sm text-gray-900 dark:text-slate-100 text-right">
                      {formatReportBalance(entry.openingBalance)}
                    </td>
                    <td className="px-4 py-3 text-sm text-gray-900 dark:text-slate-100 text-right font-semibold">
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
