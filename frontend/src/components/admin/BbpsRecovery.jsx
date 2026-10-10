import React, { useCallback, useEffect, useState } from 'react';
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
  FaMagnifyingGlass,
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

function ageLabel(iso) {
  if (!iso) return '—';
  const ms = Date.now() - new Date(iso).getTime();
  if (!Number.isFinite(ms) || ms < 0) return 'just now';
  const mins = Math.floor(ms / 60000);
  if (mins < 60) return `${mins}m`;
  const hours = Math.floor(mins / 60);
  if (hours < 48) return `${hours}h`;
  return `${Math.floor(hours / 24)}d`;
}

function statusClass(status) {
  const s = String(status || '').toUpperCase();
  if (s === 'SUCCESS') return 'bg-emerald-100 text-emerald-800 dark:bg-emerald-950/50 dark:text-emerald-300';
  if (s === 'FAILED' || s === 'FAILURE') return 'bg-rose-100 text-rose-800 dark:bg-rose-950/50 dark:text-rose-300';
  return 'bg-amber-100 text-amber-800 dark:bg-amber-950/50 dark:text-amber-300';
}

const BbpsRecovery = () => {
  const [stats, setStats] = useState(null);
  const [rows, setRows] = useState([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [q, setQ] = useState('');
  const [appliedQ, setAppliedQ] = useState('');
  const [loading, setLoading] = useState(false);
  const [loadError, setLoadError] = useState('');
  const [selected, setSelected] = useState(null);
  const [note, setNote] = useState('');
  const [reason, setReason] = useState('BillAvenue confirmed failure');
  const [complaintDesc, setComplaintDesc] = useState('');
  const [actionBusy, setActionBusy] = useState('');
  const [actionMsg, setActionMsg] = useState('');
  const [actionTone, setActionTone] = useState('ok');

  const loadStats = useCallback(async () => {
    const res = await adminAPI.getBbpsRecoveryStats();
    if (res.success) setStats(res.data);
  }, []);

  const loadList = useCallback(async () => {
    setLoading(true);
    setLoadError('');
    const res = await adminAPI.listBbpsRecovery({
      page,
      page_size: 20,
      q: appliedQ || undefined,
    });
    setLoading(false);
    if (!res.success) {
      setRows([]);
      setTotal(0);
      setLoadError(res.message || 'Could not load BBPS payments');
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

  const refreshAll = async () => {
    await Promise.all([loadStats(), loadList()]);
    if (selected?.id) {
      const res = await adminAPI.getBbpsRecoveryDetail(selected.id);
      if (res.success) setSelected(res.data);
    }
  };

  const openDetail = async (row) => {
    setActionMsg('');
    setNote('');
    setReason('BillAvenue confirmed failure');
    setComplaintDesc('');
    const res = await adminAPI.getBbpsRecoveryDetail(row.id);
    setSelected(res.success ? res.data : row);
  };

  const run = async (key, fn) => {
    if (!selected?.id) return;
    setActionBusy(key);
    setActionMsg('');
    const res = await fn();
    setActionBusy('');
    if (!res.success) {
      setActionTone('bad');
      setActionMsg(res.message || 'Request failed');
      return;
    }
    setActionTone('ok');
    setActionMsg(res.message || 'Done');
    if (res.data?.payment) setSelected(res.data.payment);
    else if (res.data && res.data.id && res.data.service_id) setSelected(res.data);
    await refreshAll();
  };

  const totalPages = Math.max(1, Math.ceil(total / 20));
  const inFlight = String(selected?.status || '').toUpperCase() === 'PENDING'
    || ['PAY_INITIATED', 'AWAITED'].includes(String(selected?.attempt_status || '').toUpperCase());

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
                BBPS recovery
              </h1>
              <p className="mt-2 max-w-2xl text-sm text-slate-600 dark:text-slate-400">
                A bill payment stays here only while BillAvenue has not given a final result.
                The wallet reserve stays with it. Check status asks BillAvenue. Mark success or
                failed only after you have confirmed the result.
              </p>
            </div>
            <div className="flex flex-wrap gap-2">
              <Button type="button" variant="outline" icon={FaArrowsRotate} onClick={refreshAll} loading={loading}>
                Refresh
              </Button>
              <Link
                to="/reports/bbps"
                className="inline-flex items-center rounded-lg border-2 border-slate-200 px-4 py-2.5 text-sm font-semibold text-slate-700 dark:border-slate-600 dark:text-slate-200"
              >
                BBPS report
              </Link>
              <Link
                to="/admin/payout-recovery"
                className="inline-flex items-center rounded-lg border-2 border-slate-200 px-4 py-2.5 text-sm font-semibold text-slate-700 dark:border-slate-600 dark:text-slate-200"
              >
                Payout recovery
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
                <p className="text-xs font-medium uppercase tracking-wide text-slate-500">In flight</p>
                <p className="mt-1 text-2xl font-bold tabular-nums text-slate-900 dark:text-slate-100">
                  {stats?.stuck ?? '—'}
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
                <p className="text-xs font-medium uppercase tracking-wide text-slate-500">Reserved</p>
                <p className="mt-1 text-2xl font-bold tabular-nums text-slate-900 dark:text-slate-100">
                  {stats?.held_amount != null ? formatCurrency(parseFloat(stats.held_amount)) : '—'}
                </p>
              </div>
            </div>
          </Card>
          <Card padding="lg" className="border-slate-200/70 dark:border-slate-700">
            <div className="flex items-start gap-3">
              <span className="rounded-xl bg-slate-100 p-2.5 text-slate-700 dark:bg-slate-800 dark:text-slate-200">
                <FaMagnifyingGlass size={18} />
              </span>
              <div>
                <p className="text-xs font-medium uppercase tracking-wide text-slate-500">Oldest waiting</p>
                <p className="mt-1 text-2xl font-bold tabular-nums text-slate-900 dark:text-slate-100">
                  {stats?.oldest_created_at ? ageLabel(stats.oldest_created_at) : 'None'}
                </p>
              </div>
            </div>
          </Card>
        </div>

        <Card padding="lg">
          <form
            className="mb-4 flex flex-col gap-2 sm:flex-row"
            onSubmit={(e) => {
              e.preventDefault();
              setPage(1);
              setAppliedQ(q.trim());
            }}
          >
            <Input
              value={q}
              onChange={(e) => setQ(e.target.value)}
              placeholder="Service id, request id, B-Connect, retailer code, mobile"
            />
            <Button type="submit">Search</Button>
          </form>
          <p className="mb-4 text-sm text-slate-600 dark:text-slate-400">
            Completed payments are on the BBPS report. This list is only Pay initiated, Awaited, and Pending.
          </p>
          {loadError ? <p className="text-sm text-rose-600 dark:text-rose-400">{loadError}</p> : null}
          {loading ? (
            <div className="flex justify-center py-12">
              <LoadingSpinner />
            </div>
          ) : rows.length === 0 ? (
            <div className="rounded-xl border border-dashed border-slate-300 px-4 py-10 text-center dark:border-slate-600">
              <p className="font-medium text-slate-800 dark:text-slate-100">No payments are waiting on BillAvenue</p>
              <p className="mx-auto mt-1 max-w-lg text-sm text-slate-500">
                Success and failed bills stay on the report. A new payment appears here only if BillAvenue
                has not confirmed it yet. Use Refresh after a status check.
              </p>
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="min-w-full text-left text-sm">
                <thead className="border-b text-xs uppercase tracking-wide text-slate-500">
                  <tr>
                    <th className="px-3 py-2">Age</th>
                    <th className="px-3 py-2">Retailer</th>
                    <th className="px-3 py-2">Amount</th>
                    <th className="px-3 py-2">Biller</th>
                    <th className="px-3 py-2">Reference</th>
                    <th className="px-3 py-2">Status</th>
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
                        <span className="inline-flex rounded-full bg-amber-100 px-2 py-0.5 text-xs font-semibold text-amber-800 dark:bg-amber-950/50 dark:text-amber-300">
                          {ageLabel(row.created_at)}
                        </span>
                        <div className="mt-1 text-xs text-slate-500">{formatWhen(row.created_at)}</div>
                      </td>
                      <td className="px-3 py-3">
                        <div className="font-medium text-slate-900 dark:text-slate-100">{row.retailer_code || '—'}</div>
                        <div className="text-xs text-slate-500">{row.retailer_phone || '—'}</div>
                      </td>
                      <td className="px-3 py-3 tabular-nums">
                        <div className="font-semibold">{formatCurrency(parseFloat(row.amount || 0))}</div>
                        <div className="text-xs text-slate-500">
                          Hold {formatCurrency(parseFloat(row.wallet_hold_amount || 0))}
                        </div>
                      </td>
                      <td className="px-3 py-3">
                        <div>{row.biller || '—'}</div>
                        <div className="text-xs text-slate-500">{row.biller_id || ''}</div>
                      </td>
                      <td className="px-3 py-3">
                        <code className="text-xs">{row.txn_ref_id || 'No B-Connect id yet'}</code>
                        <div className="text-xs text-slate-500">{row.service_id}</div>
                      </td>
                      <td className="px-3 py-3">
                        <span className={`inline-flex rounded-full px-2 py-0.5 text-xs font-semibold ${statusClass(row.status)}`}>
                          {row.status || row.attempt_status}
                        </span>
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
                Page {page} / {totalPages} · {total} waiting
              </span>
              <div className="flex gap-2">
                <Button type="button" size="sm" variant="outline" disabled={page <= 1} onClick={() => setPage((p) => Math.max(1, p - 1))}>
                  Prev
                </Button>
                <Button type="button" size="sm" variant="outline" disabled={page >= totalPages} onClick={() => setPage((p) => p + 1)}>
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
              <h2 className="text-lg font-bold text-slate-900 dark:text-slate-100">Review bill payment</h2>
              <p className="mt-1 text-sm text-slate-500">
                Check status asks BillAvenue and applies the result once. Mark success or failed only when you already know the outcome.
              </p>
            </div>
            <div className="space-y-4 px-5 py-4 text-sm">
              <div className="rounded-xl bg-slate-50 p-3 dark:bg-slate-800/60">
                <div className="flex items-center justify-between gap-2">
                  <div className="font-semibold text-slate-900 dark:text-slate-100">
                    {formatCurrency(parseFloat(selected.amount || 0))} · {selected.biller || 'Biller'}
                  </div>
                  <span className={`inline-flex rounded-full px-2 py-0.5 text-xs font-semibold ${statusClass(selected.status)}`}>
                    {selected.status}
                  </span>
                </div>
                <div className="mt-1 text-slate-600 dark:text-slate-300">
                  {selected.retailer_code || '—'} · {selected.retailer_phone || '—'}
                </div>
                <div className="mt-2 break-all font-mono text-xs">{selected.txn_ref_id || 'B-Connect id not assigned yet'}</div>
                <div className="mt-1 break-all text-xs text-slate-500">{selected.service_id}</div>
                <div className="mt-1 text-xs text-slate-500">
                  Attempt {selected.attempt_status} · Created {formatWhen(selected.created_at)}
                </div>
                <div className="mt-1 text-xs text-slate-500">
                  Last status check {formatWhen(selected.last_status_checked_at)} · Hold {formatCurrency(parseFloat(selected.wallet_hold_amount || 0))}
                </div>
              </div>

              {actionMsg ? (
                <p className={`text-sm ${actionTone === 'bad' ? 'text-rose-600 dark:text-rose-400' : 'text-emerald-700 dark:text-emerald-300'}`}>
                  {actionMsg}
                </p>
              ) : null}

              <Button
                type="button"
                variant="outline"
                icon={FaArrowsRotate}
                fullWidth
                loading={actionBusy === 'check'}
                disabled={Boolean(actionBusy)}
                onClick={() => run('check', () => adminAPI.checkBbpsRecoveryStatus(selected.id))}
              >
                Check status with BillAvenue
              </Button>

              <Input
                label="Internal note"
                value={note}
                onChange={(e) => setNote(e.target.value)}
                placeholder="Why you are marking this, and what BillAvenue showed"
              />
              <Input
                label="Failure reason"
                value={reason}
                onChange={(e) => setReason(e.target.value)}
              />

              <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
                <Button
                  type="button"
                  variant="success"
                  icon={FaCircleCheck}
                  loading={actionBusy === 'ok'}
                  disabled={Boolean(actionBusy) || !inFlight}
                  onClick={() => {
                    if (!window.confirm('Mark this payment successful and settle the reserve once?')) return;
                    run('ok', () => adminAPI.markBbpsRecoverySuccess(selected.id, { internalNote: note }));
                  }}
                >
                  Mark success
                </Button>
                <Button
                  type="button"
                  variant="danger"
                  icon={FaCircleXmark}
                  loading={actionBusy === 'bad'}
                  disabled={Boolean(actionBusy) || !inFlight}
                  onClick={() => {
                    if (!window.confirm('Mark this payment failed and release the reserve once?')) return;
                    run('bad', () => adminAPI.markBbpsRecoveryFailed(selected.id, { reason, internalNote: note }));
                  }}
                >
                  Mark failed
                </Button>
              </div>

              <div className="border-t pt-4 dark:border-slate-700">
                <p className="mb-2 text-xs text-slate-500">
                  A complaint is filed on the retailer’s payment. It needs a B-Connect id.
                </p>
                <Input
                  label="Complaint description"
                  value={complaintDesc}
                  onChange={(e) => setComplaintDesc(e.target.value)}
                  placeholder="What the retailer reported"
                />
                <div className="mt-2">
                  <Button
                    type="button"
                    variant="secondary"
                    fullWidth
                    disabled={Boolean(actionBusy) || !selected.txn_ref_id}
                    loading={actionBusy === 'cmp'}
                    onClick={() =>
                      run('cmp', () =>
                        adminAPI.raiseBbpsRecoveryComplaint(selected.id, {
                          complaintDesc,
                          complaintDisposition: 'Transaction Successful, Amount Debited but services not received',
                        })
                      )
                    }
                  >
                    Raise complaint for retailer
                  </Button>
                </div>
              </div>

              <Button type="button" variant="ghost" fullWidth onClick={() => setSelected(null)}>
                Close
              </Button>
            </div>
          </div>
        </div>
      ) : null}
    </div>
  );
};

export default BbpsRecovery;
