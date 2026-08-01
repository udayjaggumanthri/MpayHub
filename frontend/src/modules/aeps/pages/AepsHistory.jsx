import React, { useEffect, useState } from 'react';
import aepsAPI from '../services/aepsApi';

const AepsHistory = () => {
  const [rows, setRows] = useState([]);
  const [total, setTotal] = useState(0);
  const [filters, setFilters] = useState({ product: '', status: '', search: '' });

  const load = async () => {
    const res = await aepsAPI.transactions({
      product: filters.product || undefined,
      status: filters.status || undefined,
      search: filters.search || undefined,
      limit: 50,
    });
    if (res.success) {
      setRows(res.data?.results || []);
      setTotal(res.data?.total || 0);
    }
  };

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <div className="space-y-4">
      <header className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h2 className="text-xl font-bold text-slate-900">AEPS history</h2>
          <p className="text-sm text-slate-500">Module-local only — not mixed with Pay-in/Payout/BBPS reports.</p>
        </div>
        <button
          type="button"
          onClick={load}
          className="rounded-lg bg-slate-100 px-3 py-2 text-sm font-semibold text-slate-800 hover:bg-slate-200"
        >
          Refresh
        </button>
      </header>

      <div className="flex flex-wrap gap-2">
        <select
          className="rounded-lg border border-slate-200 px-3 py-2 text-sm"
          value={filters.product}
          onChange={(e) => setFilters({ ...filters, product: e.target.value })}
        >
          <option value="">All products</option>
          {['CW', 'BE', 'MS', 'AP', 'CD', 'EKY', '2FA'].map((p) => (
            <option key={p} value={p}>
              {p}
            </option>
          ))}
        </select>
        <select
          className="rounded-lg border border-slate-200 px-3 py-2 text-sm"
          value={filters.status}
          onChange={(e) => setFilters({ ...filters, status: e.target.value })}
        >
          <option value="">All status</option>
          {['success', 'failed', 'pending', 'timeout', 'reconciled'].map((s) => (
            <option key={s} value={s}>
              {s}
            </option>
          ))}
        </select>
        <input
          className="rounded-lg border border-slate-200 px-3 py-2 text-sm"
          placeholder="Search RRN / txn id"
          value={filters.search}
          onChange={(e) => setFilters({ ...filters, search: e.target.value })}
        />
        <button type="button" onClick={load} className="rounded-lg bg-blue-600 px-3 py-2 text-sm font-semibold text-white">
          Apply
        </button>
      </div>

      <div className="overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm">
        <table className="min-w-full text-left text-sm">
          <thead className="bg-slate-50 text-xs uppercase tracking-wide text-slate-500">
            <tr>
              <th className="px-4 py-3">Time</th>
              <th className="px-4 py-3">Product</th>
              <th className="px-4 py-3">Amount</th>
              <th className="px-4 py-3">Status</th>
              <th className="px-4 py-3">RRN</th>
              <th className="px-4 py-3">Txn id</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => (
              <tr key={r.merchant_tran_id} className="border-t border-slate-100">
                <td className="px-4 py-3 text-slate-600">{r.created_at ? new Date(r.created_at).toLocaleString() : '—'}</td>
                <td className="px-4 py-3 font-medium">{r.product}</td>
                <td className="px-4 py-3">₹{r.amount}</td>
                <td className="px-4 py-3">{r.status}</td>
                <td className="px-4 py-3 font-mono text-xs">{r.bank_rrn || '—'}</td>
                <td className="px-4 py-3 font-mono text-xs">{r.merchant_tran_id}</td>
              </tr>
            ))}
            {!rows.length ? (
              <tr>
                <td colSpan={6} className="px-4 py-10 text-center text-slate-500">
                  No AEPS transactions yet ({total} total).
                </td>
              </tr>
            ) : null}
          </tbody>
        </table>
      </div>
    </div>
  );
};

export default AepsHistory;
