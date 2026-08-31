import React, { useState, useEffect, useCallback, useMemo, useRef } from 'react';
import { FiDownload, FiEye, FiFilter, FiHelpCircle, FiX } from 'react-icons/fi';
import { MdReceiptLong } from 'react-icons/md';
import { useSearchParams } from 'react-router-dom';
import { useAuth } from '../../context/AuthContext';
import { reportsAPI } from '../../services/api';
import { DRILLDOWN_SCOPE_PLATFORM, parseDrillDownSearchParams } from '../../utils/dashboardDrillDown';
import { canUseTeamReportScope, isAdminUser } from '../../utils/rolePermissions';
import FeedbackModal from '../common/FeedbackModal';
import ReportTransactionDetailModal from './ReportTransactionDetailModal';
import PayinTransactionReceiptView from './PayinTransactionReceiptView';
import { mapPayinRowToReceiptTransaction } from './payinReceiptFields';
import { buildPayinReceiptPrintHtml, openPayinReceiptPrint } from './payinReceiptPrint';
import {
  formatCurrency,
  formatDateTime,
  formatReportDateTime,
  formatAccountNumber,
} from '../../utils/formatters';
import { balanceFromRow, formatReportBalance } from '../../utils/reportBalanceDisplay';
import ReportDateRange from '../common/ReportDateRange';
import ReportPagination from '../common/ReportPagination';
import {
  CollapsibleReportFilters,
  FILTER_INPUT_CLASS,
  FILTER_SELECT_CLASS,
  ReportFilterDateRow,
  ReportFilterField,
  ReportFilterGrid,
} from '../common/ReportFilterPanel';
import { countActiveReportFilters, filtersEqual } from '../../utils/reportFilters';

const DEFAULT_PAGE_SIZE = 25;

const ledgerStyleTypes = ['payin', 'payout'];

const EMPTY_FILTERS = {
  serviceId: '',
  status: 'ALL',
  dateFrom: '',
  dateTo: '',
  mobile: '',
  amountMin: '',
  amountMax: '',
  serviceType: 'all',
  agentRole: '',
  collectionRail: 'all',
  utr: '',
};

function mergeDrillDownFilters(drillDown) {
  if (!drillDown?.hasDrillDown) return { ...EMPTY_FILTERS };
  return {
    ...EMPTY_FILTERS,
    status: drillDown.filters.status,
    dateFrom: drillDown.filters.dateFrom,
    dateTo: drillDown.filters.dateTo,
  };
}

const TransactionReport = ({ type = 'all' }) => {
  const { user } = useAuth();
  const [searchParams, setSearchParams] = useSearchParams();
  const drillDown = useMemo(() => parseDrillDownSearchParams(searchParams), [searchParams]);
  const initialFilters = useMemo(() => mergeDrillDownFilters(drillDown), [drillDown]);

  const [transactions, setTransactions] = useState([]);
  const [filters, setFilters] = useState(initialFilters);
  /** API query; updated only when the user clicks Apply. */
  const [appliedFilters, setAppliedFilters] = useState(initialFilters);
  const fetchIdRef = useRef(0);
  const [loading, setLoading] = useState(true);
  const [hasLoadedOnce, setHasLoadedOnce] = useState(false);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(DEFAULT_PAGE_SIZE);
  const [total, setTotal] = useState(0);
  const [summary, setSummary] = useState({
    success: 0,
    pending: 0,
    failure: 0,
  });
  const [detailRecord, setDetailRecord] = useState(null);
  const [receiptTxn, setReceiptTxn] = useState(null);
  const [helpTxnId, setHelpTxnId] = useState(null);
  const [reportScope, setReportScope] = useState(() =>
    drillDown.scope === DRILLDOWN_SCOPE_PLATFORM && isAdminUser(user) ? 'platform' : 'self'
  );
  const [showDashboardBanner, setShowDashboardBanner] = useState(drillDown.fromDashboard);
  const [showFilters, setShowFilters] = useState(() => Boolean(drillDown.hasDrillDown));

  const userId = user?.id ?? user?.user_id;
  const userRole = user?.role;

  useEffect(() => {
    const next = mergeDrillDownFilters(drillDown);
    setFilters((prev) => (filtersEqual(prev, next) ? prev : next));
    setAppliedFilters((prev) => (filtersEqual(prev, next) ? prev : next));
    if (drillDown.scope === DRILLDOWN_SCOPE_PLATFORM && isAdminUser(user)) {
      setReportScope('platform');
    }
    setShowDashboardBanner(drillDown.fromDashboard);
    if (drillDown.hasDrillDown) setShowFilters(true);
  }, [drillDown, userId, userRole]);

  const buildReportParams = useCallback((forExport = false) => {
    let scope = 'self';
    if (reportScope === 'platform' && isAdminUser(user)) {
      scope = 'platform';
    } else if (reportScope === 'team' && canUseTeamReportScope(user?.role)) {
      scope = 'team';
    }
    const q = appliedFilters;
    const params = forExport
      ? { scope, page: 1, page_size: 500 }
      : { scope, page, page_size: pageSize };
    if (q.dateFrom) params.date_from = q.dateFrom;
    if (q.dateTo) params.date_to = q.dateTo;
    if (q.status && q.status !== 'ALL') params.status = q.status === 'FAILURE' ? 'FAILED' : q.status;
    const sid = q.serviceId.trim();
    if (sid) params.service_id = sid;
    if (q.mobile.trim()) params.mobile = q.mobile.trim();
    if (q.amountMin) params.amount_min = q.amountMin;
    if (q.amountMax) params.amount_max = q.amountMax;
    if (q.serviceType && q.serviceType !== 'all') params.service_type = q.serviceType;
    if (q.agentRole.trim()) params.agent_role = q.agentRole.trim();
    if (type === 'payin' && q.collectionRail && q.collectionRail !== 'all') {
      params.collection_rail = q.collectionRail;
    }
    if (type === 'payin' && q.utr.trim()) params.utr = q.utr.trim();
    return params;
  }, [reportScope, userRole, type, appliedFilters, page, pageSize]);

  const loadTransactions = useCallback(async () => {
    if (!userId) return;
    if (!['payin', 'payout', 'bbps'].includes(type)) return;

    const runId = ++fetchIdRef.current;
    if (hasLoadedOnce) setIsRefreshing(true);
    else setLoading(true);
    try {
      const params = buildReportParams();
      let result;
      if (type === 'payin') result = await reportsAPI.getPayInReport(params);
      else if (type === 'payout') result = await reportsAPI.getPayOutReport(params);
      else result = await reportsAPI.getBBPSReport(params);

      if (runId !== fetchIdRef.current) return;

      if (!result.success) {
        setTransactions([]);
        setTotal(0);
        setSummary({ success: 0, pending: 0, failure: 0 });
        return;
      }

      setTotal(Number(result.data?.total) || 0);

      const by = result.data?.summary?.by_status || {};
      const parseAmt = (x) => parseFloat(x || '0') || 0;
      setSummary({
        success: parseAmt(by.SUCCESS?.amount),
        pending: parseAmt(by.PENDING?.amount) + parseAmt(by.PENDING_REVIEW?.amount),
        failure: parseAmt(by.FAILED?.amount),
      });

      const rows = result.data?.rows || [];
      if (type === 'payin') {
        setTransactions(
          rows.map((r) => ({
            id: r.id,
            transactionId: r.service_id,
            requestId: r.reference || r.provider_order_id || '—',
            orderAmount: parseFloat(r.principal) || 0,
            billAmount: parseFloat(r.net_credit) || 0,
            modeOfPayment: r.mode || '—',
            paymentGatewayName: r.payment_gateway_name || '—',
            railTypeLabel: r.rail_type_label || '',
            collectionRail: r.collection_rail || 'gateway',
            utr: r.utr || '',
            qrAccountName: r.qr_account_name || '',
            proofReceiptUrl: r.proof_receipt_url || '',
            receiptDetails: r.receipt_details || null,
            submittedAmount: r.submitted_amount || '',
            rejectReason: r.reject_reason || '',
            charges: parseFloat(r.service_charge) || 0,
            date: r.created_at,
            status: r.status,
            failureReason: '',
            openingBalance: r.opening_balance,
            closingBalance: r.closing_balance,
            detailLine1: `${r.agent_details?.user_code || ''} · ${r.agent_details?.name || ''}`,
            detailLine2: `Customer: ${r.customer_phone || r.customer_id || '—'}`,
            accountMasked: '',
            category: '',
            detail: {
              cardLast4: r.card_last4,
              bankTxnId: r.bank_txn_id,
              gatewayPaymentMeta: r.gateway_payment_meta,
              customerId: r.customer_user_code || r.customer_id,
              customerPhone: r.customer_phone || r.customer_id,
              customerName: r.customer_name,
              customerEmail: r.customer_email,
              agentDetails: r.agent_details,
              packageId: r.package_id,
              packageCode: r.package_code,
              packageDisplayName: r.package_display_name,
              paymentGatewayName: r.payment_gateway_name,
              railTypeLabel: r.rail_type_label,
              proofReceiptUrl: r.proof_receipt_url,
              receiptDetails: r.receipt_details,
              openingBalance: r.opening_balance,
              closingBalance: r.closing_balance,
              paymentModeDisplay: r.mode,
              providerOrderId: r.provider_order_id,
              providerPaymentId: r.provider_payment_id,
              gatewayTransactionId: r.gateway_transaction_id,
              gatewayUtr: r.gateway_utr,
              collectionRail: r.collection_rail,
              utr: r.utr,
              qrAccountName: r.qr_account_name,
              proofReceiptUrl: r.proof_receipt_url,
              receiptDetails: r.receipt_details,
              submittedAmount: r.submitted_amount,
              rejectReason: r.reject_reason,
              feeSnapshot: r.fee_breakdown_snapshot,
            },
            rawRow: r,
          }))
        );
      } else if (type === 'payout') {
        setTransactions(
          rows.map((r) => ({
            id: r.id,
            transactionId: r.transaction_id,
            requestId: r.reference || '—',
            orderAmount: parseFloat(r.net_debit) || 0,
            billAmount: parseFloat(r.transfer_amount) || 0,
            category: 'Payout',
            charges: (parseFloat(r.payout_charge) || 0) + (parseFloat(r.platform_fee) || 0),
            date: r.created_at,
            status: r.status,
            failureReason: '',
            detailLine1: `${r.agent_details?.user_code || ''} · ${r.agent_details?.name || ''}`,
            detailLine2: r.bank_name || '—',
            accountMasked: r.account_number_masked || '—',
            openingBalance: r.opening_balance,
            closingBalance: r.closing_balance,
            detail: {
              bankName: r.bank_name,
              accountMasked: r.account_number_masked,
              accountDisplay: r.account_number_masked,
              commissionBreakdown: r.commission_breakdown,
              agentDetails: r.agent_details,
              platformFee: parseFloat(r.platform_fee || '0'),
              netDebit: parseFloat(r.net_debit || '0'),
              totalDeducted: parseFloat(r.net_debit || '0'),
              gatewayTransactionId: r.reference,
              openingBalance: r.opening_balance,
              closingBalance: r.closing_balance,
            },
          }))
        );
      } else {
        setTransactions(
          rows.map((r) => ({
            id: r.id,
            date: r.created_at,
            serviceId: r.transaction_id,
            biller: r.biller || r.category || '—',
            amount: parseFloat(r.bill_amount) || 0,
            status: r.status,
            statusToken: r.status_token,
            detail: { agentDetails: r.agent_details, requestId: r.request_id },
          }))
        );
      }
    } catch (error) {
      if (runId !== fetchIdRef.current) return;
      console.error('Error loading transactions:', error);
      setTransactions([]);
      setTotal(0);
      setSummary({ success: 0, pending: 0, failure: 0 });
    } finally {
      if (runId !== fetchIdRef.current) return;
      setLoading(false);
      setIsRefreshing(false);
      setHasLoadedOnce(true);
    }
  }, [userId, type, buildReportParams, hasLoadedOnce]);

  const exportCsv = useCallback(async () => {
    if (!['payin', 'payout', 'bbps'].includes(type)) return;
    const params = buildReportParams(true);
    const path =
      type === 'payin' ? '/reports/payin/export.csv' : type === 'payout' ? '/reports/payout/export.csv' : '/reports/bbps/export.csv';
    const res = await reportsAPI.downloadReportCsv(path, params);
    if (!res.success || !res.blob) return;
    const url = window.URL.createObjectURL(res.blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `${type}_report.csv`;
    a.click();
    window.URL.revokeObjectURL(url);
  }, [buildReportParams, type]);

  useEffect(() => {
    loadTransactions();
  }, [loadTransactions]);

  const getStatusBadge = (status) => {
    const statusUpper = status?.toUpperCase() || 'PENDING';
    const colors = {
      SUCCESS: 'bg-emerald-600 text-white border-emerald-700',
      PENDING: 'bg-yellow-100 dark:bg-yellow-900/40 text-yellow-800 dark:text-yellow-300 border-yellow-200 dark:border-yellow-800',
      FAILURE: 'bg-red-100 dark:bg-red-900/40 text-red-800 dark:text-red-300 border-red-200 dark:border-red-800',
      FAILED: 'bg-red-100 dark:bg-red-900/40 text-red-800 dark:text-red-300 border-red-200 dark:border-red-800',
    };

    const colorClass = colors[statusUpper] || colors.PENDING;

    return (
      <span className={`inline-flex rounded-full border px-3 py-1 text-xs font-bold ${colorClass}`}>
        {statusUpper}
      </span>
    );
  };

  const reportTitle = {
    all: 'All Transactions',
    payin: 'Pay In Report',
    payout: 'Pay Out Report',
    bbps: 'BBPS Report',
  };

  const isLedgerStyle = ledgerStyleTypes.includes(type);

  const clearDashboardDrillDown = () => {
    setSearchParams({});
    setShowDashboardBanner(false);
    const cleared = { ...EMPTY_FILTERS };
    setFilters(cleared);
    setPage(1);
    setAppliedFilters(cleared);
    if (isAdminUser(user)) setReportScope('self');
  };

  const openPayinReceipt = (txn) => {
    const receiptTransaction = mapPayinRowToReceiptTransaction({
      id: txn.id,
      service_id: txn.transactionId,
      status: txn.status,
      collection_rail: txn.collectionRail,
      rail_type_label: txn.railTypeLabel,
      payment_gateway_name: txn.paymentGatewayName,
      mode: txn.modeOfPayment,
      utr: txn.utr,
      qr_account_name: txn.qrAccountName,
      principal: txn.orderAmount,
      service_charge: txn.charges,
      net_credit: txn.billAmount,
      submitted_amount: txn.submittedAmount,
      created_at: txn.date,
      customer_name: txn.detail?.customerName,
      customer_phone: txn.detail?.customerPhone,
      customer_email: txn.detail?.customerEmail,
      agent_details: txn.detail?.agentDetails,
      package_display_name: txn.detail?.packageDisplayName,
      proof_receipt_url: txn.proofReceiptUrl,
      reject_reason: txn.rejectReason,
      opening_balance: txn.openingBalance,
      closing_balance: txn.closingBalance,
      receipt_details: txn.receiptDetails,
      reference: txn.requestId,
    });
    setReceiptTxn(receiptTransaction);
  };

  const printPayinReceipt = (txn, { mobile = false } = {}) => {
    const html = buildPayinReceiptPrintHtml(txn, { mobile });
    openPayinReceiptPrint(html, { mobile });
  };

  return (
    <div className="space-y-4 sm:space-y-6 px-4 sm:px-0">
      {showDashboardBanner && drillDown.fromDashboard && (
        <div className="flex flex-wrap items-center justify-between gap-2 rounded-lg border border-blue-200 dark:border-blue-800 bg-blue-50 dark:bg-blue-950/40 px-4 py-3 text-sm text-blue-900 dark:text-blue-300">
          <span>Filtered from dashboard portal activity (platform-wide).</span>
          <button
            type="button"
            onClick={clearDashboardDrillDown}
            className="font-semibold text-blue-700 dark:text-blue-300 hover:underline focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-500 rounded"
          >
            Clear filters
          </button>
        </div>
      )}
      <ReportTransactionDetailModal
        open={Boolean(detailRecord)}
        onClose={() => setDetailRecord(null)}
        variant={detailRecord?.variant}
        record={detailRecord?.record}
      />

      {type === 'payin' && receiptTxn ? (
        <div
          className="fixed inset-0 z-[80] flex items-center justify-center bg-black/50 p-4"
          role="presentation"
          onClick={() => setReceiptTxn(null)}
        >
          <div
            className="relative max-h-[92vh] w-full max-w-3xl overflow-y-auto rounded-2xl bg-white dark:bg-slate-900 p-6 shadow-2xl"
            role="dialog"
            aria-modal="true"
            onClick={(e) => e.stopPropagation()}
          >
            <button
              type="button"
              onClick={() => setReceiptTxn(null)}
              className="absolute right-4 top-4 flex h-9 w-9 items-center justify-center rounded-full bg-red-500 text-white shadow-sm hover:bg-red-600"
              aria-label="Close receipt"
            >
              <FiX className="h-5 w-5" />
            </button>
            <PayinTransactionReceiptView
              transaction={receiptTxn}
              onPrint={() => printPayinReceipt(receiptTxn)}
              onMobilePrint={() => printPayinReceipt(receiptTxn, { mobile: true })}
            />
          </div>
        </div>
      ) : null}

      <FeedbackModal
        open={Boolean(helpTxnId)}
        onClose={() => setHelpTxnId(null)}
        title="Need help?"
        description={`Share this transaction ID with support:\n\n${helpTxnId}\n\nYou can also attach a screenshot of this screen for faster resolution.`}
      />

      <div className="bg-white dark:bg-slate-900 rounded-xl shadow-sm p-4 sm:p-6 border border-gray-200 dark:border-slate-700">
        <h2 className="text-xl sm:text-2xl font-bold text-gray-900 dark:text-slate-100 mb-2">
          {reportTitle[type] || 'Transaction Report'}
        </h2>
        {(canUseTeamReportScope(user?.role) || isAdminUser(user)) && (
          <div className="flex flex-wrap gap-2 mb-4">
            {!isAdminUser(user) ? (
              <>
                <button
                  type="button"
                  onClick={() => setReportScope('self')}
                  className={`px-4 py-2 rounded-lg text-sm font-semibold border ${
                    reportScope === 'self'
                      ? 'bg-blue-600 text-white border-blue-600'
                      : 'bg-white dark:bg-slate-900 text-gray-700 dark:text-slate-300 border-gray-300 dark:border-slate-600'
                  }`}
                >
                  My activity
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
                  Team activity
                </button>
              </>
            ) : (
              <>
                <button
                  type="button"
                  onClick={() => setReportScope('platform')}
                  className={`px-4 py-2 rounded-lg text-sm font-semibold border ${
                    reportScope === 'platform'
                      ? 'bg-blue-600 text-white border-blue-600'
                      : 'bg-white dark:bg-slate-900 text-gray-700 dark:text-slate-300 border-gray-300 dark:border-slate-600'
                  }`}
                >
                  Platform (all users)
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
                  Team (excl. me)
                </button>
                <button
                  type="button"
                  onClick={() => setReportScope('self')}
                  className={`px-4 py-2 rounded-lg text-sm font-semibold border ${
                    reportScope === 'self'
                      ? 'bg-blue-600 text-white border-blue-600'
                      : 'bg-white dark:bg-slate-900 text-gray-700 dark:text-slate-300 border-gray-300 dark:border-slate-600'
                  }`}
                >
                  My activity
                </button>
              </>
            )}
          </div>
        )}
        {type === 'payin' && (
          <p className="text-sm text-gray-600 dark:text-slate-400 mb-4 sm:mb-6">
            Pay-in ledger view (principal, charges, net credit). Team scope follows your role visibility
            rules.
          </p>
        )}
        {type === 'payout' && (
          <p className="text-sm text-gray-600 dark:text-slate-400 mb-4 sm:mb-6">
            Payout ledger: transfer amount, charges, and net debit. Use filters and CSV export for
            reconciliation.
          </p>
        )}


        {/* Summary Cards */}
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 mb-4">
          <div className="bg-green-50 dark:bg-green-950/40 border-2 border-green-200 dark:border-green-800 rounded-lg p-4">
            <p className="text-sm text-gray-600 dark:text-slate-400 mb-1">SUCCESS</p>
            <p className="text-2xl font-bold text-green-600 dark:text-green-400">{formatCurrency(summary.success)}</p>
          </div>
          <div className="bg-yellow-50 dark:bg-yellow-950/40 border-2 border-yellow-200 dark:border-yellow-800 rounded-lg p-4">
            <p className="text-sm text-gray-600 dark:text-slate-400 mb-1">PENDING</p>
            <p className="text-2xl font-bold text-yellow-600 dark:text-yellow-400">{formatCurrency(summary.pending)}</p>
          </div>
          <div className="bg-red-50 dark:bg-red-950/40 border-2 border-red-200 dark:border-red-800 rounded-lg p-4">
            <p className="text-sm text-gray-600 dark:text-slate-400 mb-1">FAILURE</p>
            <p className="text-2xl font-bold text-red-600 dark:text-red-400">{formatCurrency(summary.failure)}</p>
          </div>
        </div>

        <CollapsibleReportFilters
          open={showFilters}
          onOpenChange={setShowFilters}
          activeCount={countActiveReportFilters(appliedFilters)}
          applying={isRefreshing}
          toolbarEnd={
            ['payin', 'payout', 'bbps'].includes(type) ? (
              <button
                type="button"
                onClick={() => exportCsv()}
                className="inline-flex min-h-[40px] items-center gap-2 rounded-lg border border-gray-300 dark:border-slate-600 bg-white dark:bg-slate-900 px-3.5 py-2 text-sm font-semibold text-gray-800 dark:text-slate-200 shadow-sm hover:bg-gray-50 dark:hover:bg-slate-800"
              >
                <FiDownload className="h-4 w-4" aria-hidden />
                Download CSV
              </button>
            ) : null
          }
          onApply={() => {
            setPage(1);
            setAppliedFilters({ ...filters });
          }}
          onClear={clearDashboardDrillDown}
        >
          <ReportFilterGrid>
            <ReportFilterField
              label={isLedgerStyle ? 'Transaction ID' : type === 'bbps' ? 'Service ID' : 'Search'}
              htmlFor="txn-filter-id"
              span={2}
            >
              <input
                id="txn-filter-id"
                type="text"
                value={filters.serviceId}
                onChange={(e) => setFilters({ ...filters, serviceId: e.target.value })}
                placeholder={isLedgerStyle ? 'Search transaction id…' : type === 'bbps' ? 'BBPS service id…' : 'Filter…'}
                className={FILTER_INPUT_CLASS}
              />
            </ReportFilterField>
            <ReportFilterField label="Status" htmlFor="txn-filter-status">
              <select
                id="txn-filter-status"
                value={filters.status}
                onChange={(e) => setFilters({ ...filters, status: e.target.value })}
                className={FILTER_SELECT_CLASS}
              >
                <option value="ALL">All statuses</option>
                <option value="SUCCESS">Success</option>
                <option value="PENDING">Pending</option>
                <option value="PENDING_REVIEW">Pending review</option>
                <option value="FAILURE">Failed</option>
              </select>
            </ReportFilterField>
            {isLedgerStyle ? (
              <>
                <ReportFilterField label="Mobile" htmlFor="txn-filter-mobile">
                  <input
                    id="txn-filter-mobile"
                    type="text"
                    inputMode="tel"
                    value={filters.mobile}
                    onChange={(e) => setFilters({ ...filters, mobile: e.target.value })}
                    placeholder="User / customer mobile"
                    className={FILTER_INPUT_CLASS}
                  />
                </ReportFilterField>
                <ReportFilterField label="Amount min" htmlFor="txn-filter-min">
                  <input
                    id="txn-filter-min"
                    type="text"
                    inputMode="decimal"
                    value={filters.amountMin}
                    onChange={(e) => setFilters({ ...filters, amountMin: e.target.value })}
                    placeholder="Min"
                    className={FILTER_INPUT_CLASS}
                  />
                </ReportFilterField>
                <ReportFilterField label="Amount max" htmlFor="txn-filter-max">
                  <input
                    id="txn-filter-max"
                    type="text"
                    inputMode="decimal"
                    value={filters.amountMax}
                    onChange={(e) => setFilters({ ...filters, amountMax: e.target.value })}
                    placeholder="Max"
                    className={FILTER_INPUT_CLASS}
                  />
                </ReportFilterField>
                {type === 'payin' ? (
                  <>
                    <ReportFilterField label="Payment rail" htmlFor="txn-filter-rail">
                      <select
                        id="txn-filter-rail"
                        value={filters.collectionRail}
                        onChange={(e) => setFilters({ ...filters, collectionRail: e.target.value })}
                        className={FILTER_SELECT_CLASS}
                      >
                        <option value="all">All rails</option>
                        <option value="gateway">Gateway</option>
                        <option value="qr">QR</option>
                      </select>
                    </ReportFilterField>
                    <ReportFilterField label="UTR" htmlFor="txn-filter-utr">
                      <input
                        id="txn-filter-utr"
                        type="text"
                        value={filters.utr}
                        onChange={(e) => setFilters({ ...filters, utr: e.target.value })}
                        placeholder="UTR / reference"
                        className={FILTER_INPUT_CLASS}
                      />
                    </ReportFilterField>
                  </>
                ) : null}
                {canUseTeamReportScope(user?.role) ? (
                  <ReportFilterField label="Agent role" htmlFor="txn-filter-role">
                    <input
                      id="txn-filter-role"
                      type="text"
                      value={filters.agentRole}
                      onChange={(e) => setFilters({ ...filters, agentRole: e.target.value })}
                      placeholder="e.g. Retailer"
                      className={FILTER_INPUT_CLASS}
                    />
                  </ReportFilterField>
                ) : null}
              </>
            ) : null}
          </ReportFilterGrid>
          <ReportFilterDateRow>
            <ReportDateRange
              idPrefix={`txn-${type}`}
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

        {/* Transactions Table */}
        {loading && !hasLoadedOnce ? (
          <div className="text-center py-12">
            <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto"></div>
            <p className="mt-4 text-gray-600 dark:text-slate-400">Loading transactions...</p>
          </div>
        ) : hasLoadedOnce && transactions.length === 0 && !isRefreshing ? (
          <div className="text-center py-12 text-gray-500 dark:text-slate-400">No transactions found</div>
        ) : (
          <div className={isRefreshing ? 'opacity-60 pointer-events-none' : ''}>
        {isLedgerStyle ? (
          <div className="overflow-x-auto rounded-lg border border-gray-200 dark:border-slate-700">
            <table className="w-full min-w-[1080px] border-collapse text-left">
              <thead>
                <tr className="border-b border-gray-200 dark:border-slate-700 bg-gray-50 dark:bg-slate-800/50">
                  <th className="px-3 py-3 text-xs font-semibold uppercase tracking-wide text-gray-600 dark:text-slate-400 sm:px-4">
                    S.No
                  </th>
                  <th className="px-3 py-3 text-xs font-semibold uppercase tracking-wide text-gray-600 dark:text-slate-400 sm:px-4">
                    Transaction ID
                  </th>
                  <th className="px-3 py-3 text-xs font-semibold uppercase tracking-wide text-gray-600 dark:text-slate-400 sm:px-4">
                    Request ID
                  </th>
                  <th className="px-3 py-3 text-xs font-semibold uppercase tracking-wide text-gray-600 dark:text-slate-400 sm:px-4">
                    Order amount
                  </th>
                  <th className="px-3 py-3 text-xs font-semibold uppercase tracking-wide text-gray-600 dark:text-slate-400 sm:px-4">
                    Bill amount
                  </th>
                  {type === 'payin' ? (
                    <>
                      <th className="px-3 py-3 text-xs font-semibold uppercase tracking-wide text-gray-600 dark:text-slate-400 sm:px-4">
                        Mode of payment
                      </th>
                      <th className="px-3 py-3 text-xs font-semibold uppercase tracking-wide text-gray-600 dark:text-slate-400 sm:px-4">
                        Collection method
                      </th>
                      <th className="px-3 py-3 text-xs font-semibold uppercase tracking-wide text-gray-600 dark:text-slate-400 sm:px-4">
                        Rail / reference
                      </th>
                    </>
                  ) : (
                    <th className="px-3 py-3 text-xs font-semibold uppercase tracking-wide text-gray-600 dark:text-slate-400 sm:px-4">
                      Transfer mode
                    </th>
                  )}
                  <th className="px-3 py-3 text-xs font-semibold uppercase tracking-wide text-gray-600 dark:text-slate-400 sm:px-4">
                    {type === 'payin' ? 'Payer details' : 'Beneficiary details'}
                  </th>
                  <th className="px-3 py-3 text-xs font-semibold uppercase tracking-wide text-gray-600 dark:text-slate-400 sm:px-4">
                    Charges
                  </th>
                  <th className="px-3 py-3 text-xs font-semibold uppercase tracking-wide text-gray-600 dark:text-slate-400 sm:px-4">
                    Agent
                  </th>
                  <th className="px-3 py-3 text-right text-xs font-semibold uppercase tracking-wide text-gray-600 dark:text-slate-400 sm:px-4">
                    Opening balance
                  </th>
                  <th className="px-3 py-3 text-right text-xs font-semibold uppercase tracking-wide text-gray-600 dark:text-slate-400 sm:px-4">
                    Closing balance
                  </th>
                  <th className="px-3 py-3 text-xs font-semibold uppercase tracking-wide text-gray-600 dark:text-slate-400 sm:px-4">
                    Transaction date
                  </th>
                  <th className="px-3 py-3 text-xs font-semibold uppercase tracking-wide text-gray-600 dark:text-slate-400 sm:px-4">
                    Status
                  </th>
                  <th className="px-3 py-3 text-center text-xs font-semibold uppercase tracking-wide text-gray-600 dark:text-slate-400 sm:px-4">
                    Action
                  </th>
                </tr>
              </thead>
              <tbody>
                {transactions.map((txn, index) => (
                  <tr key={txn.id} className="border-b border-gray-100 dark:border-slate-800 hover:bg-gray-50/80 dark:hover:bg-slate-800/80">
                    <td className="px-3 py-3 text-sm text-gray-600 dark:text-slate-400 sm:px-4">{(page - 1) * pageSize + index + 1}</td>
                    <td className="px-3 py-3 text-sm font-medium text-gray-900 dark:text-slate-100 sm:px-4">
                      <span className="break-all">{txn.transactionId}</span>
                    </td>
                    <td className="px-3 py-3 text-sm text-gray-700 dark:text-slate-300 sm:px-4">
                      <span className="break-all">{txn.requestId}</span>
                    </td>
                    <td className="px-3 py-3 text-sm text-gray-900 dark:text-slate-100 sm:px-4">
                      {formatCurrency(txn.orderAmount)}
                    </td>
                    <td className="px-3 py-3 text-sm text-gray-900 dark:text-slate-100 sm:px-4">
                      {formatCurrency(txn.billAmount)}
                    </td>
                    {type === 'payin' ? (
                      <>
                        <td className="px-3 py-3 text-sm text-gray-800 dark:text-slate-200 sm:px-4">{txn.modeOfPayment}</td>
                        <td className="px-3 py-3 text-sm text-gray-800 dark:text-slate-200 sm:px-4">
                          <div className="font-medium">{txn.paymentGatewayName}</div>
                          {txn.railTypeLabel ? (
                            <div className="text-xs text-gray-500 dark:text-slate-400">{txn.railTypeLabel}</div>
                          ) : null}
                        </td>
                        <td className="px-3 py-3 text-sm text-gray-800 dark:text-slate-200 sm:px-4">
                          <div className="text-xs font-semibold uppercase text-gray-500 dark:text-slate-400">
                            {txn.collectionRail === 'qr' ? 'Manual QR' : 'Gateway'}
                          </div>
                          {txn.utr ? <div className="font-mono text-xs break-all">{txn.utr}</div> : '—'}
                          {txn.qrAccountName ? (
                            <div className="text-xs text-gray-600 dark:text-slate-400">{txn.qrAccountName}</div>
                          ) : null}
                        </td>
                      </>
                    ) : (
                      <td className="px-3 py-3 text-sm text-gray-700 dark:text-slate-300 sm:px-4">{txn.category}</td>
                    )}
                    <td className="px-3 py-3 text-sm text-gray-700 dark:text-slate-300 sm:px-4">
                      <div className="max-w-[200px] space-y-0.5">
                        <p className="break-words text-xs leading-snug text-gray-600 dark:text-slate-400">{txn.detailLine1}</p>
                        <p className="break-words font-medium leading-snug text-gray-900 dark:text-slate-100">
                          {type === 'payout' ? txn.accountMasked : txn.detailLine2}
                        </p>
                        {type === 'payout' ? (
                          <p className="break-words text-xs text-gray-500 dark:text-slate-400">{txn.detailLine2}</p>
                        ) : null}
                      </div>
                    </td>
                    <td className="px-3 py-3 text-sm text-gray-900 dark:text-slate-100 sm:px-4">
                      {formatCurrency(txn.charges)}
                    </td>
                    <td className="px-3 py-3 text-xs text-gray-700 dark:text-slate-300 sm:px-4 max-w-[200px] break-words">
                      {txn.detail?.agentDetails
                        ? `${txn.detail.agentDetails.user_code || ''} · ${txn.detail.agentDetails.name || ''} · ${txn.detail.agentDetails.mobile || ''}`
                        : txn.detailLine1}
                    </td>
                    <td className="px-3 py-3 text-right text-sm text-gray-900 dark:text-slate-100 sm:px-4">
                      {formatReportBalance(balanceFromRow(txn).opening)}
                    </td>
                    <td className="px-3 py-3 text-right text-sm text-gray-900 dark:text-slate-100 sm:px-4">
                      {formatReportBalance(balanceFromRow(txn).closing)}
                    </td>
                    <td className="px-3 py-3 text-sm whitespace-nowrap text-gray-700 dark:text-slate-300 sm:px-4">
                      {formatReportDateTime(txn.date)}
                    </td>
                    <td className="px-3 py-3 sm:px-4">
                      <div className="space-y-1">
                        {getStatusBadge(txn.status)}
                        {type === 'payin' &&
                        (txn.status || '').toUpperCase() === 'FAILED' &&
                        txn.collectionRail === 'qr' &&
                        txn.rejectReason ? (
                          <span
                            className="inline-block max-w-[180px] truncate rounded-md border border-red-200 dark:border-red-800 bg-red-50 dark:bg-red-950/40 px-2 py-0.5 text-xs font-medium text-red-800 dark:text-red-300"
                            title={txn.rejectReason}
                          >
                            {txn.rejectReason}
                          </span>
                        ) : null}
                      </div>
                    </td>
                    <td className="px-3 py-3 sm:px-4">
                      <div className="flex items-center justify-center gap-1">
                        <button
                          type="button"
                          onClick={() => setHelpTxnId(txn.transactionId)}
                          className="rounded-full p-2 text-gray-500 dark:text-slate-400 transition hover:bg-gray-100 dark:hover:bg-slate-700 hover:text-blue-600"
                          title="Help / support"
                          aria-label="Help for this transaction"
                        >
                          <FiHelpCircle className="h-5 w-5" />
                        </button>
                        {type === 'payin' ? (
                          <button
                            type="button"
                            onClick={() => openPayinReceipt(txn)}
                            className="rounded-full p-2 text-gray-500 dark:text-slate-400 transition hover:bg-gray-100 dark:hover:bg-slate-700 hover:text-blue-600"
                            title="View / print receipt"
                            aria-label="View pay-in receipt"
                          >
                            <MdReceiptLong className="h-5 w-5" />
                          </button>
                        ) : null}
                        <button
                          type="button"
                          onClick={() =>
                            setDetailRecord({
                              variant: type,
                              record: {
                                transactionId: txn.transactionId,
                                requestId: txn.requestId,
                                orderAmount: txn.orderAmount,
                                billAmount: txn.billAmount,
                                charges: txn.charges,
                                date: txn.date,
                                status: txn.status,
                                failureReason: txn.failureReason,
                                detail: txn.detail,
                              },
                            })
                          }
                          className="rounded-full p-2 text-gray-500 dark:text-slate-400 transition hover:bg-gray-100 dark:hover:bg-slate-700 hover:text-blue-600"
                          title="View details"
                          aria-label="View transaction details"
                        >
                          <FiEye className="h-5 w-5" />
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full border-collapse">
              <thead>
                <tr className="bg-gray-50 dark:bg-slate-800/50 border-b border-gray-200 dark:border-slate-700">
                  <th className="px-4 py-3 text-left text-sm font-semibold text-gray-700 dark:text-slate-300">DATE & TIME</th>
                  <th className="px-4 py-3 text-left text-sm font-semibold text-gray-700 dark:text-slate-300">SERVICE ID</th>
                  <th className="px-4 py-3 text-left text-sm font-semibold text-gray-700 dark:text-slate-300">BILLER</th>
                  <th className="px-4 py-3 text-left text-sm font-semibold text-gray-700 dark:text-slate-300">AMOUNT</th>
                  <th className="px-4 py-3 text-left text-sm font-semibold text-gray-700 dark:text-slate-300">STATUS</th>
                </tr>
              </thead>
              <tbody>
                {transactions.map((txn) => (
                  <tr key={txn.id} className="border-b border-gray-200 dark:border-slate-700 hover:bg-gray-50 dark:hover:bg-slate-800">
                    <td className="px-4 py-3 text-sm text-gray-700 dark:text-slate-300">{formatDateTime(txn.date)}</td>
                    <td className="px-4 py-3 text-sm text-gray-900 dark:text-slate-100 font-medium">{txn.serviceId}</td>
                    <td className="px-4 py-3 text-sm text-gray-700 dark:text-slate-300">{txn.biller || '-'}</td>
                    <td className="px-4 py-3 text-sm text-gray-900 dark:text-slate-100">{formatCurrency(txn.amount)}</td>
                    <td className="px-4 py-3">{getStatusBadge(txn.status)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
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

export default TransactionReport;
