import React, { useState, useEffect, useCallback } from 'react';
import { FiEye, FiFilter, FiHelpCircle } from 'react-icons/fi';
import { useAuth } from '../../context/AuthContext';
import { fundManagementAPI, transactionsAPI } from '../../services/api';
import FeedbackModal from '../common/FeedbackModal';
import ReportTransactionDetailModal from './ReportTransactionDetailModal';
import {
  formatCurrency,
  formatDateTime,
  formatReportDateTime,
  formatAccountNumber,
} from '../../utils/formatters';

const ledgerStyleTypes = ['payin', 'payout'];

const TransactionReport = ({ type = 'all' }) => {
  const { user } = useAuth();
  const [transactions, setTransactions] = useState([]);
  const [filters, setFilters] = useState({
    serviceId: '',
    status: 'ALL',
    dateFrom: '',
    dateTo: '',
  });
  /** Pay In / Pay Out: API query; updated on Apply (not on every keystroke). */
  const [appliedLedgerFilters, setAppliedLedgerFilters] = useState({
    serviceId: '',
    status: 'ALL',
    dateFrom: '',
    dateTo: '',
  });
  const [loading, setLoading] = useState(false);
  const [summary, setSummary] = useState({
    success: 0,
    pending: 0,
    failure: 0,
  });
  const [detailRecord, setDetailRecord] = useState(null);
  const [helpTxnId, setHelpTxnId] = useState(null);

  const loadTransactions = useCallback(async () => {
    if (!user) return;

    setLoading(true);
    try {
      if (type === 'payin') {
        const q = appliedLedgerFilters;
        const params = { page: 1, page_size: 500 };
        const sid = q.serviceId.trim();
        if (sid) params.search = sid;
        if (q.status && q.status !== 'ALL') {
          params.status = q.status === 'FAILURE' ? 'FAILED' : q.status;
        }
        if (q.dateFrom) params.date_from = q.dateFrom;
        if (q.dateTo) params.date_to = q.dateTo;

        const result = await fundManagementAPI.getLoadMoneyList(params);
        if (!result.success) {
          setTransactions([]);
          setSummary({ success: 0, pending: 0, failure: 0 });
          return;
        }

        const raw = result.data?.transactions || [];
        const mapped = raw.map((row) => {
          const orderAmount = parseFloat(row.amount) || 0;
          const billAmount = parseFloat(row.net_credit) || 0;
          const charges = parseFloat(row.charge) || 0;
          const requestId = row.provider_order_id?.trim() ? row.provider_order_id : '—';
          const st = (row.status || '').toUpperCase();
          const modeOfPayment =
            row.payment_mode_display ||
            (row.payment_method
              ? String(row.payment_method).replace(/_/g, ' ')
              : st === 'PENDING'
                ? 'Pending'
                : '—');
          const paymentGatewayName = row.payment_gateway_name || '—';
          return {
            id: row.id,
            transactionId: row.transaction_id,
            requestId,
            orderAmount,
            billAmount,
            modeOfPayment,
            paymentGatewayName,
            charges,
            date: row.created_at,
            status: row.status,
            failureReason: row.failure_reason || '',
            detailLine1: row.package != null ? `Package ID: ${row.package}` : 'Package: —',
            detailLine2:
              [row.customer_name, row.customer_phone].filter(Boolean).join(' · ') || 'Customer: —',
            detail: {
              packageId: row.package ?? '—',
              packageCode: row.gateway || '',
              paymentModeDisplay: modeOfPayment,
              paymentGatewayName,
              customerName: row.customer_name || '',
              customerEmail: row.customer_email || '',
              customerPhone: row.customer_phone || '',
              gatewayTransactionId: row.gateway_transaction_id || '',
              providerOrderId: row.provider_order_id || '',
              feeSnapshot: row.fee_breakdown_snapshot,
            },
          };
        });

        setTransactions(mapped);

        const summaryData = { success: 0, pending: 0, failure: 0 };
        mapped.forEach((txn) => {
          const status = (txn.status || 'PENDING').toUpperCase();
          const amt = txn.orderAmount || 0;
          if (status === 'SUCCESS') summaryData.success += amt;
          else if (status === 'PENDING') summaryData.pending += amt;
          else summaryData.failure += amt;
        });
        setSummary(summaryData);
        return;
      }

      if (type === 'payout') {
        const q = appliedLedgerFilters;
        const params = { page: 1, page_size: 500 };
        const sid = q.serviceId.trim();
        if (sid) params.search = sid;
        if (q.status && q.status !== 'ALL') {
          params.status = q.status === 'FAILURE' ? 'FAILED' : q.status;
        }
        if (q.dateFrom) params.date_from = q.dateFrom;
        if (q.dateTo) params.date_to = q.dateTo;

        const result = await fundManagementAPI.getPayoutList(params);
        if (!result.success) {
          setTransactions([]);
          setSummary({ success: 0, pending: 0, failure: 0 });
          return;
        }

        const raw = result.data?.transactions || [];
        const mapped = raw.map((row) => {
          const acct = row.bank_account || {};
          const orderAmount = parseFloat(row.total_deducted) || 0;
          const billAmount = parseFloat(row.amount) || 0;
          const charge = parseFloat(row.charge) || 0;
          const platformFee = parseFloat(row.platform_fee) || 0;
          const charges = charge + platformFee;
          const acctNum = acct.account_number || '';
          const requestId = row.gateway_transaction_id?.trim() ? row.gateway_transaction_id : '—';
          const beneficiary =
            acct.beneficiary_name || acct.account_holder_name || acct.bank_name || '—';
          return {
            id: row.id,
            transactionId: row.transaction_id,
            requestId,
            orderAmount,
            billAmount,
            category: row.transfer_mode || 'Payout',
            charges,
            date: row.created_at,
            status: row.status,
            failureReason: row.failure_reason || '',
            detailLine1: acct.ifsc ? `IFSC: ${acct.ifsc}` : 'IFSC: —',
            detailLine2: acct.bank_name || '—',
            accountMasked: acctNum ? formatAccountNumber(acctNum) : '—',
            detail: {
              bankName: acct.bank_name || '',
              accountDisplay: acctNum || '—',
              ifsc: acct.ifsc || '',
              beneficiaryName: beneficiary,
              transferMode: row.transfer_mode || '',
              gatewayTransactionId: row.gateway_transaction_id || '',
              platformFee,
              totalDeducted: orderAmount,
            },
          };
        });

        setTransactions(mapped);

        const summaryData = { success: 0, pending: 0, failure: 0 };
        mapped.forEach((txn) => {
          const st = (txn.status || 'PENDING').toUpperCase();
          const amt = txn.orderAmount || 0;
          if (st === 'SUCCESS') summaryData.success += amt;
          else if (st === 'PENDING') summaryData.pending += amt;
          else summaryData.failure += amt;
        });
        setSummary(summaryData);
        return;
      }

      if (type === 'bbps') {
        const params = { page: 1, page_size: 500, type: 'bbps' };
        const sid = filters.serviceId.trim();
        if (sid) params.service_id = sid;
        if (filters.status && filters.status !== 'ALL') {
          params.status = filters.status === 'FAILURE' ? 'FAILED' : filters.status;
        }
        if (filters.dateFrom) params.date_from = filters.dateFrom;
        if (filters.dateTo) params.date_to = filters.dateTo;

        const result = await transactionsAPI.listTransactions(params);
        if (!result.success) {
          setTransactions([]);
          setSummary({ success: 0, pending: 0, failure: 0 });
          return;
        }

        const raw = result.data?.transactions || [];
        const mapped = raw.map((row) => ({
          id: row.id,
          date: row.created_at,
          serviceId: row.service_id,
          biller: row.biller || row.bill_type || row.reference || '—',
          amount: parseFloat(row.amount) || 0,
          status: row.status,
        }));

        setTransactions(mapped);

        const summaryData = { success: 0, pending: 0, failure: 0 };
        mapped.forEach((txn) => {
          const st = (txn.status || 'PENDING').toUpperCase();
          const amt = txn.amount || 0;
          if (st === 'SUCCESS') summaryData.success += amt;
          else if (st === 'PENDING') summaryData.pending += amt;
          else summaryData.failure += amt;
        });
        setSummary(summaryData);
        return;
      }

      setTransactions([]);
      setSummary({ success: 0, pending: 0, failure: 0 });
    } catch (error) {
      console.error('Error loading transactions:', error);
      setTransactions([]);
      setSummary({ success: 0, pending: 0, failure: 0 });
    } finally {
      setLoading(false);
    }
  }, [user, type, filters, appliedLedgerFilters]);

  useEffect(() => {
    if (!user || type === 'bbps' || !ledgerStyleTypes.includes(type)) return;
    loadTransactions();
  }, [user, type, appliedLedgerFilters, loadTransactions]);

  useEffect(() => {
    if (!user || type !== 'bbps') return;
    loadTransactions();
  }, [user, type, filters, loadTransactions]);

  const getStatusBadge = (status) => {
    const statusUpper = status?.toUpperCase() || 'PENDING';
    const colors = {
      SUCCESS: 'bg-emerald-600 text-white border-emerald-700',
      PENDING: 'bg-yellow-100 text-yellow-800 border-yellow-200',
      FAILURE: 'bg-red-100 text-red-800 border-red-200',
      FAILED: 'bg-red-100 text-red-800 border-red-200',
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

  return (
    <div className="space-y-4 sm:space-y-6 px-4 sm:px-0">
      <ReportTransactionDetailModal
        open={Boolean(detailRecord)}
        onClose={() => setDetailRecord(null)}
        variant={detailRecord?.variant}
        record={detailRecord?.record}
      />

      <FeedbackModal
        open={Boolean(helpTxnId)}
        onClose={() => setHelpTxnId(null)}
        title="Need help?"
        description={`Share this transaction ID with support:\n\n${helpTxnId}\n\nYou can also attach a screenshot of this screen for faster resolution.`}
      />

      <div className="bg-white rounded-xl shadow-sm p-4 sm:p-6 border border-gray-200">
        <h2 className="text-xl sm:text-2xl font-bold text-gray-900 mb-2">
          {reportTitle[type] || 'Transaction Report'}
        </h2>
        {type === 'payin' && (
          <p className="text-sm text-gray-600 mb-4 sm:mb-6">
            Load-money records for your account. Order amount is gross pay-in; bill amount is net
            credit to wallet after charges.
          </p>
        )}
        {type === 'payout' && (
          <p className="text-sm text-gray-600 mb-4 sm:mb-6">
            Transfer records for your account. Order amount is total debited from your wallet;
            bill amount is the amount sent to the beneficiary.
          </p>
        )}

        {/* Summary Cards */}
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 sm:gap-4 mb-4 sm:mb-6">
          <div className="bg-green-50 border-2 border-green-200 rounded-lg p-4">
            <p className="text-sm text-gray-600 mb-1">SUCCESS</p>
            <p className="text-2xl font-bold text-green-600">{formatCurrency(summary.success)}</p>
          </div>
          <div className="bg-yellow-50 border-2 border-yellow-200 rounded-lg p-4">
            <p className="text-sm text-gray-600 mb-1">PENDING</p>
            <p className="text-2xl font-bold text-yellow-600">{formatCurrency(summary.pending)}</p>
          </div>
          <div className="bg-red-50 border-2 border-red-200 rounded-lg p-4">
            <p className="text-sm text-gray-600 mb-1">FAILURE</p>
            <p className="text-2xl font-bold text-red-600">{formatCurrency(summary.failure)}</p>
          </div>
        </div>

        {/* Filters */}
        <div className="mb-4 sm:mb-6 p-3 sm:p-4 bg-gray-50 rounded-lg border border-gray-200">
          {isLedgerStyle ? (
            <>
              <h3 className="text-base sm:text-lg font-semibold text-gray-900 mb-3 sm:mb-4">
                Search & filters
              </h3>
              <div className="flex flex-col gap-3 lg:flex-row lg:flex-wrap lg:items-end">
                <div className="min-w-0 flex-1 lg:min-w-[220px]">
                  <label className="block text-sm font-medium text-gray-700 mb-1.5">
                    Search transaction id
                  </label>
                  <input
                    type="text"
                    value={filters.serviceId}
                    onChange={(e) => setFilters({ ...filters, serviceId: e.target.value })}
                    placeholder="Search transaction id…"
                    className="w-full px-4 py-2.5 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                  />
                </div>
                <div className="w-full sm:w-auto sm:min-w-[160px]">
                  <label className="block text-sm font-medium text-gray-700 mb-1.5">From date</label>
                  <input
                    type="date"
                    value={filters.dateFrom}
                    onChange={(e) => setFilters({ ...filters, dateFrom: e.target.value })}
                    className="w-full px-4 py-2.5 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
                  />
                </div>
                <div className="w-full sm:w-auto sm:min-w-[160px]">
                  <label className="block text-sm font-medium text-gray-700 mb-1.5">To date</label>
                  <input
                    type="date"
                    value={filters.dateTo}
                    onChange={(e) => setFilters({ ...filters, dateTo: e.target.value })}
                    className="w-full px-4 py-2.5 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
                  />
                </div>
                <div className="w-full sm:w-auto sm:min-w-[180px]">
                  <label className="block text-sm font-medium text-gray-700 mb-1.5">Status</label>
                  <select
                    value={filters.status}
                    onChange={(e) => setFilters({ ...filters, status: e.target.value })}
                    className="w-full px-4 py-2.5 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
                  >
                    <option value="ALL">All statuses</option>
                    <option value="SUCCESS">SUCCESS</option>
                    <option value="PENDING">PENDING</option>
                    <option value="FAILURE">FAILED</option>
                  </select>
                </div>
                <button
                  type="button"
                  onClick={() => {
                    setAppliedLedgerFilters({ ...filters });
                  }}
                  disabled={loading}
                  className="inline-flex items-center justify-center gap-2 rounded-lg bg-blue-600 px-5 py-2.5 text-sm font-semibold text-white shadow-sm transition hover:bg-blue-700 disabled:opacity-60"
                >
                  <FiFilter className="h-4 w-4" aria-hidden />
                  Apply filters
                </button>
              </div>
            </>
          ) : (
            <>
              <h3 className="text-base sm:text-lg font-semibold text-gray-900 mb-3 sm:mb-4">FILTERS</h3>
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3 sm:gap-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    {type === 'bbps' && 'Search service ID'}
                    {type !== 'bbps' && 'Search'}
                  </label>
                  <input
                    type="text"
                    value={filters.serviceId}
                    onChange={(e) => setFilters({ ...filters, serviceId: e.target.value })}
                    placeholder={type === 'bbps' ? 'BBPS service id…' : 'Filter…'}
                    className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
                  />
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">Status</label>
                  <select
                    value={filters.status}
                    onChange={(e) => setFilters({ ...filters, status: e.target.value })}
                    className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
                  >
                    <option value="ALL">SELECT STATUS</option>
                    <option value="SUCCESS">SUCCESS</option>
                    <option value="PENDING">PENDING</option>
                    <option value="FAILURE">FAILED</option>
                  </select>
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">Date From</label>
                  <input
                    type="date"
                    value={filters.dateFrom}
                    onChange={(e) => setFilters({ ...filters, dateFrom: e.target.value })}
                    className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
                  />
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">Date To</label>
                  <input
                    type="date"
                    value={filters.dateTo}
                    onChange={(e) => setFilters({ ...filters, dateTo: e.target.value })}
                    className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
                  />
                </div>
              </div>
            </>
          )}
        </div>

        {/* Transactions Table */}
        {loading ? (
          <div className="text-center py-12">
            <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto"></div>
            <p className="mt-4 text-gray-600">Loading transactions...</p>
          </div>
        ) : transactions.length === 0 ? (
          <div className="text-center py-12 text-gray-500">No transactions found</div>
        ) : isLedgerStyle ? (
          <div className="overflow-x-auto rounded-lg border border-gray-200">
            <table className="w-full min-w-[1080px] border-collapse text-left">
              <thead>
                <tr className="border-b border-gray-200 bg-gray-50">
                  <th className="px-3 py-3 text-xs font-semibold uppercase tracking-wide text-gray-600 sm:px-4">
                    S.No
                  </th>
                  <th className="px-3 py-3 text-xs font-semibold uppercase tracking-wide text-gray-600 sm:px-4">
                    Transaction ID
                  </th>
                  <th className="px-3 py-3 text-xs font-semibold uppercase tracking-wide text-gray-600 sm:px-4">
                    Request ID
                  </th>
                  <th className="px-3 py-3 text-xs font-semibold uppercase tracking-wide text-gray-600 sm:px-4">
                    Order amount
                  </th>
                  <th className="px-3 py-3 text-xs font-semibold uppercase tracking-wide text-gray-600 sm:px-4">
                    Bill amount
                  </th>
                  {type === 'payin' ? (
                    <>
                      <th className="px-3 py-3 text-xs font-semibold uppercase tracking-wide text-gray-600 sm:px-4">
                        Mode of payment
                      </th>
                      <th className="px-3 py-3 text-xs font-semibold uppercase tracking-wide text-gray-600 sm:px-4">
                        Payment gateway
                      </th>
                    </>
                  ) : (
                    <th className="px-3 py-3 text-xs font-semibold uppercase tracking-wide text-gray-600 sm:px-4">
                      Transfer mode
                    </th>
                  )}
                  <th className="px-3 py-3 text-xs font-semibold uppercase tracking-wide text-gray-600 sm:px-4">
                    {type === 'payin' ? 'Payer details' : 'Beneficiary details'}
                  </th>
                  <th className="px-3 py-3 text-xs font-semibold uppercase tracking-wide text-gray-600 sm:px-4">
                    Charges
                  </th>
                  <th className="px-3 py-3 text-xs font-semibold uppercase tracking-wide text-gray-600 sm:px-4">
                    Transaction date
                  </th>
                  <th className="px-3 py-3 text-xs font-semibold uppercase tracking-wide text-gray-600 sm:px-4">
                    Status
                  </th>
                  <th className="px-3 py-3 text-center text-xs font-semibold uppercase tracking-wide text-gray-600 sm:px-4">
                    Action
                  </th>
                </tr>
              </thead>
              <tbody>
                {transactions.map((txn, index) => (
                  <tr key={txn.id} className="border-b border-gray-100 hover:bg-gray-50/80">
                    <td className="px-3 py-3 text-sm text-gray-600 sm:px-4">{index + 1}</td>
                    <td className="px-3 py-3 text-sm font-medium text-gray-900 sm:px-4">
                      <span className="break-all">{txn.transactionId}</span>
                    </td>
                    <td className="px-3 py-3 text-sm text-gray-700 sm:px-4">
                      <span className="break-all">{txn.requestId}</span>
                    </td>
                    <td className="px-3 py-3 text-sm text-gray-900 sm:px-4">
                      {formatCurrency(txn.orderAmount)}
                    </td>
                    <td className="px-3 py-3 text-sm text-gray-900 sm:px-4">
                      {formatCurrency(txn.billAmount)}
                    </td>
                    {type === 'payin' ? (
                      <>
                        <td className="px-3 py-3 text-sm text-gray-800 sm:px-4">{txn.modeOfPayment}</td>
                        <td className="px-3 py-3 text-sm text-gray-800 sm:px-4">
                          {txn.paymentGatewayName}
                        </td>
                      </>
                    ) : (
                      <td className="px-3 py-3 text-sm text-gray-700 sm:px-4">{txn.category}</td>
                    )}
                    <td className="px-3 py-3 text-sm text-gray-700 sm:px-4">
                      <div className="max-w-[200px] space-y-0.5">
                        <p className="break-words text-xs leading-snug text-gray-600">{txn.detailLine1}</p>
                        <p className="break-words font-medium leading-snug text-gray-900">
                          {type === 'payout' ? txn.accountMasked : txn.detailLine2}
                        </p>
                        {type === 'payout' ? (
                          <p className="break-words text-xs text-gray-500">{txn.detailLine2}</p>
                        ) : null}
                      </div>
                    </td>
                    <td className="px-3 py-3 text-sm text-gray-900 sm:px-4">
                      {formatCurrency(txn.charges)}
                    </td>
                    <td className="px-3 py-3 text-sm whitespace-nowrap text-gray-700 sm:px-4">
                      {formatReportDateTime(txn.date)}
                    </td>
                    <td className="px-3 py-3 sm:px-4">{getStatusBadge(txn.status)}</td>
                    <td className="px-3 py-3 sm:px-4">
                      <div className="flex items-center justify-center gap-1">
                        <button
                          type="button"
                          onClick={() => setHelpTxnId(txn.transactionId)}
                          className="rounded-full p-2 text-gray-500 transition hover:bg-gray-100 hover:text-blue-600"
                          title="Help / support"
                          aria-label="Help for this transaction"
                        >
                          <FiHelpCircle className="h-5 w-5" />
                        </button>
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
                          className="rounded-full p-2 text-gray-500 transition hover:bg-gray-100 hover:text-blue-600"
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
                <tr className="bg-gray-50 border-b border-gray-200">
                  <th className="px-4 py-3 text-left text-sm font-semibold text-gray-700">DATE & TIME</th>
                  <th className="px-4 py-3 text-left text-sm font-semibold text-gray-700">SERVICE ID</th>
                  <th className="px-4 py-3 text-left text-sm font-semibold text-gray-700">BILLER</th>
                  <th className="px-4 py-3 text-left text-sm font-semibold text-gray-700">AMOUNT</th>
                  <th className="px-4 py-3 text-left text-sm font-semibold text-gray-700">STATUS</th>
                </tr>
              </thead>
              <tbody>
                {transactions.map((txn) => (
                  <tr key={txn.id} className="border-b border-gray-200 hover:bg-gray-50">
                    <td className="px-4 py-3 text-sm text-gray-700">{formatDateTime(txn.date)}</td>
                    <td className="px-4 py-3 text-sm text-gray-900 font-medium">{txn.serviceId}</td>
                    <td className="px-4 py-3 text-sm text-gray-700">{txn.biller || '-'}</td>
                    <td className="px-4 py-3 text-sm text-gray-900">{formatCurrency(txn.amount)}</td>
                    <td className="px-4 py-3">{getStatusBadge(txn.status)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
};

export default TransactionReport;
