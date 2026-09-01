import React, { useState, useEffect, useCallback, useRef } from 'react';
import { FiDownload } from 'react-icons/fi';
import { useAuth } from '../../context/AuthContext';
import { reportsAPI } from '../../services/api';
import { canUseTeamReportScope } from '../../utils/rolePermissions';
import { formatCurrency, formatDateTime } from '../../utils/formatters';
import ReportDateRange from '../common/ReportDateRange';
import ReportPagination from '../common/ReportPagination';
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

const CommissionReport = () => {
  const { user } = useAuth();
  const userId = user?.id ?? user?.user_id;
  const fetchIdRef = useRef(0);
  const [commissions, setCommissions] = useState([]);
  const [loading, setLoading] = useState(true);
  const [hasLoadedOnce, setHasLoadedOnce] = useState(false);
  const hasLoadedOnceRef = useRef(false);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(DEFAULT_PAGE_SIZE);
  const [total, setTotal] = useState(0);
  const [totalCommission, setTotalCommission] = useState(0);
  const [reportScope, setReportScope] = useState('self');
  const [filters, setFilters] = useState({
    dateFrom: '',
    dateTo: '',
    mobile: '',
    agentRole: '',
    serviceId: '',
  });
  const [appliedFilters, setAppliedFilters] = useState({
    dateFrom: '',
    dateTo: '',
    mobile: '',
    agentRole: '',
    serviceId: '',
  });
  const [showFilters, setShowFilters] = useState(false);

  const loadCommissions = useCallback(async () => {
    if (!userId) return;

    const runId = ++fetchIdRef.current;
    if (hasLoadedOnceRef.current) setIsRefreshing(true);
    else setLoading(true);
    try {
      const params = { page, page_size: pageSize };
      if (reportScope === 'team' && canUseTeamReportScope(user?.role)) params.scope = 'team';
      if (appliedFilters.dateFrom) params.date_from = appliedFilters.dateFrom;
      if (appliedFilters.dateTo) params.date_to = appliedFilters.dateTo;
      if (appliedFilters.mobile.trim()) params.mobile = appliedFilters.mobile.trim();
      if (appliedFilters.agentRole.trim()) params.agent_role = appliedFilters.agentRole.trim();
      if (appliedFilters.serviceId.trim()) params.service_id = appliedFilters.serviceId.trim();
      const result = await reportsAPI.getCommissionReport(params);
      if (runId !== fetchIdRef.current) return;
      if (!result.success) {
        setCommissions([]);
        setTotal(0);
        setTotalCommission(0);
        return;
      }

      setTotal(Number(result.data?.total) || 0);

      const rawLedger = result.data?.ledger || [];

      if (rawLedger.length > 0) {
        const mapped = rawLedger.map((row) => {
          const m = row.meta || {};
          return {
            id: `ledger-${row.id}`,
            date: row.created_at,
            fromUser: row.source_name_snapshot || m.source_name || '—',
            fromUserId: row.source_user_code || m.source_user_code || '—',
            fromRole: row.source_role || m.source_role || '—',
            transactionId: row.reference_service_id || '—',
            transactionAmount: null,
            commissionRate: m.slice || null,
            commissionAmount: parseFloat(row.amount) || 0,
            status: 'SUCCESS',
          };
        });
        setCommissions(mapped);
        const lt = result.data?.summary?.ledger_total;
        if (lt != null && !Number.isNaN(parseFloat(lt))) {
          setTotalCommission(parseFloat(lt));
        } else {
          setTotalCommission(mapped.reduce((s, c) => s + (c.commissionAmount || 0), 0));
        }
        return;
      }

      const raw = result.data?.transactions || [];
      const mapped = raw.map((row) => ({
        id: row.id,
        date: row.created_at,
        fromUser: row.description || '—',
        fromUserId: '—',
        fromRole: '—',
        transactionId:
          row.reference != null && row.reference !== '' ? String(row.reference) : String(row.id),
        transactionAmount: null,
        commissionRate: null,
        commissionAmount: parseFloat(row.amount) || 0,
        status: 'SUCCESS',
      }));
      setCommissions(mapped);
      const summaryTotal = result.data?.summary?.total_commission;
      if (summaryTotal != null && !Number.isNaN(parseFloat(summaryTotal))) {
        setTotalCommission(parseFloat(summaryTotal));
      } else {
        setTotalCommission(mapped.reduce((sum, c) => sum + (c.commissionAmount || 0), 0));
      }
    } catch (error) {
      if (runId !== fetchIdRef.current) return;
      console.error('Error loading commissions:', error);
      setCommissions([]);
      setTotal(0);
      setTotalCommission(0);
    } finally {
      if (runId !== fetchIdRef.current) return;
      setLoading(false);
      setIsRefreshing(false);
      if (!hasLoadedOnceRef.current) {
        hasLoadedOnceRef.current = true;
        setHasLoadedOnce(true);
      }
    }
  }, [userId, user?.role, reportScope, appliedFilters, page, pageSize]);

  useEffect(() => {
    loadCommissions();
  }, [loadCommissions]);

  return (
    <div className="space-y-4">
      <div className="bg-white dark:bg-slate-900 rounded-xl shadow-sm p-4 sm:p-5 border border-gray-200 dark:border-slate-700">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between mb-3">
          <h2 className="text-xl sm:text-2xl font-bold text-gray-900 dark:text-slate-100">Commission Report</h2>
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
                const params =
                  reportScope === 'team' && canUseTeamReportScope(user?.role) ? { scope: 'team' } : {};
                if (appliedFilters.dateFrom) params.date_from = appliedFilters.dateFrom;
                if (appliedFilters.dateTo) params.date_to = appliedFilters.dateTo;
                if (appliedFilters.mobile.trim()) params.mobile = appliedFilters.mobile.trim();
                if (appliedFilters.agentRole.trim()) params.agent_role = appliedFilters.agentRole.trim();
                if (appliedFilters.serviceId.trim()) params.service_id = appliedFilters.serviceId.trim();
                const res = await reportsAPI.downloadReportCsv('/reports/commission/export.csv', params);
                if (!res.success || !res.blob) return;
                const url = window.URL.createObjectURL(res.blob);
                const a = document.createElement('a');
                a.href = url;
                a.download = 'commission_report.csv';
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
            const cleared = { dateFrom: '', dateTo: '', mobile: '', agentRole: '', serviceId: '' };
            setFilters(cleared);
            setPage(1);
            setAppliedFilters(cleared);
          }}
        >
          <ReportFilterGrid>
            <ReportFilterField label="Source mobile" htmlFor="commission-mobile">
              <input
                id="commission-mobile"
                type="text"
                inputMode="tel"
                value={filters.mobile}
                onChange={(e) => setFilters({ ...filters, mobile: e.target.value })}
                placeholder="Mobile number"
                className={FILTER_INPUT_CLASS}
              />
            </ReportFilterField>
            <ReportFilterField label="Source role" htmlFor="commission-role">
              <input
                id="commission-role"
                type="text"
                value={filters.agentRole}
                onChange={(e) => setFilters({ ...filters, agentRole: e.target.value })}
                placeholder="e.g. Retailer"
                className={FILTER_INPUT_CLASS}
              />
            </ReportFilterField>
            <ReportFilterField label="Pay-in reference" htmlFor="commission-ref">
              <input
                id="commission-ref"
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
              idPrefix="commission"
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
              All my commission
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
              From downline pay-in
            </button>
          </div>
        )}

        <div className="mb-4 p-4 bg-blue-50 dark:bg-blue-950/40 border-2 border-blue-200 dark:border-blue-800 rounded-lg">
          <p className="text-sm text-gray-600 dark:text-slate-400 mb-1">Net commission (this view)</p>
          <p className="text-3xl font-bold text-blue-600 dark:text-blue-400">{formatCurrency(totalCommission)}</p>
        </div>

        {loading && !hasLoadedOnce ? (
          <div className="text-center py-12">
            <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto"></div>
            <p className="mt-4 text-gray-600 dark:text-slate-400">Loading commissions...</p>
          </div>
        ) : hasLoadedOnce && commissions.length === 0 && !isRefreshing ? (
          <div className="text-center py-12 text-gray-500 dark:text-slate-400">No commission records found</div>
        ) : (
          <div className={isRefreshing ? 'opacity-60 pointer-events-none' : ''}>
          <div className="overflow-x-auto">
            <table className="w-full border-collapse">
              <thead>
                <tr className="bg-gray-50 dark:bg-slate-800/50 border-b border-gray-200 dark:border-slate-700">
                  <th className="px-4 py-3 text-left text-sm font-semibold text-gray-700 dark:text-slate-300">DATE & TIME</th>
                  <th className="px-4 py-3 text-left text-sm font-semibold text-gray-700 dark:text-slate-300">SOURCE NAME</th>
                  <th className="px-4 py-3 text-left text-sm font-semibold text-gray-700 dark:text-slate-300">USER ID</th>
                  <th className="px-4 py-3 text-left text-sm font-semibold text-gray-700 dark:text-slate-300">ROLE</th>
                  <th className="px-4 py-3 text-left text-sm font-semibold text-gray-700 dark:text-slate-300">PAY-IN REF</th>
                  <th className="px-4 py-3 text-left text-sm font-semibold text-gray-700 dark:text-slate-300">SLICE / NOTE</th>
                  <th className="px-4 py-3 text-left text-sm font-semibold text-gray-700 dark:text-slate-300">AMOUNT</th>
                  <th className="px-4 py-3 text-left text-sm font-semibold text-gray-700 dark:text-slate-300">STATUS</th>
                </tr>
              </thead>
              <tbody>
                {commissions.map((comm) => (
                  <tr key={comm.id} className="border-b border-gray-200 dark:border-slate-700 hover:bg-gray-50 dark:hover:bg-slate-800">
                    <td className="px-4 py-3 text-sm text-gray-700 dark:text-slate-300">{formatDateTime(comm.date)}</td>
                    <td className="px-4 py-3 text-sm text-gray-900 dark:text-slate-100 font-medium">{comm.fromUser || '-'}</td>
                    <td className="px-4 py-3 text-sm text-gray-700 dark:text-slate-300">{comm.fromUserId || '-'}</td>
                    <td className="px-4 py-3 text-sm text-gray-700 dark:text-slate-300">{comm.fromRole || '—'}</td>
                    <td className="px-4 py-3 text-sm text-gray-700 dark:text-slate-300">{comm.transactionId || '-'}</td>
                    <td className="px-4 py-3 text-sm text-gray-700 dark:text-slate-300">
                      {comm.commissionRate != null ? String(comm.commissionRate) : '—'}
                    </td>
                    <td className="px-4 py-3 text-sm font-semibold text-green-600 dark:text-green-400">
                      {formatCurrency(comm.commissionAmount || 0)}
                    </td>
                    <td className="px-4 py-3">
                      <span className="px-3 py-1 rounded-full text-xs font-semibold bg-green-100 dark:bg-green-900/40 text-green-800 dark:text-green-300 border border-green-200 dark:border-green-800">
                        {comm.status || 'SUCCESS'}
                      </span>
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

export default CommissionReport;
