import React, { useCallback, useEffect, useState } from 'react';
import { adminAPI } from '../../services/api';
import Card from '../common/Card';
import Input from '../common/Input';
import Button from '../common/Button';
import LoadingSpinner from '../common/LoadingSpinner';
import { formatCurrency } from '../../utils/formatters';
import { FaCircleCheck, FaCircleXmark, FaXmark } from 'react-icons/fa6';

function formatWhen(iso) {
  if (!iso) return '—';
  try {
    return new Date(iso).toLocaleString('en-IN');
  } catch {
    return iso;
  }
}

function money(value) {
  const n = parseFloat(value);
  if (Number.isNaN(n)) return '—';
  return formatCurrency(n);
}

const PayInRecovery = () => {
  const [stats, setStats] = useState(null);
  const [rows, setRows] = useState([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [q, setQ] = useState('');
  const [appliedQ, setAppliedQ] = useState('');
  const [loading, setLoading] = useState(false);
  const [loadError, setLoadError] = useState('');
  const [selected, setSelected] = useState(null);
  const [utr, setUtr] = useState('');
  const [reason, setReason] = useState('Payment was not completed');
  const [note, setNote] = useState('');
  const [actionBusy, setActionBusy] = useState('');
  const [actionMsg, setActionMsg] = useState('');

  const loadStats = useCallback(async () => {
    const res = await adminAPI.getPayinRecoveryStats();
    if (res.success) setStats(res.data);
  }, []);

  const loadList = useCallback(async () => {
    setLoading(true);
    setLoadError('');
    const res = await adminAPI.listPayinRecovery({
      page,
      page_size: 20,
      q: appliedQ || undefined,
    });
    setLoading(false);
    if (!res.success) {
      setRows([]);
      setTotal(0);
      setLoadError(res.message || 'Could not load pay-ins');
      return;
    }
    setRows(res.data?.results || []);
    setTotal(res.data?.total || 0);
  }, [page, appliedQ]);

  useEffect(() => {
    loadStats();
  }, [loadStats]);

  useEffect(() => {
    loadList();
  }, [loadList]);

  const openDetail = async (row) => {
    setActionMsg('');
    setUtr(row.utr || row.gateway_transaction_id || '');
    setReason('Payment was not completed');
    setNote('');
    const res = await adminAPI.getPayinRecoveryDetail(row.id);
    setSelected(res.success ? res.data : row);
  };

  const refreshAll = async () => {
    await Promise.all([loadStats(), loadList()]);
    if (selected?.id) {
      const res = await adminAPI.getPayinRecoveryDetail(selected.id);
      if (res.success) setSelected(res.data);
    }
  };

  const run = async (key, action, confirmText) => {
    if (!selected?.id) return;
    if (confirmText && !window.confirm(confirmText)) return;
    setActionBusy(key);
    setActionMsg('');
    const res = await action();
    setActionBusy('');
    if (!res.success) {
      setActionMsg(res.message || 'Could not update this pay-in');
      return;
    }
    setActionMsg(res.message || 'Updated');
    setSelected(res.data || null);
    await refreshAll();
  };

  const gap = (value) => {
    const n = parseFloat(value);
    return !Number.isNaN(n) && n !== 0;
  };

  const totalPages = Math.max(1, Math.ceil(total / 20));

  return (
    <div className="mx-auto max-w-7xl space-y-6 px-4 py-8">
      <header>
        <p className="text-xs font-semibold uppercase tracking-wide text-amber-700">Ops recovery</p>
        <h1 className="text-2xl font-bold text-slate-900 dark:text-slate-100">Pay-in recovery</h1>
        <p className="mt-1 text-sm text-slate-600 dark:text-slate-400">
          Open pending gateway and QR pay-ins, or search a receipt such as a transaction id.
          A fee correction changes only that one wallet.
        </p>
      </header>

      <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
        <Card padding="md">
          <div className="text-xs text-slate-500">Pending gateway</div>
          <div className="text-2xl font-bold">{stats?.pending_count ?? '—'}</div>
        </Card>
        <Card padding="md">
          <div className="text-xs text-slate-500">QR waiting for review</div>
          <div className="text-2xl font-bold">{stats?.review_count ?? '—'}</div>
        </Card>
        <Card padding="md">
          <div className="text-xs text-slate-500">Open together</div>
          <div className="text-2xl font-bold">{stats?.open_count ?? '—'}</div>
        </Card>
      </div>

      <Card padding="md">
        <form
          className="flex flex-col gap-2 sm:flex-row"
          onSubmit={(e) => {
            e.preventDefault();
            setPage(1);
            setAppliedQ(q.trim());
          }}
        >
          <Input
            value={q}
            onChange={(e) => setQ(e.target.value)}
            placeholder="Transaction id, UTR, phone, or user id"
          />
          <Button type="submit">Search</Button>
          {appliedQ && (
            <Button
              type="button"
              variant="outline"
              onClick={() => {
                setQ('');
                setAppliedQ('');
                setPage(1);
              }}
            >
              Clear
            </Button>
          )}
        </form>
        <p className="mt-2 text-xs text-slate-500">
          {appliedQ
            ? `Showing matches for “${appliedQ}”.`
            : 'Showing open pay-ins, plus settled pay-ins from the last 14 days whose credit does not match the quote.'}
        </p>
      </Card>

      {loadError && <p className="text-sm text-red-700">{loadError}</p>}
      {loading ? (
        <div className="flex justify-center py-10"><LoadingSpinner /></div>
      ) : (
        <div className="overflow-x-auto rounded-xl border border-slate-200 bg-white dark:border-slate-700 dark:bg-slate-900">
          <table className="min-w-full text-sm">
            <thead className="bg-slate-50 text-left text-xs uppercase text-slate-500 dark:bg-slate-800">
              <tr>
                <th className="p-3">Transaction</th>
                <th className="p-3">Status</th>
                <th className="p-3">Gross</th>
                <th className="p-3">Credited</th>
                <th className="p-3">Rail</th>
                <th className="p-3" />
              </tr>
            </thead>
            <tbody>
              {rows.length === 0 && (
                <tr><td className="p-4 text-slate-500" colSpan={6}>No pay-ins in this list.</td></tr>
              )}
              {rows.map((row) => (
                <tr key={row.id} className="border-t border-slate-100 dark:border-slate-800">
                  <td className="p-3">
                    <div className="font-medium">{row.transaction_id}</div>
                    <div className="text-xs text-slate-500">
                      {[row.user_name, row.user_id].filter(Boolean).join(' · ')} · {formatWhen(row.created_at)}
                    </div>
                  </td>
                  <td className="p-3">{row.status}</td>
                  <td className="p-3">{money(row.gross)}</td>
                  <td className="p-3">{money(row.credited_net)}</td>
                  <td className="p-3">{row.qr_name || row.gateway_name || row.collection_rail}</td>
                  <td className="p-3 text-right">
                    <Button type="button" size="sm" variant="outline" onClick={() => openDetail(row)}>Open</Button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          <div className="flex items-center justify-between p-3 text-sm">
            <span>Page {page} of {totalPages} ({total})</span>
            <div className="flex gap-2">
              <Button type="button" size="sm" variant="outline" disabled={page <= 1} onClick={() => setPage((p) => p - 1)}>Previous</Button>
              <Button type="button" size="sm" variant="outline" disabled={page >= totalPages} onClick={() => setPage((p) => p + 1)}>Next</Button>
            </div>
          </div>
        </div>
      )}

      {selected && (
        <div
          className="fixed inset-0 z-50 flex items-end justify-center bg-black/50 p-4 sm:items-center"
          onClick={() => { if (!actionBusy) setSelected(null); }}
        >
          <div
            role="dialog"
            aria-modal="true"
            aria-labelledby="payin-recovery-title"
            className="max-h-[92vh] w-full max-w-lg overflow-y-auto rounded-2xl border border-slate-200 bg-white shadow-xl dark:border-slate-700 dark:bg-slate-900"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-start justify-between gap-3 border-b px-5 py-4 dark:border-slate-700">
              <div>
                <p className="text-xs font-semibold uppercase tracking-wide text-amber-700 dark:text-amber-300">Review pay-in</p>
                <h2 id="payin-recovery-title" className="mt-1 break-all text-lg font-bold text-slate-900 dark:text-slate-100">
                  {selected.transaction_id}
                </h2>
              </div>
              <button
                type="button"
                className="rounded-lg p-2 text-slate-500 hover:bg-slate-100 dark:hover:bg-slate-800"
                aria-label="Close"
                disabled={Boolean(actionBusy)}
                onClick={() => setSelected(null)}
              >
                <FaXmark />
              </button>
            </div>
            <div className="space-y-4 px-5 py-4 text-sm">
              <div className="rounded-xl bg-slate-50 p-3 dark:bg-slate-800/60">
                <div className="flex items-center justify-between gap-2">
                  <span className="text-xs font-semibold uppercase tracking-wide text-slate-500">{selected.status}</span>
                  <span className="font-semibold text-slate-900 dark:text-slate-100">
                    {selected.qr_name || selected.gateway_name || selected.collection_rail || '—'}
                  </span>
                </div>
                <div className="mt-2 font-medium text-slate-900 dark:text-slate-100">
                  {[selected.user_name, selected.user_id].filter(Boolean).join(' · ') || '—'}
                </div>
                <div className="text-xs text-slate-500">
                  {[selected.user_phone, selected.user_email].filter(Boolean).join(' · ') || '—'}
                </div>
                <div className="mt-2 text-xs text-slate-500">
                  {selected.package_name || 'No package'} · {formatWhen(selected.created_at)}
                </div>
              </div>

              <dl className="grid grid-cols-2 gap-3">
                <div>
                  <dt className="text-xs text-slate-500">Gross</dt>
                  <dd className="font-semibold text-slate-900 dark:text-slate-100">{money(selected.gross)}</dd>
                </div>
                <div>
                  <dt className="text-xs text-slate-500">Service charge</dt>
                  <dd className="font-semibold text-slate-900 dark:text-slate-100">{money(selected.charge)}</dd>
                </div>
                <div>
                  <dt className="text-xs text-slate-500">Quote saved on the order</dt>
                  <dd className="font-semibold text-slate-900 dark:text-slate-100">{selected.locked_net ? money(selected.locked_net) : '—'}</dd>
                </div>
                <div>
                  <dt className="text-xs text-slate-500">{selected.status === 'SUCCESS' ? 'Wallet credited' : 'Not credited yet'}</dt>
                  <dd className="font-semibold text-slate-900 dark:text-slate-100">{money(selected.credited_net)}</dd>
                </div>
                {selected.status === 'SUCCESS' && (
                  <div className="col-span-2">
                    <dt className="text-xs text-slate-500">Package rate</dt>
                    <dd className="font-semibold text-slate-900 dark:text-slate-100">
                      {selected.package_rate_net ? money(selected.package_rate_net) : '—'}
                    </dd>
                  </div>
                )}
                <div>
                  <dt className="text-xs text-slate-500">UTR</dt>
                  <dd className="break-all font-semibold text-slate-900 dark:text-slate-100">{selected.utr || '—'}</dd>
                </div>
                <div>
                  <dt className="text-xs text-slate-500">Gateway reference</dt>
                  <dd className="break-all font-semibold text-slate-900 dark:text-slate-100">{selected.gateway_transaction_id || '—'}</dd>
                </div>
              </dl>

              {selected.failure_reason && (
                <p className="rounded-lg bg-rose-50 px-3 py-2 text-sm text-rose-800 dark:bg-rose-950/40 dark:text-rose-200">
                  {selected.failure_reason}
                </p>
              )}
              {selected.adjustment_applied && (
                <p className="text-sm text-emerald-800 dark:text-emerald-300">This pay-in already has a one-time wallet correction.</p>
              )}
              {actionMsg && <p className="text-sm text-slate-700 dark:text-slate-200">{actionMsg}</p>}

              {selected.status !== 'SUCCESS' && selected.status !== 'FAILED' && (
                <div className="space-y-3">
                  <Input label="UTR / bank reference" value={utr} onChange={(e) => setUtr(e.target.value)} placeholder="Bank reference, if the payment reached the bank" />
                  <Input label="Internal note" value={note} onChange={(e) => setNote(e.target.value)} placeholder="What you checked before updating this pay-in" />
                  <Input label="Failure reason" value={reason} onChange={(e) => setReason(e.target.value)} />
                  <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
                    <Button
                      type="button"
                      icon={FaCircleCheck}
                      loading={actionBusy === 'ok'}
                      disabled={Boolean(actionBusy)}
                      onClick={() => run(
                        'ok',
                        () => adminAPI.markPayinRecoverySuccess(selected.id, { utr, internalNote: note }),
                        `Credit ${money(selected.locked_net || selected.credited_net)} to this wallet?`,
                      )}
                    >
                      Mark successful
                    </Button>
                    <Button
                      type="button"
                      variant="danger"
                      icon={FaCircleXmark}
                      loading={actionBusy === 'bad'}
                      disabled={Boolean(actionBusy)}
                      onClick={() => run(
                        'bad',
                        () => adminAPI.markPayinRecoveryFailed(selected.id, { reason, internalNote: note }),
                        'Mark this pay-in failed? Nothing will be credited.',
                      )}
                    >
                      Mark failed
                    </Button>
                  </div>
                </div>
              )}

              {selected.status === 'SUCCESS' && !selected.adjustment_applied && (gap(selected.locked_gap) || gap(selected.package_rate_gap)) && (
                <div className="space-y-2">
                  <p className="text-xs text-slate-500">
                    This moves only this user&apos;s main wallet. Commission already paid to uplines stays as recorded.
                  </p>
                  <div className="grid grid-cols-1 gap-2">
                    {gap(selected.locked_gap) && (
                      <Button
                        type="button"
                        loading={actionBusy === 'locked'}
                        disabled={Boolean(actionBusy)}
                        onClick={() => run(
                          'locked',
                          () => adminAPI.adjustPayinRecovery(selected.id, 'locked'),
                          `Adjust this wallet to the locked quote of ${money(selected.locked_net)}?`,
                        )}
                      >
                        Match locked quote ({money(selected.locked_net)})
                      </Button>
                    )}
                    {gap(selected.package_rate_gap) && (
                      <Button
                        type="button"
                        variant="outline"
                        loading={actionBusy === 'package'}
                        disabled={Boolean(actionBusy)}
                        onClick={() => run(
                          'package',
                          () => adminAPI.adjustPayinRecovery(selected.id, 'package_rate'),
                          `Adjust this wallet to the package rate of ${money(selected.package_rate_net)}?`,
                        )}
                      >
                        Match package rate ({money(selected.package_rate_net)})
                      </Button>
                    )}
                  </div>
                </div>
              )}

              <Button type="button" variant="outline" fullWidth disabled={Boolean(actionBusy)} onClick={() => setSelected(null)}>
                Close
              </Button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default PayInRecovery;
