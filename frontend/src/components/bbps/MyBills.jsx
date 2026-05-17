import React, { useState, useEffect, useCallback, useRef } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
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
} from 'react-icons/fa6';
import Input from '../common/Input';
import Button from '../common/Button';
import BbpsTransactionReceiptView from './BbpsTransactionReceiptView';
import { mapApiPaymentToReceiptTransaction } from './bbpsReceiptFields';
import { buildBbpsReceiptPrintHtml, openBbpsReceiptPrint } from './bbpsReceiptPrint';
import { normalizeCategorySlug } from '../../constants/bbpsCanonicalCategories';

const deriveCustomerId = (row) => {
  const r = row || {};
  const rd = r.receipt_details && typeof r.receipt_details === 'object' ? r.receipt_details : {};
  const details = r.customer_details && typeof r.customer_details === 'object' ? r.customer_details : {};
  const inputParams = Array.isArray(r.input_params) ? r.input_params : Array.isArray(r.inputParams) ? r.inputParams : [];
  const paramPatterns = /customer.?id|customer.?number|consumer.?number|subscriber|mobile|msisdn|account.?id|consumer.?id/i;
  const fromInputParam =
    inputParams.find((p) => paramPatterns.test(String(p?.paramName || p?.param_name || '')))?.paramValue ||
    inputParams.find((p) => paramPatterns.test(String(p?.param_name || '')))?.param_value ||
    '';
  const fromDetails = Object.entries(details).find(([k]) => paramPatterns.test(String(k || '')))?.[1];
  return (
    rd.bill_number ||
    r.customer_id ||
    r.customer_number ||
    details.customer_id ||
    details.customerId ||
    details['Customer ID'] ||
    details['CustomerId'] ||
    details['Customer Number'] ||
    details['Mobile Number'] ||
    details['Subscriber ID'] ||
    fromDetails ||
    fromInputParam ||
    r.mobile ||
    r.card_last4 ||
    ''
  );
};

const toInputParamRows = (row) =>
  Array.isArray(row?.inputParams)
    ? row.inputParams
    : Array.isArray(row?.input_params)
      ? row.input_params
      : [];

const toCustomerDetails = (row) => {
  const details = row?.customerDetails || row?.customer_details;
  return details && typeof details === 'object' ? details : {};
};

const pickFromInputParams = (row, patterns = []) => {
  const rows = toInputParamRows(row);
  for (const item of rows) {
    const key = String(item?.paramName || item?.param_name || '').toLowerCase();
    const value = String(item?.paramValue || item?.param_value || '').trim();
    if (!key || !value) continue;
    if (patterns.some((rx) => rx.test(key))) return value;
  }
  return '';
};

const pickFromCustomerDetails = (row, patterns = []) => {
  const details = toCustomerDetails(row);
  for (const [k, v] of Object.entries(details)) {
    const key = String(k || '').toLowerCase();
    const value = String(v || '').trim();
    if (!key || !value) continue;
    if (patterns.some((rx) => rx.test(key))) return value;
  }
  return '';
};

const deriveReceiptIdentity = (row) => {
  const rawCat = String(row?.billType || row?.bill_type || row?.category || '');
  const category = rawCat.toLowerCase();
  const byPattern = (patterns) => pickFromCustomerDetails(row, patterns) || pickFromInputParams(row, patterns);

  const catNorm = normalizeCategorySlug(rawCat);
  const isFastag = catNorm === 'fastag' || catNorm === 'fast-tag' || rawCat.toLowerCase().includes('fastag');
  if (isFastag) {
    const vehicleNumber =
      byPattern([/vehicle/, /registration/, /\breg\b/, /\bvrn\b/, /\brc\b/, /veh.*no/, /car.*no/]) ||
      String(row?.vehicle_number || row?.vehicle_no || '').trim();
    if (vehicleNumber) return { label: 'Vehicle Number', value: vehicleNumber };
  }

  if (category.includes('credit') && category.includes('card')) {
    const last4 =
      byPattern([/card.*last.?4/, /last.?4/, /card.*digit/]) ||
      String(row?.cardLast4 || row?.card_last4 || '').trim();
    if (last4) return { label: 'Card Number (Last 4)', value: last4 };
  }

  if (category.includes('mobile')) {
    const mobile = byPattern([/mobile/, /phone/]) || String(row?.mobile || '').trim();
    if (mobile) return { label: 'Mobile Number', value: mobile };
  }

  const fallback = deriveCustomerId(row);
  return { label: 'Customer ID', value: fallback || 'N/A' };
};

const MyBills = () => {
  const location = useLocation();
  const navigate = useNavigate();
  const autoOpenDoneRef = useRef(false);
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
  const selectedIdentity = deriveReceiptIdentity(selectedTransaction || {});

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
            ...mapApiPaymentToReceiptTransaction(p),
            customerId: deriveCustomerId(p) || null,
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
    navigate('/bill-payments/my-bills', { replace: true, state: null });
  }, [loading, transactions, location.state, navigate]);

  const downloadReceipt = (txn, { mobile = false } = {}) => {
    if (!txn) return;
    const identity = deriveReceiptIdentity(txn);
    const html = buildBbpsReceiptPrintHtml(txn, identity, { mobile });
    openBbpsReceiptPrint(html, { mobile });
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
          <div className="bg-white rounded-xl shadow-2xl max-w-4xl w-full p-6 my-auto max-h-[95vh] overflow-y-auto">
            <div className="flex items-center justify-end mb-2">
              <button
                type="button"
                onClick={closeDetailsModal}
                className="text-gray-400 hover:text-gray-600 transition-colors"
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
              onAnotherTransaction={() => {
                closeDetailsModal();
                navigate('/bill-payments/pay');
              }}
            />
          </div>
        </div>
      )}
    </div>
  );
};

export default MyBills;
