import React, { useEffect, useState } from 'react';
import { useAuth } from '../../../context/AuthContext';
import { isAdminUser } from '../../../utils/rolePermissions';
import Card from '../../../components/common/Card';
import Button from '../../../components/common/Button';
import aepsAPI from '../services/aepsApi';

const AepsReports = () => {
  const { user } = useAuth();
  const isAdmin = isAdminUser(user);
  const [summary, setSummary] = useState(null);
  const [rows, setRows] = useState([]);
  const [days, setDays] = useState(30);

  const load = async () => {
    const params = isAdmin ? { scope: 'all', days } : { days };
    const [sum, tx] = await Promise.all([
      aepsAPI.reportsSummary(params),
      aepsAPI.transactions(isAdmin ? { scope: 'all', limit: 100 } : { limit: 100 }),
    ]);
    if (sum.success) setSummary(sum.data);
    if (tx.success) setRows(tx.data?.results || []);
  };

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isAdmin, days]);

  const exportCsv = () => {
    const header = ['product', 'status', 'amount', 'bank_rrn', 'created_at'];
    const lines = [header.join(',')].concat(
      rows.map((r) =>
        [r.product, r.status, r.amount, r.bank_rrn || '', r.created_at || '']
          .map((c) => `"${String(c).replace(/"/g, '""')}"`)
          .join(',')
      )
    );
    const blob = new Blob([lines.join('\n')], { type: 'text/csv;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `aeps-reports-${Date.now()}.csv`;
    a.click();
    URL.revokeObjectURL(url);
  };

  return (
    <div className="space-y-6">
      <header className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h2 className="text-xl font-bold text-slate-900">AEPS reports</h2>
          <p className="text-sm text-slate-500">
            Built only on AEPS transactions{isAdmin ? ' (all users)' : ' (your activity)'}.
          </p>
        </div>
        <div className="flex gap-2">
          <select
            className="rounded-lg border border-slate-200 px-3 py-2 text-sm"
            value={days}
            onChange={(e) => setDays(Number(e.target.value))}
          >
            {[7, 30, 90].map((d) => (
              <option key={d} value={d}>
                Last {d} days
              </option>
            ))}
          </select>
          <Button size="sm" variant="secondary" onClick={exportCsv}>
            Export CSV
          </Button>
        </div>
      </header>

      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
        <Metric label="Total" value={summary?.total ?? '—'} />
        <Metric label="Success" value={summary?.success ?? '—'} />
        <Metric label="Failed" value={summary?.failed ?? '—'} />
        <Metric label="Pending" value={summary?.pending ?? '—'} />
        <Metric label="Volume" value={summary?.volume != null ? `₹${summary.volume}` : '—'} />
      </div>

      <div className="overflow-x-auto rounded-xl border border-slate-200 bg-white shadow-sm">
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
                <td className="whitespace-nowrap px-4 py-3 text-slate-600">
                  {r.created_at ? new Date(r.created_at).toLocaleString() : '—'}
                </td>
              </tr>
            ))}
            {!rows.length ? (
              <tr>
                <td colSpan={5} className="px-4 py-10 text-center text-slate-500">
                  No rows in this period.
                </td>
              </tr>
            ) : null}
          </tbody>
        </table>
      </div>
    </div>
  );
};

const Metric = ({ label, value }) => (
  <Card padding="md" shadow="sm">
    <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">{label}</p>
    <p className="mt-1 text-2xl font-bold text-slate-900">{value}</p>
  </Card>
);

export default AepsReports;
