import React, { useState, useEffect, useCallback } from 'react';
import { useAuth } from '../../context/AuthContext';
import { reportsAPI } from '../../services/api';
import { formatCurrency, formatDateTime } from '../../utils/formatters';

const CommissionReport = () => {
  const { user } = useAuth();
  const [commissions, setCommissions] = useState([]);
  const [loading, setLoading] = useState(false);
  const [totalCommission, setTotalCommission] = useState(0);

  const loadCommissions = useCallback(async () => {
    if (!user) return;

    setLoading(true);
    try {
      const result = await reportsAPI.getCommissionReport();
      if (!result.success) {
        setCommissions([]);
        setTotalCommission(0);
        return;
      }
      const raw = result.data?.transactions || [];
      const mapped = raw.map((row) => ({
        id: row.id,
        date: row.created_at,
        fromUser: row.description || '—',
        fromUserId: '—',
        transactionId: row.reference != null && row.reference !== '' ? String(row.reference) : String(row.id),
        transactionAmount: null,
        commissionRate: null,
        commissionAmount: parseFloat(row.amount) || 0,
        status: 'SUCCESS',
      }));
      setCommissions(mapped);
      const summaryTotal = result.data?.summary?.total_commission;
      if (summaryTotal != null && !Number.isNaN(Number(summaryTotal))) {
        setTotalCommission(Number(summaryTotal));
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
  }, [user]);

  useEffect(() => {
    loadCommissions();
  }, [loadCommissions]);

  return (
    <div className="space-y-6">
      <div className="bg-white rounded-xl shadow-sm p-6 border border-gray-200">
        <h2 className="text-2xl font-bold text-gray-900 mb-6">Commission Report</h2>

        {/* Total Commission */}
        <div className="mb-6 p-4 bg-blue-50 border-2 border-blue-200 rounded-lg">
          <p className="text-sm text-gray-600 mb-1">Total Commission Earned</p>
          <p className="text-3xl font-bold text-blue-600">{formatCurrency(totalCommission)}</p>
        </div>

        {/* Commissions Table */}
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
                  <th className="px-4 py-3 text-left text-sm font-semibold text-gray-700">FROM USER</th>
                  <th className="px-4 py-3 text-left text-sm font-semibold text-gray-700">USER ID</th>
                  <th className="px-4 py-3 text-left text-sm font-semibold text-gray-700">TRANSACTION ID</th>
                  <th className="px-4 py-3 text-left text-sm font-semibold text-gray-700">TRANSACTION AMOUNT</th>
                  <th className="px-4 py-3 text-left text-sm font-semibold text-gray-700">COMMISSION RATE</th>
                  <th className="px-4 py-3 text-left text-sm font-semibold text-gray-700">COMMISSION AMOUNT</th>
                  <th className="px-4 py-3 text-left text-sm font-semibold text-gray-700">STATUS</th>
                </tr>
              </thead>
              <tbody>
                {commissions.map((comm) => (
                  <tr key={comm.id} className="border-b border-gray-200 hover:bg-gray-50">
                    <td className="px-4 py-3 text-sm text-gray-700">{formatDateTime(comm.date)}</td>
                    <td className="px-4 py-3 text-sm text-gray-900 font-medium">{comm.fromUser || '-'}</td>
                    <td className="px-4 py-3 text-sm text-gray-700">{comm.fromUserId || '-'}</td>
                    <td className="px-4 py-3 text-sm text-gray-700">{comm.transactionId || '-'}</td>
                    <td className="px-4 py-3 text-sm text-gray-900">
                      {comm.transactionAmount != null ? formatCurrency(comm.transactionAmount) : '—'}
                    </td>
                    <td className="px-4 py-3 text-sm text-gray-700">
                      {comm.commissionRate != null ? `${comm.commissionRate * 100}%` : '—'}
                    </td>
                    <td className="px-4 py-3 text-sm font-semibold text-green-600">{formatCurrency(comm.commissionAmount || 0)}</td>
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
