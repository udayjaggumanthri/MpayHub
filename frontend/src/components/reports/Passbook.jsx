import React, { useState, useEffect, useCallback } from 'react';
import { useAuth } from '../../context/AuthContext';
import { FiDownload } from 'react-icons/fi';
import { passbookAPI, reportsAPI } from '../../services/api';
import { canUseTeamReportScope } from '../../utils/rolePermissions';
import { formatCurrency, formatDateTime } from '../../utils/formatters';

const Passbook = () => {
  const { user } = useAuth();
  const [reportScope, setReportScope] = useState('self');
  const [entries, setEntries] = useState([]);
  const [filters, setFilters] = useState({
    search: '',
    dateFrom: '',
    dateTo: '',
    mobile: '',
    amountMin: '',
    amountMax: '',
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
      if (reportScope === 'team' && canUseTeamReportScope(user?.role)) {
        params.scope = 'team';
      }
      const q = filters.search.trim();
      if (q) params.search = q;
      if (filters.dateFrom) params.date_from = filters.dateFrom;
      if (filters.dateTo) params.date_to = filters.dateTo;
      if (filters.mobile.trim()) params.mobile = filters.mobile.trim();
      if (filters.amountMin) params.amount_min = filters.amountMin;
      if (filters.amountMax) params.amount_max = filters.amountMax;

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
  }, [user, filters, reportScope]);

  useEffect(() => {
    loadPassbook();
  }, [loadPassbook]);

  return (
    <div className="space-y-6">
      <div className="bg-white rounded-xl shadow-sm p-6 border border-gray-200">
        <h2 className="text-2xl font-bold text-gray-900 mb-4">Passbook</h2>
        <div className="mb-4 flex justify-end">
          <button
            type="button"
            onClick={async () => {
              const params = { page: 1, page_size: 5000 };
              if (reportScope === 'team' && canUseTeamReportScope(user?.role)) params.scope = 'team';
              const q = filters.search.trim();
              if (q) params.search = q;
              if (filters.dateFrom) params.date_from = filters.dateFrom;
              if (filters.dateTo) params.date_to = filters.dateTo;
              if (filters.mobile.trim()) params.mobile = filters.mobile.trim();
              if (filters.amountMin) params.amount_min = filters.amountMin;
              if (filters.amountMax) params.amount_max = filters.amountMax;
              const res = await reportsAPI.downloadReportCsv('/reports/passbook/export.csv', params);
              if (!res.success || !res.blob) return;
              const url = window.URL.createObjectURL(res.blob);
              const a = document.createElement('a');
              a.href = url;
              a.download = 'passbook_report.csv';
              a.click();
              window.URL.revokeObjectURL(url);
            }}
            className="inline-flex items-center gap-2 rounded-lg border border-gray-300 bg-white px-4 py-2 text-sm font-semibold text-gray-800 shadow-sm hover:bg-gray-50"
          >
            <FiDownload className="h-4 w-4" aria-hidden />
            Download CSV
          </button>
        </div>

        {canUseTeamReportScope(user?.role) && (
          <div className="flex flex-wrap gap-2 mb-6">
            <button
              type="button"
              onClick={() => setReportScope('self')}
              className={`px-4 py-2 rounded-lg text-sm font-semibold border ${
                reportScope === 'self'
                  ? 'bg-blue-600 text-white border-blue-600'
                  : 'bg-white text-gray-700 border-gray-300'
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
                  : 'bg-white text-gray-700 border-gray-300'
              }`}
            >
              Team passbooks
            </button>
          </div>
        )}

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
          <div className="grid grid-cols-1 md:grid-cols-3 lg:grid-cols-6 gap-4">
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
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">Mobile</label>
              <input
                type="text"
                value={filters.mobile}
                onChange={(e) => setFilters({ ...filters, mobile: e.target.value })}
                className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">Amount min</label>
              <input
                type="text"
                value={filters.amountMin}
                onChange={(e) => setFilters({ ...filters, amountMin: e.target.value })}
                className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">Amount max</label>
              <input
                type="text"
                value={filters.amountMax}
                onChange={(e) => setFilters({ ...filters, amountMax: e.target.value })}
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
                  <th className="px-4 py-3 text-left text-sm font-semibold text-gray-700">USER ID</th>
                  <th className="px-4 py-3 text-right text-sm font-semibold text-gray-700">CHARGE</th>
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
                    <td className="px-4 py-3 text-sm text-gray-600">{entry.ownerUserId || '—'}</td>
                    <td className="px-4 py-3 text-sm text-gray-700 text-right">
                      {entry.serviceCharge > 0 ? formatCurrency(entry.serviceCharge) : '—'}
                    </td>
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
