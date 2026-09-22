import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  HiArrowsRightLeft,
  HiBanknotes,
  HiBuildingLibrary,
  HiFingerPrint,
  HiReceiptPercent,
} from 'react-icons/hi2';
import { reportsAPI } from '../../services/api';
import { formatCurrency } from '../../utils/formatters';

const TYPE_ICON = {
  payin: HiBanknotes,
  payout: HiArrowsRightLeft,
  bbps: HiReceiptPercent,
  aeps: HiFingerPrint,
  cms: HiBuildingLibrary,
};

const STATUS_CLASS = {
  SUCCESS: 'bg-emerald-50 text-emerald-700 dark:bg-emerald-950/50 dark:text-emerald-300',
  PENDING: 'bg-amber-50 text-amber-800 dark:bg-amber-950/40 dark:text-amber-300',
  FAILED: 'bg-rose-50 text-rose-700 dark:bg-rose-950/40 dark:text-rose-300',
};

const STATUS_LABEL = {
  SUCCESS: 'Success',
  PENDING: 'Pending',
  FAILED: 'Failed',
};

function formatWhen(iso) {
  if (!iso) return '—';
  try {
    return new Date(iso).toLocaleString('en-IN', {
      day: '2-digit',
      month: 'short',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    });
  } catch {
    return iso;
  }
}

const RecentTransactionsTable = () => {
  const navigate = useNavigate();
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let mounted = true;
    reportsAPI.getDashboardRecentTransactions({ limit: 8 }).then((res) => {
      if (!mounted) return;
      setItems(res.success ? res.data?.items || [] : []);
      setLoading(false);
    });
    return () => {
      mounted = false;
    };
  }, []);

  return (
    <section
      aria-labelledby="dash-recent-heading"
      className="overflow-hidden rounded-2xl border border-slate-200/90 bg-white shadow-sm dark:border-slate-700/90 dark:bg-slate-900"
    >
      <div className="flex items-center justify-between gap-2 px-4 py-3 sm:px-5">
        <h2
          id="dash-recent-heading"
          className="text-[12px] font-semibold uppercase tracking-[0.12em] text-slate-500 dark:text-slate-400"
        >
          Recent Transactions
        </h2>
        <button
          type="button"
          onClick={() => navigate('/reports/payin')}
          className="text-xs font-semibold text-blue-600 hover:text-blue-800 dark:text-blue-400"
        >
          View All →
        </button>
      </div>

      {loading ? (
        <div className="space-y-2 px-4 pb-4" aria-busy="true">
          {Array.from({ length: 4 }).map((_, i) => (
            <div key={i} className="h-10 animate-pulse rounded-lg bg-slate-100 dark:bg-slate-800" />
          ))}
        </div>
      ) : items.length === 0 ? (
        <p className="px-4 pb-5 text-sm text-slate-500 dark:text-slate-400">
          No recent transactions yet. Load money or pay a bill to see them here.
        </p>
      ) : (
        <>
          <div className="hidden overflow-x-auto sm:block">
            <table className="min-w-full text-sm">
              <thead>
                <tr className="border-y border-slate-100 text-left text-[11px] uppercase tracking-wide text-slate-500 dark:border-slate-800 dark:text-slate-400">
                  <th className="px-4 py-2 font-semibold sm:px-5">#</th>
                  <th className="px-3 py-2 font-semibold">Date &amp; Time</th>
                  <th className="px-3 py-2 font-semibold">Type</th>
                  <th className="px-3 py-2 text-right font-semibold">Amount</th>
                  <th className="px-4 py-2 text-right font-semibold sm:px-5">Status</th>
                </tr>
              </thead>
              <tbody>
                {items.map((row, index) => {
                  const Icon = TYPE_ICON[row.module] || HiBanknotes;
                  const amount = Number(row.amount || 0);
                  const signed = row.signed === 'debit' ? -amount : amount;
                  return (
                    <tr
                      key={row.id}
                      className="border-b border-slate-50 last:border-0 dark:border-slate-800/80"
                    >
                      <td className="px-4 py-2.5 tabular-nums text-slate-400 sm:px-5">{index + 1}</td>
                      <td className="px-3 py-2.5 text-slate-600 dark:text-slate-300">
                        {formatWhen(row.created_at)}
                      </td>
                      <td className="px-3 py-2.5">
                        <span className="inline-flex items-center gap-2 font-medium text-slate-800 dark:text-slate-100">
                          <Icon className="h-4 w-4 text-slate-400" aria-hidden />
                          {row.type}
                        </span>
                      </td>
                      <td
                        className={`px-3 py-2.5 text-right tabular-nums font-semibold ${
                          signed < 0 ? 'text-rose-600 dark:text-rose-300' : 'text-emerald-700 dark:text-emerald-300'
                        }`}
                      >
                        {signed < 0 ? '−' : '+'}
                        {formatCurrency(Math.abs(signed))}
                      </td>
                      <td className="px-4 py-2.5 text-right sm:px-5">
                        <span
                          className={`inline-flex rounded-full px-2 py-0.5 text-[11px] font-semibold ${
                            STATUS_CLASS[row.status] || STATUS_CLASS.PENDING
                          }`}
                        >
                          {STATUS_LABEL[row.status] || row.status}
                        </span>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>

          <ul className="divide-y divide-slate-100 px-4 pb-3 sm:hidden dark:divide-slate-800">
            {items.map((row) => {
              const Icon = TYPE_ICON[row.module] || HiBanknotes;
              const amount = Number(row.amount || 0);
              const signed = row.signed === 'debit' ? -amount : amount;
              return (
                <li key={row.id} className="flex items-center justify-between gap-3 py-3">
                  <span className="flex min-w-0 items-center gap-2">
                    <Icon className="h-4 w-4 shrink-0 text-slate-400" aria-hidden />
                    <span className="min-w-0">
                      <span className="block truncate text-sm font-semibold text-slate-800 dark:text-slate-100">
                        {row.type}
                      </span>
                      <span className="block text-[11px] text-slate-500">{formatWhen(row.created_at)}</span>
                    </span>
                  </span>
                  <span className="text-right">
                    <span
                      className={`block text-sm font-bold tabular-nums ${
                        signed < 0 ? 'text-rose-600' : 'text-emerald-700'
                      }`}
                    >
                      {signed < 0 ? '−' : '+'}
                      {formatCurrency(Math.abs(signed))}
                    </span>
                    <span className={`text-[10px] font-semibold ${STATUS_CLASS[row.status] || ''}`}>
                      {STATUS_LABEL[row.status] || row.status}
                    </span>
                  </span>
                </li>
              );
            })}
          </ul>
        </>
      )}
    </section>
  );
};

export default RecentTransactionsTable;
