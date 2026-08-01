import React, { useEffect, useState } from 'react';
import { useAuth } from '../../../context/AuthContext';
import { isAdminUser } from '../../../utils/rolePermissions';
import aepsAPI from '../services/aepsApi';

const AepsReports = () => {
  const { user } = useAuth();
  const isAdmin = isAdminUser(user);
  const [summary, setSummary] = useState(null);
  const [rows, setRows] = useState([]);

  useEffect(() => {
    const params = isAdmin ? { scope: 'all', days: 30 } : { days: 30 };
    aepsAPI.reportsSummary(params).then((res) => {
      if (res.success) setSummary(res.data);
    });
    aepsAPI.transactions(isAdmin ? { scope: 'all', limit: 100 } : { limit: 100 }).then((res) => {
      if (res.success) setRows(res.data?.results || []);
    });
  }, [isAdmin]);

  return (
    <div className="space-y-6">
      <header>
        <h2 className="text-xl font-bold text-slate-900">AEPS reports</h2>
        <p className="text-sm text-slate-500">
          Built only on AEPS transactions{isAdmin ? ' (all users)' : ' (your activity)'}.
        </p>
      </header>

      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
        <Card label="Total" value={summary?.total ?? '—'} />
        <Card label="Success" value={summary?.success ?? '—'} />
        <Card label="Failed" value={summary?.failed ?? '—'} />
        <Card label="Pending" value={summary?.pending ?? '—'} />
        <Card label="Volume" value={summary?.volume != null ? `₹${summary.volume}` : '—'} />
      </div>

      <div className="overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm">
        <table className="min-w-full text-left text-sm">
          <thead className="bg-slate-50 text-xs uppercase text-slate-500">
            <tr>
              <th className="px-4 py-3">Product</th>
              <th className="px-4 py-3">Status</th>
              <th className="px-4 py-3">Amount</th>
              <th className="px-4 py-3">RRN</th>
              <th className="px-4 py-3">When</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => (
              <tr key={r.merchant_tran_id} className="border-t border-slate-100">
                <td className="px-4 py-3">{r.product}</td>
                <td className="px-4 py-3">{r.status}</td>
                <td className="px-4 py-3">₹{r.amount}</td>
                <td className="px-4 py-3 font-mono text-xs">{r.bank_rrn || '—'}</td>
                <td className="px-4 py-3 text-slate-600">
                  {r.created_at ? new Date(r.created_at).toLocaleString() : '—'}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
};

const Card = ({ label, value }) => (
  <div className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
    <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">{label}</p>
    <p className="mt-1 text-2xl font-bold text-slate-900">{value}</p>
  </div>
);

export default AepsReports;
