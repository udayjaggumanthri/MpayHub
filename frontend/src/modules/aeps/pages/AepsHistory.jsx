import React, { useEffect, useState } from 'react';
import Card from '../../../components/common/Card';
import Button from '../../../components/common/Button';
import ReportDateRange from '../../../components/common/ReportDateRange';
import aepsAPI from '../services/aepsApi';

const AepsHistory = () => {
  const [rows, setRows] = useState([]);
  const [total, setTotal] = useState(0);
  const [detail, setDetail] = useState(null);
  const [busy, setBusy] = useState(false);
  const [filters, setFilters] = useState({
    product: '',
    status: '',
    search: '',
    date_from: '',
    date_to: '',
  });

  const load = async () => {
    const res = await aepsAPI.transactions({
      product: filters.product || undefined,
      status: filters.status || undefined,
      search: filters.search || undefined,
      date_from: filters.date_from || undefined,
      date_to: filters.date_to || undefined,
      limit: 100,
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

  const exportCsv = () => {
    const header = ['created_at', 'product', 'amount', 'status', 'bank_rrn', 'merchant_tran_id'];
    const lines = [header.join(',')].concat(
      rows.map((r) =>
        [
          r.created_at || '',
          r.product || '',
          r.amount ?? '',
          r.status || '',
          r.bank_rrn || '',
          r.merchant_tran_id || '',
        ]
          .map((c) => `"${String(c).replace(/"/g, '""')}"`)
          .join(',')
      )
    );
    const blob = new Blob([lines.join('\n')], { type: 'text/csv;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `aeps-history-${Date.now()}.csv`;
    a.click();
    URL.revokeObjectURL(url);
  };

  const statusCheck = async (r) => {
    setBusy(true);
    const st = await aepsAPI.statusCheck(r.merchant_tran_id, {
      otp_mode: r.product === 'CD_OTP',
    });
    if (st.success) {
      setDetail(st.data?.transaction || st.data);
      await load();
    }
    setBusy(false);
  };

  return (
    <div className="space-y-4">
      <header className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h2 className="text-xl font-bold text-slate-900">AEPS history</h2>
          <p className="text-sm text-slate-500">Module-local only — not mixed with Pay-in/Payout/BBPS.</p>
        </div>
        <div className="flex gap-2">
          <Button size="sm" variant="secondary" onClick={exportCsv}>
            Export CSV
          </Button>
          <Button size="sm" variant="secondary" onClick={load}>
            Refresh
          </Button>
        </div>
      </header>

      <Card padding="sm" shadow="sm">
        <div className="flex flex-wrap gap-2">
          <select
            className="rounded-lg border border-slate-200 px-3 py-2 text-sm"
            value={filters.product}
            onChange={(e) => setFilters({ ...filters, product: e.target.value })}
          >
            <option value="">All products</option>
            {['CW', 'BE', 'MS', 'AP', 'CD', 'CD_OTP', 'EKY', '2FA'].map((p) => (
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
          <div className="min-w-0 w-full sm:min-w-[280px] sm:flex-1">
            <ReportDateRange
              idPrefix="aeps-history"
              dateFrom={filters.date_from}
              dateTo={filters.date_to}
              fromLabel="From"
              toLabel="To"
              onChange={({ dateFrom, dateTo }) =>
                setFilters({ ...filters, date_from: dateFrom, date_to: dateTo })
              }
            />
          </div>
          <input
            className="rounded-lg border border-slate-200 px-3 py-2 text-sm"
            placeholder="Search RRN / txn id"
            value={filters.search}
            onChange={(e) => setFilters({ ...filters, search: e.target.value })}
          />
          <Button size="sm" onClick={load}>
            Apply
          </Button>
        </div>
      </Card>

      <div className="overflow-x-auto rounded-xl border border-slate-200 bg-white shadow-sm">
        <table className="min-w-full text-left text-sm">
          <thead className="bg-slate-50 text-xs uppercase tracking-wide text-slate-500">
            <tr>
              <th className="px-4 py-3">Time</th>
              <th className="px-4 py-3">Product</th>
              <th className="px-4 py-3">Amount</th>
              <th className="px-4 py-3">Status</th>
              <th className="px-4 py-3">RRN</th>
              <th className="px-4 py-3">Txn id</th>
              <th className="px-4 py-3">Actions</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => (
              <tr key={r.merchant_tran_id} className="border-t border-slate-100">
                <td className="whitespace-nowrap px-4 py-3 text-slate-600">
                  {r.created_at ? new Date(r.created_at).toLocaleString() : '—'}
                </td>
                <td className="px-4 py-3 font-medium">{r.product}</td>
                <td className="px-4 py-3">₹{r.amount}</td>
                <td className="px-4 py-3">{r.status}</td>
                <td className="px-4 py-3 font-mono text-xs">{r.bank_rrn || '—'}</td>
                <td className="px-4 py-3 font-mono text-xs">{r.merchant_tran_id}</td>
                <td className="px-4 py-3">
                  <div className="flex gap-2">
                    <button
                      type="button"
                      className="text-xs font-semibold text-blue-700"
                      onClick={() => setDetail(r)}
                    >
                      Detail
                    </button>
                    {['pending', 'timeout', 'initiated'].includes(r.status) ? (
                      <button
                        type="button"
                        disabled={busy}
                        className="text-xs font-semibold text-slate-700"
                        onClick={() => statusCheck(r)}
                      >
                        Check
                      </button>
                    ) : null}
                  </div>
                </td>
              </tr>
            ))}
            {!rows.length ? (
              <tr>
                <td colSpan={7} className="px-4 py-10 text-center text-slate-500">
                  No AEPS transactions yet ({total} total).
                </td>
              </tr>
            ) : null}
          </tbody>
        </table>
      </div>

      {detail ? (
        <div className="fixed inset-0 z-40 flex items-end justify-center bg-black/40 p-4 sm:items-center">
          <Card className="max-h-[80vh] w-full max-w-lg overflow-auto" shadow="lg" title="Transaction detail">
            <pre className="overflow-auto rounded-lg bg-slate-50 p-3 text-xs text-slate-800">
              {JSON.stringify(detail, null, 2)}
            </pre>
            <Button className="mt-3" variant="secondary" onClick={() => setDetail(null)}>
              Close
            </Button>
          </Card>
        </div>
      ) : null}
    </div>
  );
};

export default AepsHistory;
