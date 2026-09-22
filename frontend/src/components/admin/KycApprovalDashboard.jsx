import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import {
  FaBan,
  FaCircleCheck,
  FaClock,
  FaIdCard,
  FaArrowsRotate,
  FaEye,
} from 'react-icons/fa6';
import { usersAPI } from '../../services/api';
import { formatUserId } from '../../utils/formatters';
import Button from '../common/Button';
import Card from '../common/Card';
import LoadingSpinner from '../common/LoadingSpinner';

const TABS = [
  { id: 'awaiting_approval', label: 'Awaiting approval', tone: 'amber' },
  { id: 'rejected', label: 'Rejected', tone: 'red' },
  { id: 'pending', label: 'In progress', tone: 'slate' },
  { id: 'verified', label: 'Verified', tone: 'emerald' },
];

function formatWhen(iso) {
  if (!iso) return '—';
  try {
    return new Date(iso).toLocaleString('en-IN');
  } catch {
    return iso;
  }
}

function statusBadge(status) {
  const map = {
    awaiting_approval: 'bg-amber-100 text-amber-900 ring-amber-200 dark:bg-amber-950/50 dark:text-amber-200 dark:ring-amber-800',
    rejected: 'bg-red-100 text-red-900 ring-red-200 dark:bg-red-950/50 dark:text-red-200 dark:ring-red-800',
    pending: 'bg-slate-100 text-slate-800 ring-slate-200 dark:bg-slate-800 dark:text-slate-200 dark:ring-slate-700',
    verified: 'bg-emerald-100 text-emerald-900 ring-emerald-200 dark:bg-emerald-950/50 dark:text-emerald-200 dark:ring-emerald-800',
  };
  const labels = {
    awaiting_approval: 'Awaiting approval',
    rejected: 'Rejected',
    pending: 'Pending',
    verified: 'Verified',
  };
  return (
    <span className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-semibold ring-1 ${map[status] || map.pending}`}>
      {labels[status] || status}
    </span>
  );
}

const KycApprovalDashboard = () => {
  const [tab, setTab] = useState('awaiting_approval');
  const [search, setSearch] = useState('');
  const [appliedSearch, setAppliedSearch] = useState('');
  const [page, setPage] = useState(1);
  const [rows, setRows] = useState([]);
  const [total, setTotal] = useState(0);
  const [stats, setStats] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [actionUserId, setActionUserId] = useState(null);
  const [rejectFor, setRejectFor] = useState(null);
  const [rejectNotes, setRejectNotes] = useState('');
  const [banner, setBanner] = useState('');

  const pageSize = 20;

  const loadStats = useCallback(async () => {
    const res = await usersAPI.getUserStats();
    if (res.success) setStats(res.data);
  }, []);

  const loadList = useCallback(async () => {
    setLoading(true);
    setError('');
    const res = await usersAPI.listUsers({
      kyc_status: tab,
      search: appliedSearch || undefined,
      page,
      page_size: pageSize,
    });
    setLoading(false);
    if (!res.success) {
      setError(res.message || 'Failed to load KYC queue.');
      setRows([]);
      setTotal(0);
      return;
    }
    setRows(res.data?.users || []);
    setTotal(Number(res.data?.total) || 0);
  }, [tab, appliedSearch, page]);

  useEffect(() => {
    loadStats();
  }, [loadStats]);

  useEffect(() => {
    loadList();
  }, [loadList]);

  const counts = useMemo(
    () => ({
      awaiting_approval: stats?.kyc_awaiting_approval ?? null,
      rejected: stats?.kyc_rejected ?? null,
      pending: stats?.kyc_pending ?? null,
      verified: stats?.kyc_verified ?? null,
    }),
    [stats]
  );

  const totalPages = Math.max(1, Math.ceil(total / pageSize));

  const runDecision = async (userId, decision, notes = '') => {
    setActionUserId(userId);
    setBanner('');
    try {
      const res = await usersAPI.decideKycApproval(userId, decision, notes);
      if (!res.success) {
        setBanner(res.message || 'Action failed.');
        return;
      }
      setBanner(res.message || 'Updated.');
      setRejectFor(null);
      setRejectNotes('');
      await Promise.all([loadList(), loadStats()]);
    } catch {
      setBanner('Action failed. Please try again.');
    } finally {
      setActionUserId(null);
    }
  };

  const applySearch = (e) => {
    e?.preventDefault?.();
    setPage(1);
    setAppliedSearch(search.trim());
  };

  return (
    <div className="mx-auto max-w-6xl space-y-6">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <h1 className="text-2xl font-bold text-slate-900 dark:text-slate-100">KYC Approvals</h1>
          <p className="mt-1 text-sm text-slate-600 dark:text-slate-400">
            Review pending verifications, approve or reject, and request re-KYC when needed.
          </p>
        </div>
        <Button
          type="button"
          variant="outline"
          size="sm"
          icon={FaArrowsRotate}
          onClick={() => {
            loadList();
            loadStats();
          }}
        >
          Refresh
        </Button>
      </div>

      {banner ? (
        <div className="rounded-lg border border-slate-200 bg-slate-50 px-4 py-3 text-sm text-slate-800 dark:border-slate-700 dark:bg-slate-800/60 dark:text-slate-200">
          {banner}
        </div>
      ) : null}
      {error ? (
        <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800 dark:border-red-900 dark:bg-red-950/40 dark:text-red-200">
          {error}
        </div>
      ) : null}

      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        {TABS.map((t) => {
          const active = tab === t.id;
          const count = counts[t.id];
          return (
            <button
              key={t.id}
              type="button"
              onClick={() => {
                setTab(t.id);
                setPage(1);
                setRejectFor(null);
              }}
              className={`rounded-2xl border px-4 py-3 text-left transition ${
                active
                  ? 'border-blue-300 bg-blue-50 shadow-sm dark:border-blue-800 dark:bg-blue-950/40'
                  : 'border-slate-200 bg-white hover:bg-slate-50 dark:border-slate-700 dark:bg-slate-900 dark:hover:bg-slate-800/80'
              }`}
            >
              <p className="text-xs font-semibold uppercase tracking-wide text-slate-500 dark:text-slate-400">
                {t.label}
              </p>
              <p className="mt-1 text-2xl font-bold tabular-nums text-slate-900 dark:text-slate-100">
                {count == null ? '—' : count}
              </p>
            </button>
          );
        })}
      </div>

      <Card padding="md">
        <form onSubmit={applySearch} className="mb-4 flex flex-col gap-2 sm:flex-row sm:items-center">
          <input
            type="search"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search name, phone, email, or user ID…"
            className="w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm text-slate-900 focus:border-blue-400 focus:outline-none focus:ring-2 focus:ring-blue-500/20 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-100"
          />
          <Button type="submit" variant="primary" size="md">
            Search
          </Button>
        </form>

        {loading ? (
          <div className="flex justify-center py-16">
            <LoadingSpinner />
          </div>
        ) : rows.length === 0 ? (
          <div className="py-14 text-center">
            <FaIdCard className="mx-auto mb-3 text-slate-300 dark:text-slate-600" size={40} />
            <p className="text-sm font-medium text-slate-700 dark:text-slate-300">No KYC records in this queue</p>
            <p className="mt-1 text-xs text-slate-500 dark:text-slate-400">
              Switch tabs or clear search to see other statuses.
            </p>
          </div>
        ) : (
          <ul className="divide-y divide-slate-100 dark:divide-slate-800">
            {rows.map((u) => {
              const status = u.kyc?.verification_status || 'pending';
              const busy = String(actionUserId) === String(u.id);
              const name = `${u.first_name || ''} ${u.last_name || ''}`.trim() || '—';
              const showingReject = rejectFor === u.id;
              return (
                <li key={u.id} className="py-4">
                  <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
                    <div className="min-w-0 space-y-1">
                      <div className="flex flex-wrap items-center gap-2">
                        <p className="truncate text-base font-semibold text-slate-900 dark:text-slate-100">{name}</p>
                        {statusBadge(status)}
                      </div>
                      <p className="text-sm text-slate-600 dark:text-slate-400">
                        {formatUserId(u)} · {u.role || '—'} · {u.phone || '—'}
                      </p>
                      <p className="text-xs text-slate-500 dark:text-slate-500">
                        PAN {u.kyc?.pan_verified ? '✓' : '—'} · Aadhaar {u.kyc?.aadhaar_verified ? '✓' : '—'}
                        {u.kyc?.decided_at ? ` · Last decision ${formatWhen(u.kyc.decided_at)}` : ''}
                      </p>
                      {u.kyc?.decision_notes ? (
                        <p className="text-xs text-slate-600 dark:text-slate-400">
                          Notes: {u.kyc.decision_notes}
                        </p>
                      ) : null}
                    </div>

                    <div className="flex flex-wrap items-center gap-2">
                      <Link
                        to={`/user-management/users/${u.id}`}
                        className="inline-flex items-center gap-1.5 rounded-lg border border-slate-200 px-3 py-2 text-xs font-semibold text-slate-700 transition hover:bg-slate-50 dark:border-slate-700 dark:text-slate-200 dark:hover:bg-slate-800"
                      >
                        <FaEye size={12} />
                        Open profile
                      </Link>

                      {status === 'awaiting_approval' || status === 'rejected' ? (
                        <Button
                          type="button"
                          variant="primary"
                          size="sm"
                          icon={FaCircleCheck}
                          disabled={busy}
                          onClick={() => runDecision(u.id, 'approve')}
                        >
                          Approve
                        </Button>
                      ) : null}

                      {status === 'awaiting_approval' || status === 'verified' ? (
                        <Button
                          type="button"
                          variant="outline"
                          size="sm"
                          icon={FaBan}
                          disabled={busy}
                          className="border-red-200 text-red-800 hover:bg-red-50 dark:border-red-800 dark:text-red-300 dark:hover:bg-red-950/50"
                          onClick={() => {
                            setRejectFor(showingReject ? null : u.id);
                            setRejectNotes('');
                          }}
                        >
                          Reject
                        </Button>
                      ) : null}

                      {status !== 'pending' ? (
                        <Button
                          type="button"
                          variant="outline"
                          size="sm"
                          icon={FaArrowsRotate}
                          disabled={busy}
                          onClick={() => {
                            if (
                              window.confirm(
                                `Request re-KYC for ${name}? They will need to submit documents again.`
                              )
                            ) {
                              runDecision(u.id, 'request_resubmit', 'Administrator requested re-KYC.');
                            }
                          }}
                        >
                          Request re-KYC
                        </Button>
                      ) : null}
                    </div>
                  </div>

                  {showingReject ? (
                    <div className="mt-3 rounded-xl border border-red-200 bg-red-50/70 p-3 dark:border-red-900 dark:bg-red-950/30">
                      <label className="mb-1 block text-xs font-semibold uppercase tracking-wide text-red-800 dark:text-red-300">
                        Rejection reason
                      </label>
                      <textarea
                        value={rejectNotes}
                        onChange={(e) => setRejectNotes(e.target.value)}
                        rows={3}
                        className="w-full rounded-xl border border-red-200 bg-white px-3 py-2 text-sm dark:border-red-900 dark:bg-slate-900"
                        placeholder="Explain why KYC cannot be approved…"
                      />
                      <div className="mt-2 flex gap-2">
                        <Button
                          type="button"
                          variant="outline"
                          size="sm"
                          disabled={busy || !rejectNotes.trim()}
                          className="border-red-200 text-red-800 dark:border-red-800 dark:text-red-300"
                          onClick={() => runDecision(u.id, 'reject', rejectNotes.trim())}
                        >
                          Confirm reject
                        </Button>
                        <Button
                          type="button"
                          variant="outline"
                          size="sm"
                          disabled={busy}
                          onClick={() => setRejectFor(null)}
                        >
                          Cancel
                        </Button>
                      </div>
                    </div>
                  ) : null}
                </li>
              );
            })}
          </ul>
        )}

        {totalPages > 1 ? (
          <div className="mt-4 flex items-center justify-between border-t border-slate-100 pt-4 dark:border-slate-800">
            <p className="text-xs text-slate-500 dark:text-slate-400">
              Page {page} of {totalPages} · {total} total
            </p>
            <div className="flex gap-2">
              <Button
                type="button"
                variant="outline"
                size="sm"
                disabled={page <= 1 || loading}
                onClick={() => setPage((p) => Math.max(1, p - 1))}
              >
                Previous
              </Button>
              <Button
                type="button"
                variant="outline"
                size="sm"
                disabled={page >= totalPages || loading}
                onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
              >
                Next
              </Button>
            </div>
          </div>
        ) : null}
      </Card>

      <p className="flex items-start gap-2 text-xs text-slate-500 dark:text-slate-400">
        <FaClock className="mt-0.5 shrink-0" />
        Open the user profile for full verified identity details before approving. Rejected users can
        resubmit from onboarding; admins can also request re-KYC anytime from this queue or the profile.
      </p>
    </div>
  );
};

export default KycApprovalDashboard;
