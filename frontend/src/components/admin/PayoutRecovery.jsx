import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import { adminAPI } from '../../services/api';
import Card from '../common/Card';
import Input from '../common/Input';
import Button from '../common/Button';
import LoadingSpinner from '../common/LoadingSpinner';
import { formatCurrency } from '../../utils/formatters';
import {
  FaArrowsRotate,
  FaCircleCheck,
  FaCircleXmark,
  FaClock,
  FaTriangleExclamation,
  FaWallet,
} from 'react-icons/fa6';

function formatWhen(iso) {
  if (!iso) return '—';
  try {
    return new Date(iso).toLocaleString('en-IN');
  } catch {
    return iso;
  }
}

const PayoutRecovery = () => {
  const [stats, setStats] = useState(null);
  const [rows, setRows] = useState([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [q, setQ] = useState('');
  const [appliedQ, setAppliedQ] = useState('');
  const [onlyStuck, setOnlyStuck] = useState(true);
  const [loading, setLoading] = useState(false);
  const [loadError, setLoadError] = useState('');
  const [selected, setSelected] = useState(null);
  const [rrn, setRrn] = useState('');
  const [providerTxnId, setProviderTxnId] = useState('');
  const [note, setNote] = useState('');
  const [reason, setReason] = useState('Provider/bank confirmed failure');
  const [actionBusy, setActionBusy] = useState(null);
  const [actionMsg, setActionMsg] = useState('');

  const loadStats = useCallback(async () => {
    const res = await adminAPI.getPayoutRecoveryStats();
    if (res.success) setStats(res.data);
  }, []);

  const loadList = useCallback(async () => {
    setLoading(true);
    setLoadError('');
    const res = await adminAPI.listPayoutRecovery({
      page,
      page_size: 20,
      q: appliedQ || undefined,
      min_age_minutes: onlyStuck ? 30 : undefined,
    });
    setLoading(false);
    if (!res.success) {
      setRows([]);
      setTotal(0);
      setLoadError(res.message || 'Could not load pending payouts');
      return;
    }
    setRows(res.data?.results || []);
    setTotal(res.data?.total || 0);
  }, [page, appliedQ, onlyStuck]);

  useEffect(() => {
    loadStats();
  }, [loadStats]);

  useEffect(() => {
    loadList();
  }, [loadList]);

  const openDetail = async (row) => {
    setActionMsg('');
    setRrn(row.rrn || '');
    setProviderTxnId(row.provider_txn_id || '');
    setNote('');
    setReason('Provider/bank confirmed failure');
    const res = await adminAPI.getPayoutRecoveryDetail(row.id);
    setSelected(res.success ? res.data : row);
  };

  const refreshAll = async () => {
    await Promise.all([loadStats(), loadList()]);
    if (selected?.id) {
      const res = await adminAPI.getPayoutRecoveryDetail(selected.id);
      if (res.success) setSelected(res.data);
    }
  };

  const handleSuccess = async () => {
    if (!selected?.id) return;
    if (!window.confirm(
      'Confirm this payout was PAID by the bank?\n\nThis will permanently debit the held amount from the user wallet.'
    )) {
      return;
    }
    setActionBusy('success');
    setActionMsg('');
    const res = await adminAPI.markPayoutRecoverySuccess(selected.id, {
      rrn,
      providerTxnId,
      internalNote: note,
    });
    setActionBusy(null);
    if (!res.success) {
      setActionMsg(res.message || 'Could not mark SUCCESS');
      return;
    }
    setActionMsg('Marked SUCCESS — hold settled.');
    setSelected(null);
    await refreshAll();
  };

  const handleFailed = async () => {
    if (!selected?.id) return;
    if (!window.confirm(
      'Confirm this payout was NOT paid?\n\nThis will release the held amount back to the user.'
    )) {
      return;
    }
    setActionBusy('failed');
    setActionMsg('');
    const res = await adminAPI.markPayoutRecoveryFailed(selected.id, {
      reason,
      internalNote: note,
    });
    setActionBusy(null);
    if (!res.success) {
      setActionMsg(res.message || 'Could not mark FAILED');
      return;
    }
    setActionMsg('Marked FAILED — hold released.');
    setSelected(null);
    await refreshAll();
  };

  const totalPages = Math.max(1, Math.ceil(total / 20));
  const helper = useMemo(
    () =>
      onlyStuck
        ? 'Showing PENDING payouts older than 30 minutes (likely missed callback).'
        : 'Showing all PENDING payouts (including fresh ones still waiting on the bank).',
    [onlyStuck]
  );

  return (
    <div className="min-h-[calc(100vh-6rem)] bg-gradient-to-b from-slate-50 dark:from-slate-900 via-white dark:via-slate-900 to-slate-50/80 dark:to-slate-900/80">
      <div className="mx-auto max-w-7xl space-y-6 px-4 py-8 sm:px-6 lg:px-8">
        <header className="rounded-2xl border border-slate-200/80 bg-white p-6 shadow-sm dark:border-slate-700/80 dark:bg-slate-900">
          <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
            <div>
              <p className="text-xs font-semibold uppercase tracking-wide text-amber-700 dark:text-amber-300">
                Ops recovery
              </p>
              <h1 className="mt-1 text-2xl font-bold text-slate-900 dark:text-slate-100 sm:text-3xl">
                Payout recovery
              </h1>
              <p className="mt-2 max-w-2xl text-sm text-slate-600 dark:text-slate-400">
                Pending payouts hold wallet funds until the bank confirms. Use this screen only after
                checking Vidual/bank — then mark Success (settle) or Failed (release).
              </p>
            </div>
            <div className="flex flex-wrap gap-2">
              <Button type="button" variant="outline" icon={FaArrowsRotate} onClick={refreshAll}>
                Refresh
              </Button>
              <Link
                to="/reports/payout"
                className="inline-flex items-center rounded-xl border px-4 py-2.5 text-sm font-semibold text-slate-700 dark:text-slate-200"
              >
                Pay Out report
              </Link>
            </div>
          </div>
        </header>

        <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
          <Card padding="lg" className="border-amber-200/70 dark:border-amber-900/40">
            <div className="flex items-start gap-3">
              <span className="rounded-xl bg-amber-100 p-2.5 text-amber-700 dark:bg-amber-950/50 dark:text-amber-300">
                <FaClock size={18} />
              </span>
              <div>
                <p className="text-xs font-medium uppercase tracking-wide text-slate-500">Pending</p>
                <p className="mt-1 text-2xl font-bold tabular-nums text-slate-900 dark:text-slate-100">
                  {stats?.pending_count ?? '—'}
                </p>
              </div>
            </div>
          </Card>
          <Card padding="lg" className="border-rose-200/70 dark:border-rose-900/40">
            <div className="flex items-start gap-3">
              <span className="rounded-xl bg-rose-100 p-2.5 text-rose-700 dark:bg-rose-950/50 dark:text-rose-300">
                <FaTriangleExclamation size={18} />
              </span>
              <div>
                <p className="text-xs font-medium uppercase tracking-wide text-slate-500">
                  Stuck (&gt;30m)
                </p>
                <p className="mt-1 text-2xl font-bold tabular-nums text-slate-900 dark:text-slate-100">
                  {stats?.stuck_count ?? '—'}
                </p>
              </div>
            </div>
          </Card>
          <Card padding="lg" className="border-sky-200/70 dark:border-sky-900/40">
            <div className="flex items-start gap-3">
              <span className="rounded-xl bg-sky-100 p-2.5 text-sky-700 dark:bg-sky-950/50 dark:text-sky-300">
                <FaWallet size={18} />
              </span>
              <div>
                <p className="text-xs font-medium uppercase tracking-wide text-slate-500">
                  Amount held
                </p>
                <p className="mt-1 text-2xl font-bold tabular-nums text-slate-900 dark:text-slate-100">
                  {stats?.held_amount != null ? formatCurrency(parseFloat(stats.held_amount)) : '—'}
                </p>
              </div>
            </div>
          </Card>
        </div>

        {actionMsg ? (
          <div className="rounded-xl border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-900 dark:border-emerald-900/50 dark:bg-emerald-950/40 dark:text-emerald-200">
            {actionMsg}
          </div>
        ) : null}

        <Card padding="lg">
          <div className="mb-4 flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
            <div className="flex-1">
              <p className="mb-2 text-sm text-slate-600 dark:text-slate-400">{helper}</p>
              <div className="flex flex-col gap-2 sm:flex-row">
                <Input
                  placeholder="Search txn id, phone, user id, RRN…"
                  value={q}
                  onChange={(e) => setQ(e.target.value)}
                />
                <Button
                  type="button"
                  onClick={() => {
                    setPage(1);
                    setAppliedQ(q.trim());
                  }}
                >
                  Search
                </Button>
              </div>
            </div>
            <label className="inline-flex items-center gap-2 text-sm text-slate-700 dark:text-slate-300">
              <input
                type="checkbox"
                checked={onlyStuck}
                onChange={(e) => {
                  setPage(1);
                  setOnlyStuck(e.target.checked);
                }}
                className="rounded border-slate-300"
              />
              Only stuck (&gt;30 min)
            </label>
          </div>

          {loadError ? (
            <p className="text-sm text-rose-600 dark:text-rose-400">{loadError}</p>
          ) : null}
          {loading ? (
            <div className="flex justify-center py-12">
              <LoadingSpinner />
            </div>
          ) : rows.length === 0 ? (
            <div className="rounded-xl border border-dashed border-slate-300 px-4 py-10 text-center dark:border-slate-600">
              <p className="font-medium text-slate-800 dark:text-slate-100">No pending payouts here</p>
              <p className="mt-1 text-sm text-slate-500">
                Fresh transfers stay pending until the bank callback — that is normal.
              </p>
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="min-w-full text-left text-sm">
                <thead className="border-b text-xs uppercase tracking-wide text-slate-500">
                  <tr>
                    <th className="px-3 py-2">Age</th>
                    <th className="px-3 py-2">User</th>
                    <th className="px-3 py-2">Amount</th>
                    <th className="px-3 py-2">Account</th>
                    <th className="px-3 py-2">Reference</th>
                    <th className="px-3 py-2" />
                  </tr>
                </thead>
                <tbody>
                  {rows.map((row) => (
                    <tr
                      key={row.id}
                      className="border-b border-slate-100 dark:border-slate-800 hover:bg-slate-50/80 dark:hover:bg-slate-800/40"
                    >
                      <td className="px-3 py-3">
                        <span
                          className={`inline-flex rounded-full px-2 py-0.5 text-xs font-semibold ${
                            row.is_stuck
                              ? 'bg-rose-100 text-rose-800 dark:bg-rose-950/50 dark:text-rose-300'
                              : 'bg-amber-100 text-amber-800 dark:bg-amber-950/50 dark:text-amber-300'
                          }`}
                        >
                          {row.age_label}
                        </span>
                        <div className="mt-1 text-xs text-slate-500">{formatWhen(row.created_at)}</div>
                      </td>
                      <td className="px-3 py-3">
                        <div className="font-medium text-slate-900 dark:text-slate-100">
                          {row.user?.name || '—'}
                        </div>
                        <div className="text-xs text-slate-500">
                          {row.user?.user_id} · {row.user?.phone}
                        </div>
                      </td>
                      <td className="px-3 py-3 tabular-nums">
                        <div className="font-semibold">{formatCurrency(parseFloat(row.amount))}</div>
                        <div className="text-xs text-slate-500">
                          Hold {formatCurrency(parseFloat(row.total_deducted))}
                        </div>
                      </td>
                      <td className="px-3 py-3">
                        <div>{row.bank_account?.bank_name}</div>
                        <div className="text-xs text-slate-500">
                          {row.bank_account?.account_masked} · {row.bank_account?.ifsc}
                        </div>
                      </td>
                      <td className="px-3 py-3">
                        <code className="text-xs">{row.transaction_id}</code>
                        {row.provider_txn_id ? (
                          <div className="text-xs text-slate-500">Prov {row.provider_txn_id}</div>
                        ) : null}
                      </td>
                      <td className="px-3 py-3 text-right">
                        <Button type="button" size="sm" variant="outline" onClick={() => openDetail(row)}>
                          Review
                        </Button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          {totalPages > 1 ? (
            <div className="mt-4 flex items-center justify-between text-sm">
              <span className="text-slate-500">
                Page {page} / {totalPages} · {total} total
              </span>
              <div className="flex gap-2">
                <Button
                  type="button"
                  size="sm"
                  variant="outline"
                  disabled={page <= 1}
                  onClick={() => setPage((p) => Math.max(1, p - 1))}
                >
                  Prev
                </Button>
                <Button
                  type="button"
                  size="sm"
                  variant="outline"
                  disabled={page >= totalPages}
                  onClick={() => setPage((p) => p + 1)}
                >
                  Next
                </Button>
              </div>
            </div>
          ) : null}
        </Card>
      </div>

      {selected ? (
        <div className="fixed inset-0 z-50 flex items-end justify-center bg-black/50 p-4 sm:items-center">
          <div className="max-h-[92vh] w-full max-w-lg overflow-y-auto rounded-2xl border border-slate-200 bg-white shadow-xl dark:border-slate-700 dark:bg-slate-900">
            <div className="border-b px-5 py-4 dark:border-slate-700">
              <h2 className="text-lg font-bold text-slate-900 dark:text-slate-100">Review payout</h2>
              <p className="mt-1 text-sm text-slate-500">
                Confirm with Vidual/bank first. Wrong action can debit or unlock money incorrectly.
              </p>
            </div>
            <div className="space-y-4 px-5 py-4 text-sm">
              <div className="rounded-xl bg-slate-50 p-3 dark:bg-slate-800/60">
                <div className="font-semibold text-slate-900 dark:text-slate-100">
                  {formatCurrency(parseFloat(selected.amount))} · {selected.transfer_mode}
                </div>
                <div className="mt-1 text-slate-600 dark:text-slate-300">
                  {selected.user?.name} ({selected.user?.user_id})
                </div>
                <div className="mt-1 text-xs text-slate-500">
                  {selected.bank_account?.bank_name} · {selected.bank_account?.account_masked} ·{' '}
                  {selected.bank_account?.ifsc}
                </div>
                <div className="mt-2 break-all font-mono text-xs">{selected.transaction_id}</div>
                <div className="mt-1 text-xs text-slate-500">
                  Age {selected.age_label} · Created {formatWhen(selected.created_at)}
                </div>
              </div>

              <Input
                label="RRN / UTR (for SUCCESS)"
                value={rrn}
                onChange={(e) => setRrn(e.target.value)}
                placeholder="Bank reference if available"
              />
              <Input
                label="Provider txn id (optional)"
                value={providerTxnId}
                onChange={(e) => setProviderTxnId(e.target.value)}
              />
              <Input
                label="Internal note (required)"
                value={note}
                onChange={(e) => setNote(e.target.value)}
                placeholder="e.g. Confirmed SUCCESS on Vidual at 5:40pm"
              />
              <Input
                label="Failure reason (for FAILED)"
                value={reason}
                onChange={(e) => setReason(e.target.value)}
              />

              {actionMsg && selected ? (
                <p className="text-sm text-rose-600 dark:text-rose-400">{actionMsg}</p>
              ) : null}

              <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
                <Button
                  type="button"
                  variant="primary"
                  icon={FaCircleCheck}
                  loading={actionBusy === 'success'}
                  disabled={Boolean(actionBusy) || selected.status !== 'PENDING'}
                  onClick={handleSuccess}
                >
                  Mark paid (SUCCESS)
                </Button>
                <Button
                  type="button"
                  variant="danger"
                  icon={FaCircleXmark}
                  loading={actionBusy === 'failed'}
                  disabled={Boolean(actionBusy) || selected.status !== 'PENDING'}
                  onClick={handleFailed}
                >
                  Mark failed (release)
                </Button>
              </div>
              <Button
                type="button"
                variant="outline"
                fullWidth
                disabled={Boolean(actionBusy)}
                onClick={() => setSelected(null)}
              >
                Cancel
              </Button>
            </div>
          </div>
        </div>
      ) : null}
    </div>
  );
};

export default PayoutRecovery;
