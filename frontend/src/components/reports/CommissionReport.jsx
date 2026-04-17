import React, { useState, useEffect, useCallback } from 'react';
import { FiDownload } from 'react-icons/fi';
import { useAuth } from '../../context/AuthContext';
import { reportsAPI } from '../../services/api';
import { canUseTeamReportScope } from '../../utils/rolePermissions';
import { formatCurrency, formatDateTime } from '../../utils/formatters';

const CommissionReport = () => {
  const { user } = useAuth();
  const [commissions, setCommissions] = useState([]);
  const [loading, setLoading] = useState(false);
  const [totalCommission, setTotalCommission] = useState(0);
  const [reportScope, setReportScope] = useState('self');
  const [filters, setFilters] = useState({
    dateFrom: '',
    dateTo: '',
    mobile: '',
    agentRole: '',
    serviceId: '',
  });

  const loadCommissions = useCallback(async () => {
    if (!user) return;

    setLoading(true);
    try {
      const params =
        reportScope === 'team' && canUseTeamReportScope(user?.role) ? { scope: 'team' } : {};
      if (filters.dateFrom) params.date_from = filters.dateFrom;
      if (filters.dateTo) params.date_to = filters.dateTo;
      if (filters.mobile.trim()) params.mobile = filters.mobile.trim();
      if (filters.agentRole.trim()) params.agent_role = filters.agentRole.trim();
      if (filters.serviceId.trim()) params.service_id = filters.serviceId.trim();
      const result = await reportsAPI.getCommissionReport(params);
      if (!result.success) {
        setCommissions([]);
        setTotalCommission(0);
        return;
      }

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
      console.error('Error loading commissions:', error);
      setCommissions([]);
      setTotalCommission(0);
    } finally {
      setLoading(false);
    }
  }, [user, reportScope, filters]);

  useEffect(() => {
    loadCommissions();
  }, [loadCommissions]);

  return (
    <div className="space-y-6">
      <div className="bg-white rounded-xl shadow-sm p-6 border border-gray-200">
        <h2 className="text-2xl font-bold text-gray-900 mb-4">Commission Report</h2>
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
              All my commission
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
              From downline pay-in
            </button>
          </div>
        )}

        <div className="mb-6 grid grid-cols-1 gap-3 rounded-lg border border-gray-200 bg-gray-50 p-4 md:grid-cols-3 lg:grid-cols-5">
          <div>
            <label className="mb-1 block text-xs font-medium text-gray-600">Date from</label>
            <input
              type="date"
              value={filters.dateFrom}
              onChange={(e) => setFilters({ ...filters, dateFrom: e.target.value })}
              className="w-full rounded border border-gray-300 px-2 py-2 text-sm"
            />
          </div>
          <div>
            <label className="mb-1 block text-xs font-medium text-gray-600">Date to</label>
            <input
              type="date"
              value={filters.dateTo}
              onChange={(e) => setFilters({ ...filters, dateTo: e.target.value })}
              className="w-full rounded border border-gray-300 px-2 py-2 text-sm"
            />
          </div>
          <div>
            <label className="mb-1 block text-xs font-medium text-gray-600">Source mobile</label>
            <input
              type="text"
              value={filters.mobile}
              onChange={(e) => setFilters({ ...filters, mobile: e.target.value })}
              className="w-full rounded border border-gray-300 px-2 py-2 text-sm"
            />
          </div>
          <div>
            <label className="mb-1 block text-xs font-medium text-gray-600">Source role</label>
            <input
              type="text"
              value={filters.agentRole}
              onChange={(e) => setFilters({ ...filters, agentRole: e.target.value })}
              className="w-full rounded border border-gray-300 px-2 py-2 text-sm"
            />
          </div>
          <div>
            <label className="mb-1 block text-xs font-medium text-gray-600">Pay-in ref</label>
            <input
              type="text"
              value={filters.serviceId}
              onChange={(e) => setFilters({ ...filters, serviceId: e.target.value })}
              className="w-full rounded border border-gray-300 px-2 py-2 text-sm"
            />
          </div>
        </div>

        <div className="mb-6 p-4 bg-blue-50 border-2 border-blue-200 rounded-lg">
          <div className="mb-3 flex justify-end">
            <button
              type="button"
              onClick={async () => {
                const params =
                  reportScope === 'team' && canUseTeamReportScope(user?.role) ? { scope: 'team' } : {};
                if (filters.dateFrom) params.date_from = filters.dateFrom;
                if (filters.dateTo) params.date_to = filters.dateTo;
                if (filters.mobile.trim()) params.mobile = filters.mobile.trim();
                if (filters.agentRole.trim()) params.agent_role = filters.agentRole.trim();
                if (filters.serviceId.trim()) params.service_id = filters.serviceId.trim();
                const res = await reportsAPI.downloadReportCsv('/reports/commission/export.csv', params);
                if (!res.success || !res.blob) return;
                const url = window.URL.createObjectURL(res.blob);
                const a = document.createElement('a');
                a.href = url;
                a.download = 'commission_report.csv';
                a.click();
                window.URL.revokeObjectURL(url);
              }}
              className="inline-flex items-center gap-2 rounded-lg border border-gray-300 bg-white px-4 py-2 text-sm font-semibold text-gray-800 shadow-sm hover:bg-gray-50"
            >
              <FiDownload className="h-4 w-4" aria-hidden />
              Download CSV
            </button>
          </div>
          <p className="text-sm text-gray-600 mb-1">Net commission (this view)</p>
          <p className="text-3xl font-bold text-blue-600">{formatCurrency(totalCommission)}</p>
        </div>

        {loading ? (
          <div className="text-center py-12">
            <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto"></div>
            <p className="mt-4 text-gray-600">Loading commissions...</p>
          </div>
        ) : commissions.length === 0 ? (
          <div className="text-center py-12 text-gray-500">No commission records found</div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full border-collapse">
              <thead>
                <tr className="bg-gray-50 border-b border-gray-200">
                  <th className="px-4 py-3 text-left text-sm font-semibold text-gray-700">DATE & TIME</th>
                  <th className="px-4 py-3 text-left text-sm font-semibold text-gray-700">SOURCE NAME</th>
                  <th className="px-4 py-3 text-left text-sm font-semibold text-gray-700">USER ID</th>
                  <th className="px-4 py-3 text-left text-sm font-semibold text-gray-700">ROLE</th>
                  <th className="px-4 py-3 text-left text-sm font-semibold text-gray-700">PAY-IN REF</th>
                  <th className="px-4 py-3 text-left text-sm font-semibold text-gray-700">SLICE / NOTE</th>
                  <th className="px-4 py-3 text-left text-sm font-semibold text-gray-700">AMOUNT</th>
                  <th className="px-4 py-3 text-left text-sm font-semibold text-gray-700">STATUS</th>
                </tr>
              </thead>
              <tbody>
                {commissions.map((comm) => (
                  <tr key={comm.id} className="border-b border-gray-200 hover:bg-gray-50">
                    <td className="px-4 py-3 text-sm text-gray-700">{formatDateTime(comm.date)}</td>
                    <td className="px-4 py-3 text-sm text-gray-900 font-medium">{comm.fromUser || '-'}</td>
                    <td className="px-4 py-3 text-sm text-gray-700">{comm.fromUserId || '-'}</td>
                    <td className="px-4 py-3 text-sm text-gray-700">{comm.fromRole || '—'}</td>
                    <td className="px-4 py-3 text-sm text-gray-700">{comm.transactionId || '-'}</td>
                    <td className="px-4 py-3 text-sm text-gray-700">
                      {comm.commissionRate != null ? String(comm.commissionRate) : '—'}
                    </td>
                    <td className="px-4 py-3 text-sm font-semibold text-green-600">
                      {formatCurrency(comm.commissionAmount || 0)}
                    </td>
                    <td className="px-4 py-3">
                      <span className="px-3 py-1 rounded-full text-xs font-semibold bg-green-100 text-green-800 border border-green-200">
                        {comm.status || 'SUCCESS'}
                      </span>
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

export default CommissionReport;
