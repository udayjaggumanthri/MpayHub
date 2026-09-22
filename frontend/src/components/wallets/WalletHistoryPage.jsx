import React, { useEffect, useMemo, useState } from 'react';
import { useLocation, useParams } from 'react-router-dom';
import { walletsAPI } from '../../services/api';
import { formatCurrency, formatReportDateTime } from '../../utils/formatters';

const TITLES = {
  main: 'Main Wallet History',
  commission: 'Commission History (legacy)',
  bbps: 'BBPS History (legacy — now Main wallet)',
  profit: 'Profit History (legacy)',
};

const LEGACY_TYPES = new Set(['bbps', 'commission', 'profit']);

const normalizeWalletType = (raw) => {
  const decoded = decodeURIComponent(String(raw || ''));
  const cleaned = decoded.replace(/(?:[-_\s]*history)$/i, '');
  const v = cleaned
    .trim()
    .toLowerCase()
    .replace(/\s+/g, '')
    .replace(/_/g, '');
  const aliases = {
    main: 'main',
    mainwallet: 'main',
    commission: 'commission',
    commissionwallet: 'commission',
    bbps: 'bbps',
    bbpswallet: 'bbps',
    bbpshistory: 'bbps',
    profit: 'profit',
    profitwallet: 'profit',
    profithistory: 'profit',
    mainhistory: 'main',
    commissionhistory: 'commission',
  };
  return aliases[v] || v;
};

const WalletHistoryPage = () => {
  const { walletType } = useParams();
  const location = useLocation();
  const pathType = String(location.pathname || '').split('/wallets/')[1]?.split('/')[0] || '';
  const type = normalizeWalletType(walletType || pathType);
  const isLegacy = LEGACY_TYPES.has(type);
  const [rows, setRows] = useState([]);
  const [loading, setLoading] = useState(false);
  const [page, setPage] = useState(1);
  const [total, setTotal] = useState(0);
  const [errorMessage, setErrorMessage] = useState('');
  const pageSize = 20;

  const title = useMemo(() => {
    if (type === 'main') return TITLES.main;
    if (isLegacy) return TITLES[type] || 'Wallet History';
    return TITLES[type] || 'Wallet History';
  }, [type, isLegacy]);

  useEffect(() => {
    let mounted = true;
    const load = async () => {
      setLoading(true);
      setErrorMessage('');
      const historyType = type || 'main';
      const res = await walletsAPI.getWalletHistory(historyType, { page });
      if (!mounted) return;
      if (res.success) {
        setRows(res.data?.transactions || []);
        setTotal(parseInt(res.data?.total || 0, 10) || 0);
      } else {
        setRows([]);
        setTotal(0);
        setErrorMessage(res.message || 'Unable to fetch wallet history.');
      }
      setLoading(false);
    };
    if (type) {
      load();
    } else {
      setRows([]);
      setTotal(0);
      setErrorMessage('Invalid wallet type in URL.');
    }
    return () => {
      mounted = false;
    };
  }, [type, page]);

  const totalPages = Math.max(1, Math.ceil(total / pageSize));

  return (
    <div className="space-y-6">
      <div className="rounded-xl border border-gray-200 dark:border-slate-700 bg-white dark:bg-slate-900 p-6 shadow-sm">
        <h2 className="mb-2 text-2xl font-bold text-gray-900 dark:text-slate-100">{title}</h2>
        <p className="text-sm text-gray-600 dark:text-slate-400">
          Detailed ledger of credits/debits with references and business descriptions.
        </p>
        {isLegacy && (
          <div className="mt-4 rounded-lg border border-amber-200 dark:border-amber-800 bg-amber-50 dark:bg-amber-950/40 px-4 py-3 text-sm text-amber-900 dark:text-amber-200">
            This wallet was merged into Main. Historical lines below keep their original wallet type.
          </div>
        )}
      </div>

      <div className="rounded-xl border border-gray-200 dark:border-slate-700 bg-white dark:bg-slate-900 p-4 shadow-sm">
        {loading ? (
          <div className="py-12 text-center text-gray-600 dark:text-slate-400">Loading history…</div>
        ) : errorMessage ? (
          <div className="py-12 text-center text-red-600 dark:text-red-400">{errorMessage}</div>
        ) : rows.length === 0 ? (
          <div className="py-12 text-center text-gray-500 dark:text-slate-400">No ledger entries found.</div>
        ) : (
          <div className="overflow-x-auto">
            <table className="min-w-full border-collapse">
              <thead>
                <tr className="border-b border-gray-200 dark:border-slate-700 bg-gray-50 dark:bg-slate-800/50">
                  <th className="px-4 py-3 text-left text-sm font-semibold text-gray-700 dark:text-slate-300">Date</th>
                  <th className="px-4 py-3 text-left text-sm font-semibold text-gray-700 dark:text-slate-300">Type</th>
                  <th className="px-4 py-3 text-right text-sm font-semibold text-gray-700 dark:text-slate-300">Amount</th>
                  <th className="px-4 py-3 text-left text-sm font-semibold text-gray-700 dark:text-slate-300">Reference</th>
                  <th className="px-4 py-3 text-left text-sm font-semibold text-gray-700 dark:text-slate-300">Description</th>
                  <th className="px-4 py-3 text-left text-sm font-semibold text-gray-700 dark:text-slate-300">Source</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((r) => (
                  <tr key={r.id} className="border-b border-gray-100 dark:border-slate-800 hover:bg-gray-50 dark:hover:bg-slate-800">
                    <td className="px-4 py-3 text-sm text-gray-700 dark:text-slate-300">{formatReportDateTime(r.created_at)}</td>
                    <td className="px-4 py-3 text-sm font-medium text-gray-800 dark:text-slate-200">
                      {String(r.transaction_type || '').toUpperCase()}
                    </td>
                    <td
                      className={`px-4 py-3 text-right text-sm font-semibold ${
                        r.transaction_type === 'credit' ? 'text-green-700 dark:text-green-300' : 'text-red-700 dark:text-red-300'
                      }`}
                    >
                      {formatCurrency(parseFloat(r.amount || 0))}
                    </td>
                    <td className="px-4 py-3 text-sm text-gray-700 dark:text-slate-300">{r.reference || '—'}</td>
                    <td className="px-4 py-3 text-sm text-gray-700 dark:text-slate-300">
                      <span className="block">{r.description || '—'}</span>
                      {r.service ? (
                        <span className="mt-0.5 block text-xs text-gray-500 dark:text-slate-400">Service: {r.service}</span>
                      ) : null}
                    </td>
                    <td className="px-4 py-3 text-sm text-gray-700 dark:text-slate-300">
                      {r.source_user_code
                        ? `${r.source_name || r.source_user_code} (${r.source_role || '—'})`
                        : '—'}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        <div className="mt-4 flex items-center justify-between">
          <button
            type="button"
            disabled={page <= 1 || loading}
            onClick={() => setPage((p) => Math.max(1, p - 1))}
            className="rounded border border-gray-300 dark:border-slate-600 px-3 py-1.5 text-sm text-gray-700 dark:text-slate-300 disabled:opacity-50"
          >
            Previous
          </button>
          <span className="text-sm text-gray-600 dark:text-slate-400">
            Page {page} of {totalPages}
          </span>
          <button
            type="button"
            disabled={page >= totalPages || loading}
            onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
            className="rounded border border-gray-300 dark:border-slate-600 px-3 py-1.5 text-sm text-gray-700 dark:text-slate-300 disabled:opacity-50"
          >
            Next
          </button>
        </div>
      </div>
    </div>
  );
};

export default WalletHistoryPage;
