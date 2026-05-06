import React, { useState, useEffect, useCallback } from 'react';
import { bbpsAPI } from '../../services/api';
import { formatCurrency, formatDateTime } from '../../utils/formatters';
import Card from '../common/Card';
import {
  FaCircleCheck,
  FaClock,
  FaCircleXmark,
  FaMagnifyingGlass,
  FaFilter,
  FaEye,
  FaX,
  FaDownload,
} from 'react-icons/fa6';
import Input from '../common/Input';
import Button from '../common/Button';
import BharatConnectBranding from './BharatConnectBranding';
import bAssuredPrimary from '../../assets/bbps/b-assured-primary.svg';
import bharatConnectPrimary from '../../assets/bbps/bharat-connect-primary.svg';

const escapeHtml = (value) =>
  String(value ?? '')
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&#39;');

const MyBills = () => {
  const [transactions, setTransactions] = useState([]);
  const [loading, setLoading] = useState(true);
  const [filters, setFilters] = useState({
    serviceId: '',
    status: 'ALL',
    dateFrom: '',
    dateTo: '',
  });
  const [showFilters, setShowFilters] = useState(false);
  const [selectedTransaction, setSelectedTransaction] = useState(null);
  const [showDetailsModal, setShowDetailsModal] = useState(false);
  const [detailsLoading, setDetailsLoading] = useState(false);

  const loadTransactions = useCallback(async () => {
    setLoading(true);
    try {
      const params = {};
      if (filters.serviceId) params.search = filters.serviceId;
      if (filters.status && filters.status !== 'ALL') params.status = filters.status;
      if (filters.dateFrom) params.date_from = filters.dateFrom;
      if (filters.dateTo) params.date_to = filters.dateTo;

      const result = await bbpsAPI.getBillPayments(params);

      if (result.success) {
        const payments = result.data?.payments || result.data?.results || [];
        setTransactions(
          payments.map((p) => ({
            id: p.id,
            serviceId: p.service_id || p.id,
            requestId: p.request_id || p.external_ref || null,
            bConnectTxnId: p.bconnect_txn_id || p.request_id || p.service_id || null,
            approvalRefNumber: p.approval_ref_number || null,
            amount: parseFloat(p.amount || 0),
            charge: parseFloat(p.charge || p.service_charge || 0),
            ccfAmount: parseFloat(p.ccf_amount || p.charge || p.service_charge || 0),
            totalDeducted: parseFloat(p.total_deducted || (parseFloat(p.amount || 0) + parseFloat(p.charge || p.service_charge || 0))),
            billType: p.category || p.bill_type || 'Bill Payment',
            biller: p.biller_name || p.biller || 'N/A',
            billerId: p.biller_id || null,
            customerId: p.customer_id || p.customer_number || p.mobile || p.card_last4 || null,
            date: p.created_at || p.transaction_date,
            status: (p.status || 'PENDING').toUpperCase(),
            cardLast4: p.card_last4 || null,
            mobile: p.mobile || null,
            failureReason: p.failure_reason || '',
            statusHistory: Array.isArray(p.status_history) ? p.status_history : [],
          }))
        );
      } else {
        setTransactions([]);
      }
    } catch (err) {
      console.error('Failed to load bill payments', err);
      setTransactions([]);
    } finally {
      setLoading(false);
    }
  }, [filters]);

  useEffect(() => {
    loadTransactions();
  }, [loadTransactions]);

  const getStatusColor = (status) => {
    switch (status) {
      case 'SUCCESS':
        return 'bg-green-100 text-green-800 border-green-200';
      case 'PENDING':
        return 'bg-yellow-100 text-yellow-800 border-yellow-200';
      case 'FAILURE':
      case 'FAILED':
        return 'bg-red-100 text-red-800 border-red-200';
      default:
        return 'bg-gray-100 text-gray-800 border-gray-200';
    }
  };

  const getStatusIcon = (status) => {
    switch (status) {
      case 'SUCCESS':
        return <FaCircleCheck className="text-green-600" size={20} />;
      case 'PENDING':
        return <FaClock className="text-yellow-600" size={20} />;
      case 'FAILURE':
      case 'FAILED':
        return <FaCircleXmark className="text-red-600" size={20} />;
      default:
        return null;
    }
  };

  const handleFilterChange = (field, value) => {
    setFilters({ ...filters, [field]: value });
  };

  const clearFilters = () => {
    setFilters({
      serviceId: '',
      status: 'ALL',
      dateFrom: '',
      dateTo: '',
    });
  };

  const handleViewDetails = async (transaction) => {
    setShowDetailsModal(true);
    setSelectedTransaction(transaction);
    setDetailsLoading(true);
    try {
      const detail = await bbpsAPI.getBillPaymentDetail(transaction.id);
      const row = detail?.data?.payment;
      if (!detail?.success || !row) return;
      setSelectedTransaction((prev) => ({
        ...(prev || transaction),
        serviceId: row.service_id || prev?.serviceId || transaction.serviceId,
        requestId: row.request_id || prev?.requestId || transaction.requestId,
        bConnectTxnId: row.bconnect_txn_id || row.request_id || row.service_id || prev?.bConnectTxnId || transaction.bConnectTxnId,
        approvalRefNumber: row.approval_ref_number || prev?.approvalRefNumber || '',
        amount: parseFloat(row.amount || prev?.amount || transaction.amount || 0),
        charge: parseFloat(row.charge || prev?.charge || transaction.charge || 0),
        ccfAmount: parseFloat(row.ccf_amount || row.charge || prev?.ccfAmount || transaction.ccfAmount || 0),
        totalDeducted: parseFloat(row.total_deducted || (parseFloat(row.amount || 0) + parseFloat(row.charge || 0))),
        status: String(row.status || prev?.status || transaction.status || 'PENDING').toUpperCase(),
        failureReason: row.failure_reason || prev?.failureReason || '',
        statusHistory: Array.isArray(row.status_history) ? row.status_history : (prev?.statusHistory || []),
        customerId: row.customer_id || row.customer_number || prev?.customerId || transaction.customerId || '',
      }));
    } finally {
      setDetailsLoading(false);
    }
  };

  const closeDetailsModal = () => {
    setShowDetailsModal(false);
    setSelectedTransaction(null);
    setDetailsLoading(false);
  };

  const downloadReceipt = (txn) => {
    if (!txn) return;
    const txnDate = formatDateTime(txn.date) || 'N/A';
    const totalDeducted = Number(txn.totalDeducted || (txn.amount + (txn.charge || 0)));
    const ccf = Number(txn.ccfAmount || txn.charge || 0);
    const html = `
      <html>
        <head>
          <title>BBPS Receipt - ${escapeHtml(txn.bConnectTxnId || txn.serviceId || txn.id)}</title>
          <style>
            body { font-family: Arial, sans-serif; padding: 28px; color: #111827; }
            .header { display:flex; justify-content:space-between; align-items:center; margin-bottom:18px; }
            .title { font-size: 28px; font-weight: 700; letter-spacing: 0.02em; }
            .sub { color:#4b5563; margin-top:4px; }
            .badge { display:inline-block; padding:6px 12px; border-radius:999px; font-weight:700; font-size:12px; background:#dcfce7; color:#166534; border:1px solid #86efac; }
            table { width:100%; border-collapse: collapse; margin-top: 16px; }
            th, td { border:1px solid #d1d5db; padding:10px; text-align:left; font-size:13px; }
            th { background:#f9fafb; width:22%; color:#374151; text-transform: uppercase; font-size:11px; }
            .section-title { margin-top:20px; font-weight:700; color:#1f2937; font-size:13px; text-transform:uppercase; }
            .logo { height: 46px; width:auto; object-fit:contain; }
            .mono { font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; }
            .row { display:flex; gap:12px; justify-content:space-between; align-items:center; margin-top:8px; }
          </style>
        </head>
        <body>
          <div class="header">
            <div>
              <div class="title">BILL PAY RECEIPT</div>
              <div class="sub">Bharat Connect BBPS Payment Confirmation</div>
            </div>
            <img class="logo" src="${window.location.origin}${bAssuredPrimary}" alt="B Assured Logo" />
          </div>
          <div class="row">
            <img class="logo" style="height:38px" src="${window.location.origin}${bharatConnectPrimary}" alt="Bharat Connect Logo" />
          </div>

          <span class="badge">${escapeHtml(txn.status || 'SUCCESS')}</span>

          <div class="section-title">Transaction Identifiers</div>
          <table>
            <tr><th>B-Connect Txn ID</th><td class="mono">${escapeHtml(txn.bConnectTxnId || 'N/A')}</td><th>Request ID</th><td class="mono">${escapeHtml(txn.requestId || 'N/A')}</td></tr>
            <tr><th>Transaction Ref ID</th><td class="mono">${escapeHtml(txn.serviceId || txn.id || 'N/A')}</td><th>Approved Number</th><td class="mono">${escapeHtml(txn.approvalRefNumber || 'N/A')}</td></tr>
          </table>

          <div class="section-title">Biller Information</div>
          <table>
            <tr><th>Biller Name</th><td>${escapeHtml(txn.biller || 'N/A')}</td><th>Biller ID</th><td>${escapeHtml(txn.billerId || 'N/A')}</td></tr>
            <tr><th>Customer ID</th><td>${escapeHtml(txn.customerId || 'N/A')}</td><th>Category</th><td>${escapeHtml(txn.billType || 'N/A')}</td></tr>
            <tr><th>Transaction Date & Time</th><td>${escapeHtml(txnDate)}</td><th>Transaction Status</th><td>${escapeHtml(txn.status || 'N/A')}</td></tr>
          </table>

          <div class="section-title">Financial Breakdown</div>
          <table>
            <tr><th>Bill Amount</th><td>${formatCurrency(txn.amount || 0)}</td><th>CCF</th><td>${formatCurrency(ccf)}</td></tr>
            <tr><th>Service Charges</th><td>${formatCurrency(txn.charge || 0)}</td><th>Total Amount</th><td><strong>${formatCurrency(totalDeducted)}</strong></td></tr>
          </table>
        </body>
      </html>
    `;
    const printWindow = window.open('', '_blank', 'width=900,height=700,noopener,noreferrer');
    if (!printWindow) return;
    try {
      printWindow.opener = null;
    } catch {
      /* ignore */
    }
    printWindow.document.open();
    printWindow.document.write(html);
    printWindow.document.close();
    printWindow.focus();
    printWindow.print();
  };

  if (loading) {
    return (
      <div className="max-w-7xl mx-auto space-y-6 px-4 sm:px-0">
        <div className="text-center py-12">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto"></div>
          <p className="mt-4 text-gray-600">Loading transactions...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="max-w-7xl mx-auto space-y-6 px-4 sm:px-0">
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-2xl sm:text-3xl font-bold text-gray-900">My Bills</h1>
          <p className="mt-1 sm:mt-2 text-sm sm:text-base text-gray-600">
            View your bill payment transaction history
          </p>
        </div>
        <Button
          onClick={() => setShowFilters(!showFilters)}
          variant="outline"
          icon={FaFilter}
          iconPosition="left"
          className="mt-4 sm:mt-0"
        >
          {showFilters ? 'Hide Filters' : 'Show Filters'}
        </Button>
      </div>

      {showFilters && (
        <Card padding="lg">
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
            <Input
              label="Transaction ID / Service ID"
              value={filters.serviceId}
              onChange={(e) => handleFilterChange('serviceId', e.target.value)}
              placeholder="Search by ID"
              icon={FaMagnifyingGlass}
            />
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">Status</label>
              <select
                value={filters.status}
                onChange={(e) => handleFilterChange('status', e.target.value)}
                className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 text-gray-900 bg-white"
              >
                <option value="ALL">All Status</option>
                <option value="SUCCESS">Success</option>
                <option value="PENDING">Pending</option>
                <option value="FAILURE">Failure</option>
              </select>
            </div>
            <Input
              label="From Date"
              type="date"
              value={filters.dateFrom}
              onChange={(e) => handleFilterChange('dateFrom', e.target.value)}
            />
            <Input
              label="To Date"
              type="date"
              value={filters.dateTo}
              onChange={(e) => handleFilterChange('dateTo', e.target.value)}
            />
          </div>
          <div className="mt-4 flex justify-end">
            <Button onClick={clearFilters} variant="outline" size="sm">
              Clear Filters
            </Button>
          </div>
        </Card>
      )}

      <Card padding="lg">
        {transactions.length === 0 ? (
          <div className="text-center py-12">
            <p className="text-gray-500 text-lg">No bill payment transactions found.</p>
            <p className="text-gray-400 text-sm mt-2">Your bill payment history will appear here.</p>
          </div>
        ) : (
          <div className="overflow-x-auto -mx-4 sm:mx-0">
            <div className="inline-block min-w-full align-middle">
              <table className="min-w-full divide-y divide-gray-200">
                <thead className="bg-gray-50">
                  <tr>
                    <th className="px-3 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      S.No
                    </th>
                    <th className="px-3 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Transaction ID
                    </th>
                    <th className="px-3 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Request ID
                    </th>
                    <th className="px-3 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Order Amount
                    </th>
                    <th className="px-3 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Bill Amount
                    </th>
                    <th className="px-3 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Category
                    </th>
                    <th className="px-3 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Biller Details
                    </th>
                    <th className="px-3 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Charges
                    </th>
                    <th className="px-3 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Transaction Date
                    </th>
                    <th className="px-3 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Status
                    </th>
                    <th className="px-3 py-3 text-center text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Action
                    </th>
                  </tr>
                </thead>
                <tbody className="bg-white divide-y divide-gray-200">
                  {transactions.map((txn, index) => (
                    <tr key={txn.id} className="hover:bg-gray-50 transition-colors">
                      <td className="px-3 py-4 whitespace-nowrap text-sm text-gray-900">{index + 1}</td>
                      <td className="px-3 py-4 whitespace-nowrap">
                        <div className="text-sm font-medium text-blue-600">{txn.serviceId || txn.id}</div>
                      </td>
                      <td className="px-3 py-4 whitespace-nowrap">
                        <div className="text-sm text-gray-900 font-mono">{txn.requestId || 'N/A'}</div>
                      </td>
                      <td className="px-3 py-4 whitespace-nowrap text-sm font-bold text-gray-900">
                        {formatCurrency(txn.amount + (txn.charge || 0))}
                      </td>
                      <td className="px-3 py-4 whitespace-nowrap text-sm font-semibold text-gray-900">
                        {formatCurrency(txn.amount)}
                      </td>
                      <td className="px-3 py-4 whitespace-nowrap text-sm text-gray-900">
                        {txn.billType || 'N/A'}
                      </td>
                      <td className="px-3 py-4 whitespace-nowrap">
                        <div className="text-sm text-gray-900">
                          <div className="font-medium">{txn.biller || 'N/A'}</div>
                          {txn.billerId && <div className="text-xs text-gray-500">ID: {txn.billerId}</div>}
                        </div>
                      </td>
                      <td className="px-3 py-4 whitespace-nowrap text-sm text-gray-600">
                        {formatCurrency(txn.charge || 0)}
                      </td>
                      <td className="px-3 py-4 whitespace-nowrap text-sm text-gray-900">
                        {formatDateTime(txn.date)}
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
                          onClick={() => handleViewDetails(txn)}
                          className="text-blue-600 hover:text-blue-800 transition-colors p-1 rounded hover:bg-blue-50"
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
        )}
      </Card>

      {showDetailsModal && selectedTransaction && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black bg-opacity-50 overflow-y-auto">
          <div className="bg-white rounded-xl shadow-2xl max-w-2xl w-full p-6 my-auto max-h-[90vh] overflow-y-auto">
            <div className="flex items-center justify-between mb-6">
              <h2 className="text-2xl font-bold text-gray-900">Transaction Details</h2>
              <button
                onClick={closeDetailsModal}
                className="text-gray-400 hover:text-gray-600 transition-colors"
              >
                <FaX size={24} />
              </button>
            </div>

            <div className="space-y-6">
              <BharatConnectBranding stage="stage3" title="BBPS Receipt View" logoSize="lg" />
              <div className="flex justify-center">
                <span
                  className={`inline-flex items-center space-x-2 px-6 py-3 rounded-full text-sm font-semibold border ${getStatusColor(
                    selectedTransaction.status
                  )}`}
                >
                  {getStatusIcon(selectedTransaction.status)}
                  <span className="text-lg">{selectedTransaction.status}</span>
                </span>
              </div>

              <div className="bg-gray-50 rounded-lg p-4 border border-gray-200">
                <h3 className="text-sm font-semibold text-gray-700 mb-3 uppercase tracking-wide">
                  Transaction Identifiers
                </h3>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div>
                    <label className="text-xs text-gray-500 uppercase">B-Connect Transaction ID</label>
                    <p className="text-sm font-medium text-gray-900 mt-1">
                      {selectedTransaction.bConnectTxnId || selectedTransaction.serviceId || selectedTransaction.id}
                    </p>
                  </div>
                  <div>
                    <label className="text-xs text-gray-500 uppercase">Request ID</label>
                    <p className="text-sm font-medium text-gray-900 mt-1">
                      {selectedTransaction.requestId || 'N/A'}
                    </p>
                  </div>
                  {selectedTransaction.id && (
                    <div>
                      <label className="text-xs text-gray-500 uppercase">Transaction Ref ID</label>
                      <p className="text-sm font-medium text-gray-900 mt-1">{selectedTransaction.id}</p>
                    </div>
                  )}
                  <div>
                    <label className="text-xs text-gray-500 uppercase">Approved Number</label>
                    <p className="text-sm font-medium text-gray-900 mt-1">
                      {selectedTransaction.approvalRefNumber || 'N/A'}
                    </p>
                  </div>
                </div>
              </div>

              <div className="bg-blue-50 rounded-lg p-4 border border-blue-200">
                <h3 className="text-sm font-semibold text-gray-700 mb-3 uppercase tracking-wide">
                  Financial Breakdown
                </h3>
                <div className="space-y-3">
                  <div className="flex justify-between items-center">
                    <span className="text-sm text-gray-600">Bill Amount:</span>
                    <span className="text-lg font-semibold text-gray-900">
                      {formatCurrency(selectedTransaction.amount)}
                    </span>
                  </div>
                  <div className="flex justify-between items-center">
                    <span className="text-sm text-gray-600">CCF:</span>
                    <span className="text-lg font-semibold text-red-600">
                      {formatCurrency(selectedTransaction.ccfAmount || 0)}
                    </span>
                  </div>
                  <div className="flex justify-between items-center">
                    <span className="text-sm text-gray-600">Service Charges:</span>
                    <span className="text-lg font-semibold text-red-600">
                      {formatCurrency(selectedTransaction.charge || 0)}
                    </span>
                  </div>
                  <div className="flex justify-between items-center pt-2 border-t border-blue-200">
                    <span className="text-base font-bold text-gray-900">Order Amount (Total Deducted):</span>
                    <span className="text-xl font-bold text-blue-600">
                      {formatCurrency(selectedTransaction.totalDeducted || (selectedTransaction.amount + (selectedTransaction.charge || 0)))}
                    </span>
                  </div>
                </div>
              </div>

              <div className="bg-gray-50 rounded-lg p-4 border border-gray-200">
                <h3 className="text-sm font-semibold text-gray-700 mb-3 uppercase tracking-wide">
                  Biller Information
                </h3>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div>
                    <label className="text-xs text-gray-500 uppercase">Category</label>
                    <p className="text-sm font-medium text-gray-900 mt-1">
                      {selectedTransaction.billType || 'N/A'}
                    </p>
                  </div>
                  <div>
                    <label className="text-xs text-gray-500 uppercase">Biller Name</label>
                    <p className="text-sm font-medium text-gray-900 mt-1">
                      {selectedTransaction.biller || 'N/A'}
                    </p>
                  </div>
                  {selectedTransaction.billerId && (
                    <div>
                      <label className="text-xs text-gray-500 uppercase">Biller ID</label>
                      <p className="text-sm font-medium text-gray-900 mt-1">{selectedTransaction.billerId}</p>
                    </div>
                  )}
                  <div>
                    <label className="text-xs text-gray-500 uppercase">Customer ID</label>
                    <p className="text-sm font-medium text-gray-900 mt-1">
                      {selectedTransaction.customerId || selectedTransaction.mobile || selectedTransaction.cardLast4 || 'N/A'}
                    </p>
                  </div>
                </div>
              </div>

              {(selectedTransaction.billType === 'Credit Card' ||
                selectedTransaction.cardLast4 ||
                selectedTransaction.mobile) && (
                <div className="bg-gray-50 rounded-lg p-4 border border-gray-200">
                  <h3 className="text-sm font-semibold text-gray-700 mb-3 uppercase tracking-wide">
                    Identity Markers
                  </h3>
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    {selectedTransaction.cardLast4 && (
                      <div>
                        <label className="text-xs text-gray-500 uppercase">Last 4 Digits of Card</label>
                        <p className="text-sm font-medium text-gray-900 mt-1">
                          **** {selectedTransaction.cardLast4}
                        </p>
                      </div>
                    )}
                    {selectedTransaction.mobile && (
                      <div>
                        <label className="text-xs text-gray-500 uppercase">Registered Mobile Number</label>
                        <p className="text-sm font-medium text-gray-900 mt-1">{selectedTransaction.mobile}</p>
                      </div>
                    )}
                  </div>
                </div>
              )}

              <div className="bg-gray-50 rounded-lg p-4 border border-gray-200">
                <h3 className="text-sm font-semibold text-gray-700 mb-3 uppercase tracking-wide">
                  Transaction Information
                </h3>
                <div>
                  <label className="text-xs text-gray-500 uppercase">Transaction Date & Time</label>
                  <p className="text-sm font-medium text-gray-900 mt-1">
                    {formatDateTime(selectedTransaction.date)}
                  </p>
                </div>
              </div>
            </div>

            {detailsLoading ? (
              <p className="text-sm text-gray-500">Refreshing receipt details...</p>
            ) : null}

            <div className="mt-6 flex justify-end gap-2">
              <Button
                onClick={() => downloadReceipt(selectedTransaction)}
                variant="outline"
                icon={FaDownload}
                iconPosition="left"
              >
                Download Receipt
              </Button>
              <Button onClick={closeDetailsModal} variant="primary">
                Close
              </Button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default MyBills;
