import React, { useState, useEffect, useCallback, useMemo } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { usersAPI } from '../../services/api';
import { formatUserId } from '../../utils/formatters';
import {
  FaMagnifyingGlass,
  FaPlus,
  FaEye,
  FaBuilding,
  FaPhone,
  FaEnvelope,
  FaUserCheck,
  FaUserSlash,
  FaCircleCheck,
  FaClock,
  FaBan,
  FaUsers,
  FaTrash,
} from 'react-icons/fa6';
import Button from '../common/Button';
import FeedbackModal from '../common/FeedbackModal';
import AccessControlConfirmModal from '../common/AccessControlConfirmModal';
import DeleteUserConfirmModal from './DeleteUserConfirmModal';
import AccessStatusBadges from './AccessStatusBadges';

const accountIsActive = (u) => u && u.is_active !== false;

const ACCOUNT_FILTERS = [
  { key: 'all', label: 'All', statKey: 'total' },
  { key: 'active', label: 'Active', statKey: 'active' },
  { key: 'disabled', label: 'Disabled', statKey: 'disabled' },
  { key: 'restricted', label: 'Restricted', statKey: 'restricted', operatorOnly: true },
  { key: 'payments_locked', label: 'Payments locked', statKey: 'payments_locked', operatorOnly: true },
];

const normalizeAccountFilter = (raw) => {
  const v = String(raw || '').trim().toLowerCase();
  if (!v || v === 'all') return 'all';
  if (v === 'inactive') return 'disabled';
  if (['active', 'disabled', 'restricted', 'payments_locked'].includes(v)) return v;
  return 'all';
};

const roleBadgeClass = (role) => {
  const r = role || '';
  const map = {
    'Super Admin':
      'bg-fuchsia-50 dark:bg-fuchsia-950/40 text-fuchsia-900 dark:text-fuchsia-300 ring-1 ring-fuchsia-200/90 dark:ring-fuchsia-800/90',
    Admin:
      'bg-violet-50 dark:bg-violet-950/40 text-violet-900 dark:text-violet-300 ring-1 ring-violet-200/90 dark:ring-violet-800/90',
    'Super Distributor':
      'bg-sky-50 dark:bg-sky-950/40 text-sky-900 dark:text-sky-300 ring-1 ring-sky-200/90 dark:ring-sky-800/90',
    'Master Distributor':
      'bg-cyan-50 dark:bg-cyan-950/40 text-cyan-900 dark:text-cyan-300 ring-1 ring-cyan-200/90 dark:ring-cyan-800/90',
    Distributor:
      'bg-indigo-50 dark:bg-indigo-950/40 text-indigo-900 dark:text-indigo-300 ring-1 ring-indigo-200/90 dark:ring-indigo-800/90',
    Retailer:
      'bg-slate-50 dark:bg-slate-800/50 text-slate-800 dark:text-slate-200 ring-1 ring-slate-200/90 dark:ring-slate-700/90',
  };
  return (
    map[r] ||
    'bg-slate-50 dark:bg-slate-800/50 text-slate-800 dark:text-slate-200 ring-1 ring-slate-200/90 dark:ring-slate-700/90'
  );
};

const emptyStats = {
  total: 0,
  active: 0,
  disabled: 0,
  restricted: 0,
  payments_locked: 0,
  by_role: {},
};

const UserList = ({
  role,
  onRoleChange,
  onCreateNew,
  currentUserId,
  isAdmin = false,
  showRoleBreakdown = false,
}) => {
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();
  const [users, setUsers] = useState([]);
  const [searchTerm, setSearchTerm] = useState('');
  const [appliedSearch, setAppliedSearch] = useState('');
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(25);
  const [total, setTotal] = useState(0);
  const [accountFilter, setAccountFilter] = useState(() =>
    normalizeAccountFilter(searchParams.get('account_status')),
  );
  const [stats, setStats] = useState(emptyStats);
  const [loading, setLoading] = useState(false);
  const [activeStatusSaving, setActiveStatusSaving] = useState(false);
  const [accountConfirm, setAccountConfirm] = useState(null);
  const [allowPayInWhenDisabled, setAllowPayInWhenDisabled] = useState(false);
  const [selfBlockOpen, setSelfBlockOpen] = useState(false);
  const [deleteConfirm, setDeleteConfirm] = useState(null);
  const [deleteSaving, setDeleteSaving] = useState(false);
  const [deleteFeedback, setDeleteFeedback] = useState(null);

  const visibleAccountFilters = useMemo(
    () => ACCOUNT_FILTERS.filter((f) => isAdmin || !f.operatorOnly),
    [isAdmin],
  );

  const loadStats = useCallback(async () => {
    try {
      const result = await usersAPI.getUserStats();
      if (result.success && result.data) {
        setStats({
          total: Number(result.data.total) || 0,
          active: Number(result.data.active) || 0,
          disabled: Number(result.data.disabled) || 0,
          restricted: Number(result.data.restricted) || 0,
          payments_locked: Number(result.data.payments_locked) || 0,
          by_role: result.data.by_role || {},
        });
      }
    } catch {
      console.error('Error loading user stats');
    }
  }, []);

  const loadUsers = useCallback(async () => {
    setLoading(true);
    try {
      const params = { page, page_size: pageSize };
      if (appliedSearch) params.search = appliedSearch;
      if (role && role !== 'all') params.role = role;
      if (accountFilter && accountFilter !== 'all') {
        params.account_status = accountFilter;
      }
      const result = await usersAPI.listUsers(params);

      if (result.success && result.data?.users) {
        setUsers(result.data.users);
        setTotal(Number(result.data.total) || result.data.users.length || 0);
      } else {
        setUsers([]);
        setTotal(0);
        console.error('Error loading users:', result.message);
      }
    } catch (error) {
      console.error('Error loading users:', error);
      setUsers([]);
      setTotal(0);
    } finally {
      setLoading(false);
    }
  }, [role, appliedSearch, accountFilter, page, pageSize]);

  useEffect(() => {
    const t = setTimeout(() => setAppliedSearch(searchTerm.trim()), 300);
    return () => clearTimeout(t);
  }, [searchTerm]);

  useEffect(() => {
    setPage(1);
  }, [appliedSearch, role, accountFilter, pageSize]);

  useEffect(() => {
    loadUsers();
  }, [loadUsers]);

  useEffect(() => {
    loadStats();
  }, [loadStats]);

  useEffect(() => {
    const fromUrl = normalizeAccountFilter(searchParams.get('account_status'));
    if (fromUrl !== accountFilter) {
      if (!isAdmin && (fromUrl === 'restricted' || fromUrl === 'payments_locked')) {
        setAccountFilter('all');
        return;
      }
      setAccountFilter(fromUrl);
    }
    // Sync from URL on mount / external navigation only
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [searchParams]);

  const applyAccountFilter = (key) => {
    const next = normalizeAccountFilter(key);
    setAccountFilter(next);
    const nextParams = new URLSearchParams(searchParams);
    if (next === 'all') {
      nextParams.delete('account_status');
    } else {
      nextParams.set('account_status', next);
    }
    setSearchParams(nextParams, { replace: true });
  };

  const handleViewDetails = (user) => {
    navigate(`/user-management/users/${user.id}`);
  };

  const refreshAfterMutation = async () => {
    await Promise.all([loadUsers(), loadStats()]);
  };

  const performActiveToggle = async (userRow, nextActive) => {
    setActiveStatusSaving(true);
    try {
      const res = await usersAPI.setUserAccessControls(userRow.id, {
        is_active: nextActive,
        ...(nextActive
          ? {}
          : { pay_in_allowed_when_disabled: Boolean(allowPayInWhenDisabled) }),
      });
      if (res.success) {
        await refreshAfterMutation();
      }
    } catch {
      console.error('Failed to toggle account status');
    } finally {
      setActiveStatusSaving(false);
      setAccountConfirm(null);
      setAllowPayInWhenDisabled(false);
    }
  };

  const requestToggleAccountActive = (userRow, nextActive) => {
    if (!isAdmin || !userRow?.id) return;
    if (String(userRow.id) === String(currentUserId)) {
      setSelfBlockOpen(true);
      return;
    }
    setAllowPayInWhenDisabled(false);
    setAccountConfirm({ user: userRow, nextActive });
  };

  const requestDeleteUser = (userRow) => {
    if (!isAdmin || !userRow?.id) return;
    if (String(userRow.id) === String(currentUserId)) {
      setSelfBlockOpen(true);
      return;
    }
    setDeleteConfirm(userRow);
  };

  const performDeleteUser = async () => {
    if (!deleteConfirm?.id) return;
    setDeleteSaving(true);
    try {
      const res = await usersAPI.deleteUser(deleteConfirm.id);
      if (res.success) {
        setDeleteConfirm(null);
        setDeleteFeedback({
          title: 'User deleted',
          description: res.message || 'The user and all account data were removed permanently.',
        });
        await refreshAfterMutation();
      } else {
        setDeleteFeedback({
          title: 'Delete failed',
          description: res.message || 'Could not delete this user.',
        });
      }
    } catch {
      setDeleteFeedback({
        title: 'Delete failed',
        description: 'Could not delete this user. Please try again.',
      });
    } finally {
      setDeleteSaving(false);
    }
  };

  const confirmUserName = accountConfirm
    ? `${accountConfirm.user.first_name || ''} ${accountConfirm.user.last_name || ''} (${formatUserId(
        accountConfirm.user,
      )})`.trim()
    : '';

  const rangeStart = total === 0 ? 0 : (page - 1) * pageSize + 1;
  const rangeEnd = Math.min(page * pageSize, total);
  const totalPages = Math.max(1, Math.ceil(total / pageSize) || 1);

  const roleBreakdown = useMemo(() => {
    const entries = Object.entries(stats.by_role || {}).filter(([, n]) => Number(n) > 0);
    entries.sort((a, b) => Number(b[1]) - Number(a[1]));
    return entries;
  }, [stats.by_role]);

  const metricCols =
    visibleAccountFilters.length >= 5
      ? 'grid-cols-2 sm:grid-cols-3 lg:grid-cols-5'
      : visibleAccountFilters.length === 4
        ? 'grid-cols-2 sm:grid-cols-4'
        : 'grid-cols-2 sm:grid-cols-3';

  return (
    <div className="space-y-4">
      {/* Account census metric cards */}
      <div className={`grid gap-2.5 ${metricCols}`}>
        {visibleAccountFilters.map((f) => {
          const count = stats[f.statKey] ?? 0;
          const selected = accountFilter === f.key;
          return (
            <button
              key={f.key}
              type="button"
              onClick={() => applyAccountFilter(f.key)}
              className={`rounded-xl border p-3 text-left shadow-sm transition-colors ${
                selected
                  ? 'border-indigo-400 bg-indigo-50 ring-1 ring-indigo-200 dark:border-indigo-600 dark:bg-indigo-950/50 dark:ring-indigo-800'
                  : 'border-slate-200/90 bg-white hover:border-slate-300 dark:border-slate-700/90 dark:bg-slate-900 dark:hover:border-slate-600'
              }`}
            >
              <p
                className={`text-[11px] font-semibold uppercase tracking-wider ${
                  selected
                    ? 'text-indigo-700 dark:text-indigo-300'
                    : 'text-slate-500 dark:text-slate-400'
                }`}
              >
                {f.label}
              </p>
              <p
                className={`mt-1 text-2xl font-bold tabular-nums tracking-tight ${
                  selected
                    ? 'text-indigo-900 dark:text-indigo-100'
                    : 'text-slate-900 dark:text-slate-100'
                }`}
              >
                {count}
              </p>
            </button>
          );
        })}
      </div>

      {showRoleBreakdown && roleBreakdown.length > 0 ? (
        <div className="rounded-xl border border-slate-200/90 bg-slate-50/60 p-3 dark:border-slate-700/90 dark:bg-slate-800/40 sm:p-4">
          <p className="mb-2.5 text-[11px] font-semibold uppercase tracking-wider text-slate-500 dark:text-slate-400">
            By role
          </p>
          <div className="grid grid-cols-2 gap-2 sm:grid-cols-3 lg:grid-cols-4 xl:grid-cols-6">
            {roleBreakdown.map(([r, n]) => {
              const selected = role === r;
              return (
                <button
                  key={r}
                  type="button"
                  onClick={() => onRoleChange?.(r)}
                  className={`rounded-lg border px-2.5 py-2 text-left transition-colors ${
                    selected
                      ? 'border-indigo-300 bg-white shadow-sm dark:border-indigo-700 dark:bg-slate-900'
                      : 'border-transparent bg-white/80 hover:border-slate-200 dark:bg-slate-900/60 dark:hover:border-slate-600'
                  }`}
                >
                  <p className="truncate text-[11px] font-medium text-slate-600 dark:text-slate-300" title={r}>
                    {r}
                  </p>
                  <p className="mt-0.5 text-lg font-bold tabular-nums text-slate-900 dark:text-slate-100">
                    {n}
                  </p>
                </button>
              );
            })}
          </div>
        </div>
      ) : null}

      {/* Toolbar */}
      <div className="rounded-xl border border-slate-200/90 bg-white p-3 shadow-sm ring-1 ring-slate-900/5 dark:border-slate-700/90 dark:bg-slate-900 sm:p-4">
        <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
          <div className="relative min-w-0 flex-1">
            <FaMagnifyingGlass
              className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-slate-400 dark:text-slate-500"
              size={16}
              aria-hidden
            />
            <input
              type="search"
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              placeholder="Search name, code, member ID, phone, email…"
              className="w-full rounded-lg border border-slate-200 bg-slate-50/80 py-2 pl-10 pr-3 text-sm text-slate-900 placeholder:text-slate-400 transition-shadow focus:border-indigo-300 focus:bg-white focus:outline-none focus:ring-2 focus:ring-indigo-500/20 dark:border-slate-700 dark:bg-slate-800/50 dark:text-slate-100 dark:placeholder:text-slate-500"
              aria-label="Search users"
            />
          </div>
          <div className="flex shrink-0 flex-col gap-2 sm:flex-row sm:items-center sm:justify-end">
            <label className="flex items-center gap-2 text-xs font-medium text-slate-600 dark:text-slate-400">
              <span className="whitespace-nowrap">Per page</span>
              <select
                value={pageSize}
                onChange={(e) => setPageSize(Number(e.target.value) || 25)}
                className="rounded-lg border border-slate-200 bg-white py-2 pl-2 pr-8 text-sm font-medium text-slate-800 shadow-sm focus:border-indigo-300 focus:outline-none focus:ring-2 focus:ring-indigo-500/20 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-200"
                aria-label="Page size"
              >
                <option value={25}>25</option>
                <option value={50}>50</option>
                <option value={100}>100</option>
              </select>
            </label>
            {onCreateNew && (
              <Button
                onClick={onCreateNew}
                variant="primary"
                icon={FaPlus}
                iconPosition="left"
                size="sm"
                className="whitespace-nowrap shadow-md shadow-indigo-600/15"
              >
                Add {role || 'user'}
              </Button>
            )}
          </div>
        </div>
        {!loading && (
          <p className="mt-2 text-xs font-medium text-slate-500 dark:text-slate-400">
            {total === 0 ? (
              'No users match the current filters'
            ) : (
              <>
                Showing{' '}
                <span className="text-slate-800 dark:text-slate-200">
                  {rangeStart}–{rangeEnd}
                </span>{' '}
                of <span className="text-slate-800 dark:text-slate-200">{total}</span>
                {appliedSearch ? ' matching your search' : ''}
              </>
            )}
          </p>
        )}
      </div>

      {/* Table */}
      {loading ? (
        <div className="flex flex-col items-center justify-center rounded-xl border border-slate-200 bg-white py-16 shadow-sm dark:border-slate-700 dark:bg-slate-900">
          <div className="h-9 w-9 animate-spin rounded-full border-2 border-indigo-600 border-t-transparent" />
          <p className="mt-3 text-sm font-medium text-slate-600 dark:text-slate-400">Loading directory…</p>
        </div>
      ) : users.length === 0 ? (
        <div className="rounded-xl border border-dashed border-slate-200 bg-slate-50/50 px-6 py-12 text-center dark:border-slate-700 dark:bg-slate-800/50">
          <FaUsers className="mx-auto mb-3 text-slate-300" size={36} />
          <p className="font-semibold text-slate-700 dark:text-slate-300">
            {searchTerm || accountFilter !== 'all'
              ? 'No matches'
              : 'No users in your network'}
          </p>
          <p className="mx-auto mt-1 max-w-md text-sm text-slate-500 dark:text-slate-400">
            {searchTerm || accountFilter !== 'all'
              ? 'Try a different search or clear filters.'
              : 'Add a user or adjust role filters above.'}
          </p>
        </div>
      ) : (
        <div className="overflow-hidden rounded-xl border border-slate-200/90 bg-white shadow-sm ring-1 ring-slate-900/5 dark:border-slate-700/90 dark:bg-slate-900">
          <div className="max-h-[min(70vh,720px)] overflow-auto">
            <table className="w-full min-w-[880px] border-collapse text-left">
              <thead className="sticky top-0 z-10">
                <tr className="border-b border-slate-200 bg-slate-50/95 backdrop-blur dark:border-slate-700 dark:bg-slate-900/95">
                  <th className="px-3 py-2 text-[10px] font-semibold uppercase tracking-wider text-slate-500 dark:text-slate-400">
                    User
                  </th>
                  <th className="px-3 py-2 text-[10px] font-semibold uppercase tracking-wider text-slate-500 dark:text-slate-400">
                    Contact
                  </th>
                  <th className="px-3 py-2 text-[10px] font-semibold uppercase tracking-wider text-slate-500 dark:text-slate-400">
                    Business
                  </th>
                  <th className="px-3 py-2 text-[10px] font-semibold uppercase tracking-wider text-slate-500 dark:text-slate-400">
                    Role
                  </th>
                  <th className="px-3 py-2 text-[10px] font-semibold uppercase tracking-wider text-slate-500 dark:text-slate-400">
                    Access
                  </th>
                  <th className="px-3 py-2 text-[10px] font-semibold uppercase tracking-wider text-slate-500 dark:text-slate-400">
                    Readiness
                  </th>
                  <th className="min-w-[9.5rem] px-3 py-2 text-center text-[10px] font-semibold uppercase tracking-wider text-slate-500 dark:text-slate-400">
                    Actions
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
                {users.map((user) => {
                  const userId = user.display_code || user.user_id || user.member_id || user.id;
                  const fullName =
                    `${user.first_name || ''} ${user.last_name || ''}`.trim() || '—';
                  const businessName = user.profile?.business_name || '—';
                  const kycStatus = user.kyc?.verification_status || 'pending';
                  const kycOk = kycStatus === 'verified';
                  const kycRejected = kycStatus === 'rejected';
                  const kycAwaiting = kycStatus === 'awaiting_approval';
                  const kycLabel = kycOk
                    ? 'verified'
                    : kycRejected
                      ? 'rejected'
                      : kycAwaiting
                        ? 'awaiting approval'
                        : 'pending';
                  const mpinOk = user.mpin_configured === true;
                  const activeOk = accountIsActive(user);
                  const isSelf = String(user.id) === String(currentUserId);

                  return (
                    <tr
                      key={user.id || userId}
                      className={`group transition-colors hover:bg-indigo-50/40 dark:hover:bg-indigo-950/60 ${
                        !activeOk ? 'bg-slate-50/90 dark:bg-slate-800/50' : ''
                      }`}
                    >
                      <td className="px-3 py-2 align-top">
                        <div className="text-sm font-semibold capitalize tracking-tight text-slate-900 dark:text-slate-100">
                          {fullName}
                        </div>
                        <div className="mt-0.5 font-mono text-[11px] font-medium tabular-nums text-indigo-600 dark:text-indigo-400">
                          {formatUserId(user)}
                        </div>
                      </td>
                      <td className="px-3 py-2 align-top text-xs text-slate-700 dark:text-slate-300">
                        <div className="flex max-w-[200px] items-start gap-1.5">
                          <FaEnvelope
                            className="mt-0.5 shrink-0 text-slate-400 dark:text-slate-500"
                            size={12}
                            aria-hidden
                          />
                          <span className="break-all leading-snug">{user.email || '—'}</span>
                        </div>
                        <div className="mt-1 flex items-center gap-1.5 tabular-nums text-slate-600 dark:text-slate-400">
                          <FaPhone
                            className="shrink-0 text-slate-400 dark:text-slate-500"
                            size={12}
                            aria-hidden
                          />
                          {user.phone || '—'}
                        </div>
                      </td>
                      <td className="max-w-[180px] px-3 py-2 align-top text-xs text-slate-700 dark:text-slate-300">
                        <div className="flex items-start gap-1.5">
                          <FaBuilding
                            className="mt-0.5 shrink-0 text-slate-400 dark:text-slate-500"
                            size={12}
                            aria-hidden
                          />
                          <span className="line-clamp-2 leading-snug" title={businessName}>
                            {businessName}
                          </span>
                        </div>
                      </td>
                      <td className="px-3 py-2 align-middle">
                        <span
                          className={`inline-flex max-w-[150px] truncate rounded-md px-2 py-0.5 text-[11px] font-semibold ${roleBadgeClass(
                            user.role,
                          )}`}
                          title={user.role}
                        >
                          {user.role}
                        </span>
                      </td>
                      <td className="px-3 py-2 align-middle">
                        <AccessStatusBadges user={user} />
                      </td>
                      <td className="px-3 py-2 align-middle">
                        <div className="flex flex-nowrap items-center gap-1.5 whitespace-nowrap text-[10px]">
                          <span
                            className={`inline-flex items-center gap-1 rounded-md px-1.5 py-0.5 font-semibold ring-1 ${
                              kycOk
                                ? 'bg-emerald-50 text-emerald-800 ring-emerald-200/80 dark:bg-emerald-950/40 dark:text-emerald-300 dark:ring-emerald-800'
                                : kycRejected
                                  ? 'bg-red-50 text-red-800 ring-red-200/80 dark:bg-red-950/40 dark:text-red-300 dark:ring-red-800'
                                  : 'bg-amber-50 text-amber-900 ring-amber-200/80 dark:bg-amber-950/40 dark:text-amber-300 dark:ring-amber-800'
                            }`}
                            title={`KYC ${kycLabel}`}
                          >
                            {kycOk ? (
                              <FaCircleCheck size={10} aria-hidden />
                            ) : kycRejected ? (
                              <FaBan size={10} aria-hidden />
                            ) : (
                              <FaClock size={10} aria-hidden />
                            )}
                            KYC · {kycOk ? 'ok' : kycRejected ? 'rej' : kycAwaiting ? 'wait' : 'pend'}
                          </span>
                          <span
                            className={`inline-flex items-center gap-1 rounded-md px-1.5 py-0.5 font-semibold ring-1 ${
                              mpinOk
                                ? 'bg-emerald-50 text-emerald-800 ring-emerald-200/80 dark:bg-emerald-950/40 dark:text-emerald-300 dark:ring-emerald-800'
                                : 'bg-amber-50 text-amber-900 ring-amber-200/80 dark:bg-amber-950/40 dark:text-amber-300 dark:ring-amber-800'
                            }`}
                            title={mpinOk ? 'MPIN set' : 'MPIN pending'}
                          >
                            {mpinOk ? (
                              <FaCircleCheck size={10} aria-hidden />
                            ) : (
                              <FaClock size={10} aria-hidden />
                            )}
                            MPIN · {mpinOk ? 'set' : 'pend'}
                          </span>
                        </div>
                      </td>
                      <td className="px-3 py-2 align-middle">
                        <div className="flex flex-nowrap items-center justify-center gap-1">
                          <button
                            type="button"
                            onClick={() => handleViewDetails(user)}
                            title="View"
                            className="inline-flex h-8 w-8 items-center justify-center rounded-md border border-slate-200 bg-white text-slate-700 shadow-sm transition-all hover:border-indigo-200 hover:bg-indigo-50 hover:text-indigo-900 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-300 dark:hover:bg-indigo-950/60 dark:hover:text-indigo-200"
                          >
                            <FaEye size={13} aria-hidden />
                            <span className="sr-only">View</span>
                          </button>
                          {isAdmin && !isSelf && (
                            <>
                              <button
                                type="button"
                                onClick={() => requestToggleAccountActive(user, !activeOk)}
                                disabled={activeStatusSaving || deleteSaving}
                                title={activeOk ? 'Disable' : 'Enable'}
                                className={`inline-flex h-8 w-8 items-center justify-center rounded-md shadow-sm transition-all disabled:opacity-50 ${
                                  activeOk
                                    ? 'border border-amber-200/90 bg-amber-50 text-amber-900 hover:bg-amber-100 dark:border-amber-800/90 dark:bg-amber-950/40 dark:text-amber-300 dark:hover:bg-amber-900/60'
                                    : 'border border-emerald-200/90 bg-emerald-50 text-emerald-900 hover:bg-emerald-100 dark:border-emerald-800/90 dark:bg-emerald-950/40 dark:text-emerald-300 dark:hover:bg-emerald-900/60'
                                }`}
                              >
                                {activeOk ? (
                                  <FaUserSlash size={13} aria-hidden />
                                ) : (
                                  <FaUserCheck size={13} aria-hidden />
                                )}
                                <span className="sr-only">{activeOk ? 'Disable' : 'Enable'}</span>
                              </button>
                              <button
                                type="button"
                                onClick={() => requestDeleteUser(user)}
                                disabled={deleteSaving || activeStatusSaving}
                                title="Delete"
                                className="inline-flex h-8 w-8 items-center justify-center rounded-md border border-red-200/90 bg-red-50 text-red-800 shadow-sm transition-all hover:bg-red-100 disabled:opacity-50 dark:border-red-800/90 dark:bg-red-950/40 dark:text-red-300 dark:hover:bg-red-900/60"
                              >
                                <FaTrash size={13} aria-hidden />
                                <span className="sr-only">Delete</span>
                              </button>
                            </>
                          )}
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
          {total > pageSize ? (
            <div className="flex flex-wrap items-center justify-between gap-3 border-t border-slate-100 px-3 py-2.5 dark:border-slate-800">
              <p className="text-xs text-slate-500 dark:text-slate-400">
                Page {page} of {totalPages}
              </p>
              <div className="flex items-center gap-2">
                <button
                  type="button"
                  disabled={page <= 1 || loading}
                  onClick={() => setPage((p) => Math.max(1, p - 1))}
                  className="rounded-lg border border-slate-200 bg-white px-3 py-1.5 text-xs font-semibold text-slate-700 disabled:opacity-50 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-300"
                >
                  Previous
                </button>
                <button
                  type="button"
                  disabled={page >= totalPages || loading}
                  onClick={() => setPage((p) => p + 1)}
                  className="rounded-lg border border-slate-200 bg-white px-3 py-1.5 text-xs font-semibold text-slate-700 disabled:opacity-50 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-300"
                >
                  Next
                </button>
              </div>
            </div>
          ) : null}
        </div>
      )}

      {accountConfirm ? (
        <AccessControlConfirmModal
          actionKey={accountConfirm.nextActive ? 'enable_account' : 'disable_account'}
          userName={confirmUserName}
          loading={activeStatusSaving}
          allowPayInWhenDisabled={allowPayInWhenDisabled}
          onAllowPayInChange={!accountConfirm.nextActive ? setAllowPayInWhenDisabled : undefined}
          onConfirm={() => performActiveToggle(accountConfirm.user, accountConfirm.nextActive)}
          onCancel={() => !activeStatusSaving && setAccountConfirm(null)}
        />
      ) : null}

      <FeedbackModal
        open={selfBlockOpen}
        onClose={() => setSelfBlockOpen(false)}
        title="Cannot modify your own account"
        description="Use another administrator account to disable, delete, or change access for your own user."
      />

      <DeleteUserConfirmModal
        open={Boolean(deleteConfirm)}
        user={deleteConfirm}
        loading={deleteSaving}
        onConfirm={performDeleteUser}
        onCancel={() => !deleteSaving && setDeleteConfirm(null)}
      />

      <FeedbackModal
        open={Boolean(deleteFeedback)}
        onClose={() => setDeleteFeedback(null)}
        title={deleteFeedback?.title || ''}
        description={deleteFeedback?.description || ''}
      />
    </div>
  );
};

export default UserList;
