import React, { useState, useEffect, useCallback, useRef, useMemo } from 'react';
import { useLocation, useNavigate, useSearchParams } from 'react-router-dom';
import { FiDownload } from 'react-icons/fi';
import { bbpsAPI } from '../../services/api';
import { formatCurrency, formatDateTime } from '../../utils/formatters';
import { balanceFromRow, formatReportBalance } from '../../utils/reportBalanceDisplay';
import { useAuth } from '../../context/AuthContext';
import { isAdminUser } from '../../utils/rolePermissions';
import {
  DRILLDOWN_SCOPE_PLATFORM,
  parseDrillDownSearchParams,
  statusForReportApi,
} from '../../utils/dashboardDrillDown';
import Card from '../common/Card';
import {
  FaCircleCheck,
  FaClock,
  FaCircleXmark,
  FaEye,
  FaX,
} from 'react-icons/fa6';
import ReportDateRange from '../common/ReportDateRange';
import BbpsTransactionReceiptView from './BbpsTransactionReceiptView';
import { mapApiPaymentToReceiptTransaction } from './bbpsReceiptFields';
import { buildBbpsReceiptPrintHtml, openBbpsReceiptPrint } from './bbpsReceiptPrint';
import { deriveCustomerId, deriveReceiptIdentity, getStatusColor } from './bbpsBillsHelpers';
import { normalizeIsoDate } from '../../utils/reportDate';
import { countActiveReportFilters, filtersEqual } from '../../utils/reportFilters';
import ReportPagination from '../common/ReportPagination';
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
  serviceId: '',
  status: 'ALL',
  dateFrom: '',
  dateTo: '',
};

function mergeDrillDownFilters(drillDown) {
  if (!drillDown?.hasDrillDown) return { ...EMPTY_FILTERS };
  let status = drillDown.filters.status;
  if (status === 'FAILURE') status = 'FAILURE';
  else if (status === 'SUCCESS' || status === 'PENDING') status = status;
  else status = 'ALL';
  return {
    ...EMPTY_FILTERS,
    status,
    dateFrom: drillDown.filters.dateFrom || '',
    dateTo: drillDown.filters.dateTo || '',
  };
}

/**
 * Shared My Bills table + receipt modal (My Bills page and Reports → BBPS).
 *
 * @param {{
 *   variant?: 'page' | 'embedded',
 *   title?: string,
 *   subtitle?: string,
 *   defaultScope?: 'self' | 'team' | 'platform',
 *   showScopeToggle?: boolean,
 *   showCsvExport?: boolean,
 *   complaintsRegisterPath?: string,
 *   payBillPath?: string,
 * }} props
 */
const BbpsBillsList = ({
  variant = 'page',
  title = 'My Bills',
  subtitle = 'View your bill payment transaction history',
  defaultScope = 'self',
  showScopeToggle = false,
  showCsvExport = false,
  complaintsRegisterPath = '/bill-payments/complaints/register',
  payBillPath = '/bill-payments/pay',
}) => {
  const { user } = useAuth();
  const location = useLocation();
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();
  const drillDown = useMemo(() => parseDrillDownSearchParams(searchParams), [searchParams]);
  const initialFilters = useMemo(() => mergeDrillDownFilters(drillDown), [drillDown]);

  const autoOpenDoneRef = useRef(false);
  const fetchIdRef = useRef(0);
  const [transactions, setTransactions] = useState([]);
  const [loading, setLoading] = useState(true);
  const [hasLoadedOnce, setHasLoadedOnce] = useState(false);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(DEFAULT_PAGE_SIZE);
  const [total, setTotal] = useState(0);
  const [exporting, setExporting] = useState(false);
  const [filters, setFilters] = useState(initialFilters);
  const [appliedFilters, setAppliedFilters] = useState(initialFilters);
  const [showFilters, setShowFilters] = useState(() => Boolean(drillDown.hasDrillDown));
  const [selectedTransaction, setSelectedTransaction] = useState(null);
  const [showDetailsModal, setShowDetailsModal] = useState(false);
  const [detailsLoading, setDetailsLoading] = useState(false);
  const [listScope, setListScope] = useState(() => {
    if (drillDown.scope === DRILLDOWN_SCOPE_PLATFORM && isAdminUser(user)) return 'platform';
    return defaultScope;
  });
  const [showDashboardBanner, setShowDashboardBanner] = useState(drillDown.fromDashboard);

  const selectedIdentity = deriveReceiptIdentity(selectedTransaction || {});
  const showAgentColumn = listScope === 'platform' || listScope === 'team';
  const isEmbedded = variant === 'embedded';

  const userId = user?.id ?? user?.user_id;
  const userRole = user?.role;

  useEffect(() => {
    const next = mergeDrillDownFilters(drillDown);
    setFilters((prev) => (filtersEqual(prev, next) ? prev : next));
    setAppliedFilters((prev) => (filtersEqual(prev, next) ? prev : next));
    if (drillDown.scope === DRILLDOWN_SCOPE_PLATFORM && isAdminUser(user)) {
      setListScope('platform');
    }
    setShowDashboardBanner(drillDown.fromDashboard);
    if (drillDown.hasDrillDown) setShowFilters(true);
  }, [drillDown, userId, userRole]);

  const buildListParams = useCallback(() => {
    const params = { page, page_size: pageSize, scope: listScope };
    if (appliedFilters.serviceId.trim()) params.search = appliedFilters.serviceId.trim();
    if (appliedFilters.status && appliedFilters.status !== 'ALL') {
      params.status = statusForReportApi(
        appliedFilters.status === 'FAILURE' ? 'FAILURE' : appliedFilters.status
      );
    }
    if (appliedFilters.dateFrom) params.date_from = appliedFilters.dateFrom;
    if (appliedFilters.dateTo) params.date_to = appliedFilters.dateTo;
    return params;
  }, [appliedFilters, listScope, page, pageSize]);

  const buildExportParams = useCallback(() => {
    const params = { page: 1, page_size: 500, scope: listScope };
    if (appliedFilters.serviceId.trim()) params.search = appliedFilters.serviceId.trim();
    if (appliedFilters.status && appliedFilters.status !== 'ALL') {
      params.status = statusForReportApi(
        appliedFilters.status === 'FAILURE' ? 'FAILURE' : appliedFilters.status
      );
    }
    if (appliedFilters.dateFrom) params.date_from = appliedFilters.dateFrom;
    if (appliedFilters.dateTo) params.date_to = appliedFilters.dateTo;
    return params;
  }, [appliedFilters, listScope]);

  const loadTransactions = useCallback(async () => {
    const runId = ++fetchIdRef.current;
    if (hasLoadedOnce) setIsRefreshing(true);
    else setLoading(true);
    try {
      const result = await bbpsAPI.getBillPayments(buildListParams());
      if (runId !== fetchIdRef.current) return;
      if (result.success) {
        const payments = result.data?.payments || result.data?.results || [];
        setTotal(Number(result.data?.total) || payments.length);
        setTransactions(
          payments.map((p) => ({
            ...mapApiPaymentToReceiptTransaction(p),
            customerId: deriveCustomerId(p) || null,
            agentUserCode: p.agent_user_code || p.user_code || '',
            agentName: p.agent_name || '',
            agentRole: p.agent_role || '',
            openingBalance: p.opening_balance,
            closingBalance: p.closing_balance,
          }))
        );
      } else {
        setTransactions([]);
        setTotal(0);
      }
    } catch (err) {
      if (runId !== fetchIdRef.current) return;
      console.error('Failed to load bill payments', err);
      setTransactions([]);
      setTotal(0);
    } finally {
      if (runId !== fetchIdRef.current) return;
      setLoading(false);
      setIsRefreshing(false);
      setHasLoadedOnce(true);
    }
  }, [buildListParams, hasLoadedOnce]);

  useEffect(() => {
    loadTransactions();
  }, [loadTransactions]);

  const exportCsv = async () => {
    setExporting(true);
    try {
      const res = await bbpsAPI.downloadBillPaymentsCsv(buildExportParams());
      if (!res.success || !res.blob) return;
      const url = window.URL.createObjectURL(res.blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = res.filename || 'bbps_bill_payments.csv';
      a.click();
      window.URL.revokeObjectURL(url);
    } finally {
      setExporting(false);
    }
  };

  const getStatusIcon = (status) => {
    switch (status) {
      case 'SUCCESS':
        return <FaCircleCheck className="text-green-600 dark:text-green-400" size={20} />;
      case 'PENDING':
        return <FaClock className="text-yellow-600 dark:text-yellow-400" size={20} />;
      case 'FAILURE':
      case 'FAILED':
        return <FaCircleXmark className="text-red-600 dark:text-red-400" size={20} />;
      default:
        return null;
    }
  };

  const handleFilterChange = (field, value) => {
    setFilters({ ...filters, [field]: value });
  };

  const applyFilters = () => {
    setPage(1);
    setAppliedFilters({
      ...filters,
      dateFrom: normalizeIsoDate(filters.dateFrom),
      dateTo: normalizeIsoDate(filters.dateTo),
    });
  };

  const clearFilters = () => {
    const cleared = { ...EMPTY_FILTERS };
    setFilters(cleared);
    setPage(1);
    setAppliedFilters(cleared);
    setSearchParams({});
    setShowDashboardBanner(false);
  };

  const handleViewDetails = async (transaction) => {
    setShowDetailsModal(true);
    setSelectedTransaction(transaction);
    setDetailsLoading(true);
    try {
      const detail = await bbpsAPI.getBillPaymentDetail(transaction.id, { scope: listScope });
      const row = detail?.data?.payment;
      if (!detail?.success || !row) return;
      const enriched = mapApiPaymentToReceiptTransaction(row);
      setSelectedTransaction({
        ...enriched,
        customerId: deriveCustomerId(row) || enriched.customerId || transaction.customerId || '',
      });
    } finally {
      setDetailsLoading(false);
    }
  };

  const closeDetailsModal = () => {
    setShowDetailsModal(false);
    setSelectedTransaction(null);
    setDetailsLoading(false);
  };

  useEffect(() => {
    if (autoOpenDoneRef.current) return;
    if (loading || !transactions.length) return;
    const ref = location.state?.openReceipt;
    if (!ref) return;

    let target = null;
    if (ref.paymentId != null) {
      target = transactions.find((t) => String(t.id) === String(ref.paymentId));
    }
    if (!target && ref.serviceId) {
      target = transactions.find((t) => String(t.serviceId || '') === String(ref.serviceId));
    }
    if (!target && ref.requestId) {
      target = transactions.find((t) => String(t.requestId || '') === String(ref.requestId));
    }
    if (!target) return;

    autoOpenDoneRef.current = true;
    handleViewDetails(target);
    if (!isEmbedded) {
      navigate('/bill-payments/my-bills', { replace: true, state: null });
    }
  }, [loading, transactions, location.state, navigate, isEmbedded]);

  const downloadReceipt = (txn, { mobile = false } = {}) => {
    if (!txn) return;
    const identity = deriveReceiptIdentity(txn);
    const html = buildBbpsReceiptPrintHtml(txn, identity, { mobile });
    openBbpsReceiptPrint(html, { mobile });
  };

  const scopeToggle = showScopeToggle && isAdminUser(user) && (
    <div className="flex flex-wrap gap-2 mb-4">
      <button
        type="button"
        onClick={() => {
          setPage(1);
          setListScope('platform');
        }}
        className={`px-4 py-2 rounded-lg text-sm font-semibold border ${
          listScope === 'platform'
            ? 'bg-blue-600 text-white border-blue-600'
            : 'bg-white dark:bg-slate-900 text-gray-700 dark:text-slate-300 border-gray-300 dark:border-slate-600'
        }`}
      >
        Platform (all users)
      </button>
      <button
        type="button"
        onClick={() => {
          setPage(1);
          setListScope('team');
        }}
        className={`px-4 py-2 rounded-lg text-sm font-semibold border ${
          listScope === 'team'
            ? 'bg-blue-600 text-white border-blue-600'
            : 'bg-white dark:bg-slate-900 text-gray-700 dark:text-slate-300 border-gray-300 dark:border-slate-600'
        }`}
      >
        Team (excl. me)
      </button>
      <button
        type="button"
        onClick={() => {
          setPage(1);
          setListScope('self');
        }}
        className={`px-4 py-2 rounded-lg text-sm font-semibold border ${
          listScope === 'self'
            ? 'bg-blue-600 text-white border-blue-600'
            : 'bg-white dark:bg-slate-900 text-gray-700 dark:text-slate-300 border-gray-300 dark:border-slate-600'
        }`}
      >
        My activity
      </button>
    </div>
  );

  const headerRow = (
    <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
      <div>
        {!isEmbedded && (
          <>
            <h1 className="text-2xl sm:text-3xl font-bold text-gray-900 dark:text-slate-100">{title}</h1>
            <p className="mt-1 sm:mt-2 text-sm sm:text-base text-gray-600 dark:text-slate-400">{subtitle}</p>
          </>
        )}
        {isEmbedded && (
          <>
            <h2 className="text-xl sm:text-2xl font-bold text-gray-900 dark:text-slate-100">{title}</h2>
            <p className="mt-1 text-sm text-gray-600 dark:text-slate-400">{subtitle}</p>
          </>
        )}
      </div>
    </div>
  );

  return (
    <div className={isEmbedded ? 'space-y-4' : 'max-w-7xl mx-auto space-y-6 px-4 sm:px-0'}>
      {showDashboardBanner && drillDown.fromDashboard && (
        <div className="flex flex-wrap items-center justify-between gap-2 rounded-lg border border-blue-200 dark:border-blue-800 bg-blue-50 dark:bg-blue-950/40 px-4 py-3 text-sm text-blue-900 dark:text-blue-300">
          <span>Filtered from dashboard portal activity.</span>
          <button
            type="button"
            onClick={clearFilters}
            className="font-semibold text-blue-700 dark:text-blue-300 hover:underline focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-500 rounded"
          >
            Clear filters
          </button>
        </div>
      )}

      {headerRow}
      {scopeToggle}

      <CollapsibleReportFilters
        open={showFilters}
        onOpenChange={setShowFilters}
        activeCount={countActiveReportFilters(appliedFilters)}
        applying={isRefreshing}
        toolbarEnd={
          showCsvExport ? (
            <button
              type="button"
              onClick={exportCsv}
              disabled={exporting || loading}
              className="inline-flex min-h-[40px] items-center gap-2 rounded-lg border border-gray-300 dark:border-slate-600 bg-white dark:bg-slate-900 px-3.5 py-2 text-sm font-semibold text-gray-800 dark:text-slate-200 shadow-sm hover:bg-gray-50 dark:hover:bg-slate-800 disabled:opacity-60"
            >
              <FiDownload className="h-4 w-4" aria-hidden />
              {exporting ? 'Exporting…' : 'Download CSV'}
            </button>
          ) : null
        }
        onApply={applyFilters}
        onClear={clearFilters}
      >
        <ReportFilterGrid>
          <ReportFilterField label="Transaction ID / Service ID" htmlFor="bbps-filter-id" span={2}>
            <input
              id="bbps-filter-id"
              type="text"
              value={filters.serviceId}
              onChange={(e) => handleFilterChange('serviceId', e.target.value)}
              placeholder="Search by ID"
              className={FILTER_INPUT_CLASS}
            />
          </ReportFilterField>
          <ReportFilterField label="Status" htmlFor="bbps-filter-status">
            <select
              id="bbps-filter-status"
              value={filters.status}
              onChange={(e) => handleFilterChange('status', e.target.value)}
              className={FILTER_SELECT_CLASS}
            >
              <option value="ALL">All status</option>
              <option value="SUCCESS">Success</option>
              <option value="PENDING">Pending</option>
              <option value="FAILURE">Failure</option>
            </select>
          </ReportFilterField>
        </ReportFilterGrid>
        <ReportFilterDateRow>
          <ReportDateRange
            idPrefix="bbps-bills"
            dateFrom={filters.dateFrom}
            dateTo={filters.dateTo}
            fromLabel="From date"
            toLabel="To date"
            compact
            onChange={({ dateFrom, dateTo }) =>
              setFilters((prev) => ({ ...prev, dateFrom, dateTo }))
            }
          />
        </ReportFilterDateRow>
      </CollapsibleReportFilters>

      <Card padding="lg">
        {loading && !hasLoadedOnce ? (
          <div className="py-12 text-center">
            <div className="mx-auto h-12 w-12 animate-spin rounded-full border-b-2 border-blue-600" />
            <p className="mt-4 text-gray-600 dark:text-slate-400">Loading transactions...</p>
          </div>
        ) : hasLoadedOnce && transactions.length === 0 && !isRefreshing ? (
          <div className="text-center py-12">
            <p className="text-gray-500 dark:text-slate-400 text-lg">No bill payment transactions found.</p>
            <p className="text-gray-400 dark:text-slate-500 text-sm mt-2">Try adjusting filters or date range.</p>
          </div>
        ) : (
          <div className={isRefreshing ? 'opacity-60 pointer-events-none' : ''}>
          <div className="overflow-x-auto -mx-4 sm:mx-0">
            <div className="inline-block min-w-full align-middle">
              <table className="min-w-full divide-y divide-gray-200 dark:divide-slate-700">
                <thead className="bg-gray-50 dark:bg-slate-800/50">
                  <tr>
                    <th className="px-3 py-3 text-left text-xs font-medium text-gray-500 dark:text-slate-400 uppercase tracking-wider">
                      S.No
                    </th>
                    <th className="px-3 py-3 text-left text-xs font-medium text-gray-500 dark:text-slate-400 uppercase tracking-wider">
                      Transaction ID
                    </th>
                    <th className="px-3 py-3 text-left text-xs font-medium text-gray-500 dark:text-slate-400 uppercase tracking-wider">
                      Request ID
                    </th>
                    {showAgentColumn && (
                      <th className="px-3 py-3 text-left text-xs font-medium text-gray-500 dark:text-slate-400 uppercase tracking-wider">
                        Agent
                      </th>
                    )}
                    <th className="px-3 py-3 text-left text-xs font-medium text-gray-500 dark:text-slate-400 uppercase tracking-wider">
                      Order Amount
                    </th>
                    <th className="px-3 py-3 text-left text-xs font-medium text-gray-500 dark:text-slate-400 uppercase tracking-wider">
                      Bill Amount
                    </th>
                    <th className="px-3 py-3 text-left text-xs font-medium text-gray-500 dark:text-slate-400 uppercase tracking-wider">
                      Category
                    </th>
                    <th className="px-3 py-3 text-left text-xs font-medium text-gray-500 dark:text-slate-400 uppercase tracking-wider">
                      Biller Details
                    </th>
                    <th className="px-3 py-3 text-left text-xs font-medium text-gray-500 dark:text-slate-400 uppercase tracking-wider">
                      Charges
                    </th>
                    <th className="px-3 py-3 text-left text-xs font-medium text-gray-500 dark:text-slate-400 uppercase tracking-wider">
                      Transaction Date
                    </th>
                    <th className="px-3 py-3 text-right text-xs font-medium text-gray-500 dark:text-slate-400 uppercase tracking-wider">
                      Opening balance
                    </th>
                    <th className="px-3 py-3 text-right text-xs font-medium text-gray-500 dark:text-slate-400 uppercase tracking-wider">
                      Closing balance
                    </th>
                    <th className="px-3 py-3 text-left text-xs font-medium text-gray-500 dark:text-slate-400 uppercase tracking-wider">
                      Status
                    </th>
                    <th className="px-3 py-3 text-center text-xs font-medium text-gray-500 dark:text-slate-400 uppercase tracking-wider">
                      Action
                    </th>
                  </tr>
                </thead>
                <tbody className="bg-white dark:bg-slate-900 divide-y divide-gray-200 dark:divide-slate-700">
                  {transactions.map((txn, index) => (
                    <tr key={txn.id} className="hover:bg-gray-50 dark:hover:bg-slate-800 transition-colors">
                      <td className="px-3 py-4 whitespace-nowrap text-sm text-gray-900 dark:text-slate-100">{(page - 1) * pageSize + index + 1}</td>
                      <td className="px-3 py-4 whitespace-nowrap">
                        <div className="text-sm font-medium text-blue-600 dark:text-blue-400">{txn.serviceId || txn.id}</div>
                      </td>
                      <td className="px-3 py-4 whitespace-nowrap">
                        <div className="text-sm text-gray-900 dark:text-slate-100 font-mono">{txn.requestId || 'N/A'}</div>
                      </td>
                      {showAgentColumn && (
                        <td className="px-3 py-4 whitespace-nowrap text-sm text-gray-900 dark:text-slate-100">
                          <div className="font-medium">{txn.agentUserCode || txn.agentName || '—'}</div>
                          {txn.agentRole && <div className="text-xs text-gray-500 dark:text-slate-400">{txn.agentRole}</div>}
                        </td>
                      )}
                      <td className="px-3 py-4 whitespace-nowrap text-sm font-bold text-gray-900 dark:text-slate-100">
                        {formatCurrency(txn.amount + (txn.charge || 0))}
                      </td>
                      <td className="px-3 py-4 whitespace-nowrap text-sm font-semibold text-gray-900 dark:text-slate-100">
                        {formatCurrency(txn.amount)}
                      </td>
                      <td className="px-3 py-4 whitespace-nowrap text-sm text-gray-900 dark:text-slate-100">
                        {txn.billType || 'N/A'}
                      </td>
                      <td className="px-3 py-4 whitespace-nowrap">
                        <div className="text-sm text-gray-900 dark:text-slate-100">
                          <div className="font-medium">{txn.biller || 'N/A'}</div>
                          {txn.billerId && <div className="text-xs text-gray-500 dark:text-slate-400">ID: {txn.billerId}</div>}
                        </div>
                      </td>
                      <td className="px-3 py-4 whitespace-nowrap text-sm text-gray-600 dark:text-slate-400">
                        {formatCurrency(txn.charge || 0)}
                      </td>
                      <td className="px-3 py-4 whitespace-nowrap text-sm text-gray-900 dark:text-slate-100">
                        {formatDateTime(txn.date)}
                      </td>
                      <td className="px-3 py-4 whitespace-nowrap text-sm text-gray-900 dark:text-slate-100 text-right">
                        {formatReportBalance(balanceFromRow(txn).opening)}
                      </td>
                      <td className="px-3 py-4 whitespace-nowrap text-sm text-gray-900 dark:text-slate-100 text-right">
                        {formatReportBalance(balanceFromRow(txn).closing)}
                      </td>
                      <td className="px-3 py-4 whitespace-nowrap">
                        <span
                          className={`inline-flex items-center space-x-1 px-2 py-1 rounded-full text-xs font-semibold border ${getStatusColor(
                            txn.status
                          )}`}
                        >
                          {getStatusIcon(txn.status)}
                          <span>{txn.status}</span>
                        </span>
                      </td>
                      <td className="px-3 py-4 whitespace-nowrap text-center">
                        <button
                          type="button"
                          onClick={() => handleViewDetails(txn)}
                          className="text-blue-600 dark:text-blue-400 hover:text-blue-800 dark:hover:text-blue-200 transition-colors p-1 rounded hover:bg-blue-50 dark:hover:bg-blue-950/60"
                          title="View Details"
                        >
                          <FaEye size={18} />
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
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

      {showDetailsModal && selectedTransaction && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black bg-opacity-50 overflow-y-auto">
          <div className="bg-white dark:bg-slate-900 rounded-xl shadow-2xl max-w-4xl w-full p-6 my-auto max-h-[95vh] overflow-y-auto">
            <div className="flex items-center justify-end mb-2">
              <button
                type="button"
                onClick={closeDetailsModal}
                className="text-gray-400 dark:text-slate-500 hover:text-gray-600 dark:hover:text-slate-400 transition-colors"
                aria-label="Close"
              >
                <FaX size={22} />
              </button>
            </div>

            <BbpsTransactionReceiptView
              transaction={selectedTransaction}
              identity={selectedIdentity}
              loading={detailsLoading}
              onPrint={() => downloadReceipt(selectedTransaction)}
              onMobilePrint={() => downloadReceipt(selectedTransaction, { mobile: true })}
              onRaiseComplaint={
                String(selectedTransaction?.status || '').toUpperCase() === 'SUCCESS'
                  ? () => {
                      const ref = String(selectedTransaction?.bConnectTxnId || '').trim();
                      closeDetailsModal();
                      navigate(complaintsRegisterPath, {
                        state: { txnRefId: ref || undefined },
                      });
                    }
                  : undefined
              }
              onAnotherTransaction={() => {
                closeDetailsModal();
                navigate(payBillPath);
              }}
            />
          </div>
        </div>
      )}
    </div>
  );
};

export default BbpsBillsList;
