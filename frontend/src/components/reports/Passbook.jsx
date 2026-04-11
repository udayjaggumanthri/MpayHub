import React, { useState, useEffect, useCallback } from 'react';
import { useAuth } from '../../context/AuthContext';
import { passbookAPI } from '../../services/api';
import { formatCurrency, formatDateTime } from '../../utils/formatters';

const Passbook = () => {
  const { user } = useAuth();
  const [entries, setEntries] = useState([]);
  const [filters, setFilters] = useState({
    search: '',
    dateFrom: '',
    dateTo: '',
  });
  const [loading, setLoading] = useState(false);
  const [summary, setSummary] = useState({
    openingBalance: 0,
    creditAmount: 0,
    debitAmount: 0,
    availableBalance: 0,
  });

  const loadPassbook = useCallback(async () => {
    if (!user) return;

    setLoading(true);
    try {
      const params = { page: 1, page_size: 500 };
      const q = filters.search.trim();
      if (q) params.search = q;
      if (filters.dateFrom) params.date_from = filters.dateFrom;
      if (filters.dateTo) params.date_to = filters.dateTo;

      const result = await passbookAPI.getPassbookEntries(params);
      if (!result.success) {
        setEntries([]);
        setSummary({
          openingBalance: 0,
          creditAmount: 0,
          debitAmount: 0,
          availableBalance: 0,
        });
        return;
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
      }));

      setEntries(sortedEntries);

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
    } catch (error) {
      console.error('Error loading passbook:', error);
      setEntries([]);
      setSummary({
        openingBalance: 0,
        creditAmount: 0,
        debitAmount: 0,
        availableBalance: 0,
      });
    } finally {
      setLoading(false);
    }
  }, [user, filters]);

  useEffect(() => {
    loadPassbook();
  }, [loadPassbook]);

  return (
    <div className="space-y-6">
      <div className="bg-white rounded-xl shadow-sm p-6 border border-gray-200">
        <h2 className="text-2xl font-bold text-gray-900 mb-6">Passbook</h2>

        {/* Summary Cards */}
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-6">
          <div className="bg-blue-50 border-2 border-blue-200 rounded-lg p-4">
            <p className="text-sm text-gray-600 mb-1">OPENING BALANCE</p>
            <p className="text-2xl font-bold text-blue-600">{formatCurrency(summary.openingBalance)}</p>
          </div>
          <div className="bg-green-50 border-2 border-green-200 rounded-lg p-4">
            <p className="text-sm text-gray-600 mb-1">CREDIT AMOUNT</p>
            <p className="text-2xl font-bold text-green-600">{formatCurrency(summary.creditAmount)}</p>
          </div>
          <div className="bg-red-50 border-2 border-red-200 rounded-lg p-4">
            <p className="text-sm text-gray-600 mb-1">DEBIT AMOUNT</p>
            <p className="text-2xl font-bold text-red-600">{formatCurrency(summary.debitAmount)}</p>
          </div>
          <div className="bg-purple-50 border-2 border-purple-200 rounded-lg p-4">
            <p className="text-sm text-gray-600 mb-1">AVAILABLE BALANCE</p>
            <p className="text-2xl font-bold text-purple-600">{formatCurrency(summary.availableBalance)}</p>
          </div>
        </div>

        {/* Filters */}
        <div className="mb-6 p-4 bg-gray-50 rounded-lg border border-gray-200">
          <h3 className="text-lg font-semibold text-gray-900 mb-4">FILTERS</h3>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">Search Anywhere</label>
              <input
                type="text"
                value={filters.search}
                onChange={(e) => setFilters({ ...filters, search: e.target.value })}
                placeholder="Search Service ID or Description"
                className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
              />
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

        {/* Passbook Table */}
        {loading ? (
          <div className="text-center py-12">
            <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto"></div>
            <p className="mt-4 text-gray-600">Loading passbook...</p>
          </div>
        ) : entries.length === 0 ? (
          <div className="text-center py-12 text-gray-500">No passbook entries found</div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full border-collapse">
              <thead>
                <tr className="bg-gray-50 border-b border-gray-200">
                  <th className="px-4 py-3 text-left text-sm font-semibold text-gray-700">DATE & TIME</th>
                  <th className="px-4 py-3 text-left text-sm font-semibold text-gray-700">SERVICE</th>
                  <th className="px-4 py-3 text-left text-sm font-semibold text-gray-700">SERVICE ID</th>
                  <th className="px-4 py-3 text-left text-sm font-semibold text-gray-700">DESCRIPTION</th>
                  <th className="px-4 py-3 text-right text-sm font-semibold text-gray-700">DEBIT AMOUNT</th>
                  <th className="px-4 py-3 text-right text-sm font-semibold text-gray-700">CREDIT AMOUNT</th>
                  <th className="px-4 py-3 text-left text-sm font-semibold text-gray-700">CL</th>
                  <th className="px-4 py-3 text-right text-sm font-semibold text-gray-700">CURRENT BALANCE</th>
                </tr>
              </thead>
              <tbody>
                {entries.map((entry, index) => (
                  <tr key={entry.id || index} className="border-b border-gray-200 hover:bg-gray-50">
                    <td className="px-4 py-3 text-sm text-gray-700">{formatDateTime(entry.date)}</td>
                    <td className="px-4 py-3 text-sm text-gray-900 font-medium">{entry.service || '-'}</td>
                    <td className="px-4 py-3 text-sm text-gray-700">{entry.serviceId || '-'}</td>
                    <td className="px-4 py-3 text-sm text-gray-700 max-w-md">{entry.description || '-'}</td>
                    <td className="px-4 py-3 text-sm text-red-600 text-right font-medium">
                      {entry.debitAmount > 0 ? formatCurrency(entry.debitAmount) : '-'}
                    </td>
                    <td className="px-4 py-3 text-sm text-green-600 text-right font-medium">
                      {entry.creditAmount > 0 ? formatCurrency(entry.creditAmount) : '-'}
                    </td>
                    <td className="px-4 py-3 text-sm text-gray-700">{entry.cl || '-'}</td>
                    <td className="px-4 py-3 text-sm text-gray-900 text-right font-semibold">
                      {formatCurrency(entry.closingBalance || entry.openingBalance || 0)}
                    </td>
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

export default Passbook;
