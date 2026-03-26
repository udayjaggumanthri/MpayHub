import React, { useState, useEffect, useCallback } from 'react';
import { useAuth } from '../../context/AuthContext';
import { getTransactions } from '../../services/mockData';
import { formatCurrency, formatDateTime } from '../../utils/formatters';

const TransactionReport = ({ type = 'all' }) => {
  const { user } = useAuth();
  const [transactions, setTransactions] = useState([]);
  const [filters, setFilters] = useState({
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

  const loadTransactions = useCallback(async () => {
    if (!user) return;

    setLoading(true);
    try {
      const filterParams = {
        ...filters,
        dateFrom: filters.dateFrom ? new Date(filters.dateFrom) : null,
        dateTo: filters.dateTo ? new Date(filters.dateTo) : null,
        status: filters.status === 'ALL' ? null : filters.status,
      };

      const result = getTransactions(user.id, type, filterParams);
      if (result.success) {
        setTransactions(result.transactions || []);

        // Calculate summary
        const summaryData = {
          success: 0,
          pending: 0,
          failure: 0,
        };

        result.transactions.forEach((txn) => {
          const status = txn.status?.toUpperCase() || 'PENDING';
          if (status === 'SUCCESS') {
            summaryData.success += txn.amount || 0;
          } else if (status === 'PENDING') {
            summaryData.pending += txn.amount || 0;
          } else {
            summaryData.failure += txn.amount || 0;
          }
        });

        setSummary(summaryData);
      }
    } catch (error) {
      console.error('Error loading transactions:', error);
    } finally {
      setLoading(false);
    }
  }, [user, type, filters]);

  useEffect(() => {
    loadTransactions();
  }, [loadTransactions]);

  const getStatusBadge = (status) => {
    const statusUpper = status?.toUpperCase() || 'PENDING';
    const colors = {
      SUCCESS: 'bg-green-100 text-green-800 border-green-200',
      PENDING: 'bg-yellow-100 text-yellow-800 border-yellow-200',
      FAILURE: 'bg-red-100 text-red-800 border-red-200',
      FAILED: 'bg-red-100 text-red-800 border-red-200',
    };

    const colorClass = colors[statusUpper] || colors.PENDING;

    return (
      <span className={`px-3 py-1 rounded-full text-xs font-semibold border ${colorClass}`}>
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

  return (
    <div className="space-y-4 sm:space-y-6 px-4 sm:px-0">
      <div className="bg-white rounded-xl shadow-sm p-4 sm:p-6 border border-gray-200">
        <h2 className="text-xl sm:text-2xl font-bold text-gray-900 mb-4 sm:mb-6">{reportTitle[type] || 'Transaction Report'}</h2>

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
          <h3 className="text-base sm:text-lg font-semibold text-gray-900 mb-3 sm:mb-4">FILTERS</h3>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3 sm:gap-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">Search Service ID</label>
              <input
                type="text"
                value={filters.serviceId}
                onChange={(e) => setFilters({ ...filters, serviceId: e.target.value })}
                placeholder="Enter Service ID"
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
                <option value="FAILURE">FAILURE</option>
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
        </div>

        {/* Transactions Table */}
        {loading ? (
          <div className="text-center py-12">
            <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto"></div>
            <p className="mt-4 text-gray-600">Loading transactions...</p>
          </div>
        ) : transactions.length === 0 ? (
          <div className="text-center py-12 text-gray-500">No transactions found</div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full border-collapse">
              <thead>
                <tr className="bg-gray-50 border-b border-gray-200">
                  <th className="px-4 py-3 text-left text-sm font-semibold text-gray-700">DATE & TIME</th>
                  <th className="px-4 py-3 text-left text-sm font-semibold text-gray-700">SERVICE ID</th>
                  {type === 'payin' && (
                      <>
                        <th className="px-4 py-3 text-left text-sm font-semibold text-gray-700">CUSTOMER ID</th>
                        <th className="px-4 py-3 text-left text-sm font-semibold text-gray-700">MODE</th>
                        <th className="px-4 py-3 text-left text-sm font-semibold text-gray-700">AMOUNT</th>
                        <th className="px-4 py-3 text-left text-sm font-semibold text-gray-700">CHARGE</th>
                        <th className="px-4 py-3 text-left text-sm font-semibold text-gray-700">NET CREDIT</th>
                        <th className="px-4 py-3 text-left text-sm font-semibold text-gray-700">CARD NUMBER</th>
                        <th className="px-4 py-3 text-left text-sm font-semibold text-gray-700">CARD NETWORK</th>
                        <th className="px-4 py-3 text-left text-sm font-semibold text-gray-700">BANK TRANSACTION ID</th>
                        <th className="px-4 py-3 text-left text-sm font-semibold text-gray-700">GATEWAY NAME</th>
                        <th className="px-4 py-3 text-left text-sm font-semibold text-gray-700">STATUS</th>
                        <th className="px-4 py-3 text-left text-sm font-semibold text-gray-700">ACTION</th>
                      </>
                    )}
                  {type === 'payout' && (
                    <>
                      <th className="px-4 py-3 text-left text-sm font-semibold text-gray-700">RETAILER ID</th>
                      <th className="px-4 py-3 text-left text-sm font-semibold text-gray-700">OPERATOR ID</th>
                      <th className="px-4 py-3 text-left text-sm font-semibold text-gray-700">ACCOUNT NUMBER</th>
                      <th className="px-4 py-3 text-left text-sm font-semibold text-gray-700">BANK NAME</th>
                      <th className="px-4 py-3 text-left text-sm font-semibold text-gray-700">AMOUNT</th>
                      <th className="px-4 py-3 text-left text-sm font-semibold text-gray-700">STATUS</th>
                    </>
                  )}
                  {type === 'bbps' && (
                    <>
                      <th className="px-4 py-3 text-left text-sm font-semibold text-gray-700">BILLER</th>
                      <th className="px-4 py-3 text-left text-sm font-semibold text-gray-700">AMOUNT</th>
                      <th className="px-4 py-3 text-left text-sm font-semibold text-gray-700">STATUS</th>
                    </>
                  )}
                </tr>
              </thead>
              <tbody>
                {transactions.map((txn) => (
                  <tr key={txn.id} className="border-b border-gray-200 hover:bg-gray-50">
                    <td className="px-4 py-3 text-sm text-gray-700">{formatDateTime(txn.date)}</td>
                    <td className="px-4 py-3 text-sm text-gray-900 font-medium">{txn.serviceId}</td>
                    {type === 'payin' && (
                      <>
                        <td className="px-4 py-3 text-sm text-gray-700">{txn.customerId || '-'}</td>
                        <td className="px-4 py-3 text-sm text-gray-700">{txn.mode || '-'}</td>
                        <td className="px-4 py-3 text-sm text-gray-900">{formatCurrency(txn.amount)}</td>
                        <td className="px-4 py-3 text-sm text-gray-700">{formatCurrency(txn.charge || 0)}</td>
                        <td className="px-4 py-3 text-sm font-semibold text-blue-600">{formatCurrency(txn.netCredit || txn.amount)}</td>
                        <td className="px-4 py-3 text-sm text-gray-700">{txn.cardNumber || '-'}</td>
                        <td className="px-4 py-3 text-sm text-gray-700">{txn.cardNetwork || '-'}</td>
                        <td className="px-4 py-3 text-sm text-gray-700">{txn.bankTransactionId || '-'}</td>
                        <td className="px-4 py-3 text-sm text-gray-700">{txn.gatewayName || '-'}</td>
                        <td className="px-4 py-3">{getStatusBadge(txn.status)}</td>
                        <td className="px-4 py-3 text-sm text-gray-700">-</td>
                      </>
                    )}
                    {type === 'payout' && (
                      <>
                        <td className="px-4 py-3 text-sm text-gray-700">{txn.retailerId || '-'}</td>
                        <td className="px-4 py-3 text-sm text-gray-700">{txn.operatorId || '-'}</td>
                        <td className="px-4 py-3 text-sm text-gray-700">{txn.accountNumber || '-'}</td>
                        <td className="px-4 py-3 text-sm text-gray-700">{txn.bankName || '-'}</td>
                        <td className="px-4 py-3 text-sm text-gray-900">{formatCurrency(txn.amount)}</td>
                        <td className="px-4 py-3">{getStatusBadge(txn.status)}</td>
                      </>
                    )}
                    {type === 'bbps' && (
                      <>
                        <td className="px-4 py-3 text-sm text-gray-700">{txn.biller || '-'}</td>
                        <td className="px-4 py-3 text-sm text-gray-900">{formatCurrency(txn.amount)}</td>
                        <td className="px-4 py-3">{getStatusBadge(txn.status)}</td>
                      </>
                    )}
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
