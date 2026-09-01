import React, { useState, useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
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

const roleBadgeClass = (role) => {
  const r = role || '';
  const map = {
    Admin: 'bg-violet-50 dark:bg-violet-950/40 text-violet-900 dark:text-violet-300 ring-1 ring-violet-200/90 dark:ring-violet-800/90',
    'Super Distributor': 'bg-sky-50 dark:bg-sky-950/40 text-sky-900 dark:text-sky-300 ring-1 ring-sky-200/90 dark:ring-sky-800/90',
    'Master Distributor': 'bg-cyan-50 dark:bg-cyan-950/40 text-cyan-900 dark:text-cyan-300 ring-1 ring-cyan-200/90 dark:ring-cyan-800/90',
    Distributor: 'bg-indigo-50 dark:bg-indigo-950/40 text-indigo-900 dark:text-indigo-300 ring-1 ring-indigo-200/90 dark:ring-indigo-800/90',
    Retailer: 'bg-slate-50 dark:bg-slate-800/50 text-slate-800 dark:text-slate-200 ring-1 ring-slate-200/90 dark:ring-slate-700/90',
  };
  return map[r] || 'bg-slate-50 dark:bg-slate-800/50 text-slate-800 dark:text-slate-200 ring-1 ring-slate-200/90 dark:ring-slate-700/90';
};

const UserList = ({ role, onCreateNew, currentUserId, isAdmin = false }) => {
  const navigate = useNavigate();
  const [users, setUsers] = useState([]);
  const [searchTerm, setSearchTerm] = useState('');
  const [appliedSearch, setAppliedSearch] = useState('');
  const [page, setPage] = useState(1);
  const [pageSize] = useState(25);
  const [total, setTotal] = useState(0);
  const [accountFilter, setAccountFilter] = useState('all');
  const [loading, setLoading] = useState(false);
  const [activeStatusSaving, setActiveStatusSaving] = useState(false);
  const [accountConfirm, setAccountConfirm] = useState(null);
  const [allowPayInWhenDisabled, setAllowPayInWhenDisabled] = useState(false);
  const [selfBlockOpen, setSelfBlockOpen] = useState(false);
  const [deleteConfirm, setDeleteConfirm] = useState(null);
  const [deleteSaving, setDeleteSaving] = useState(false);
  const [deleteFeedback, setDeleteFeedback] = useState(null);

  const loadUsers = useCallback(async () => {
    setLoading(true);
    try {
      const params = { page, page_size: pageSize };
      if (appliedSearch) params.search = appliedSearch;
      if (role && role !== 'all') params.role = role;
      if (isAdmin && accountFilter === 'active') params.account_status = 'active';
      if (isAdmin && accountFilter === 'inactive') params.account_status = 'disabled';
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
  }, [role, appliedSearch, isAdmin, accountFilter, page, pageSize]);

  useEffect(() => {
    const t = setTimeout(() => setAppliedSearch(searchTerm.trim()), 300);
    return () => clearTimeout(t);
  }, [searchTerm]);

  useEffect(() => {
    setPage(1);
  }, [appliedSearch, role, accountFilter]);

  useEffect(() => {
    loadUsers();
  }, [loadUsers]);

  const handleViewDetails = (user) => {
    navigate(`/user-management/users/${user.id}`);
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
        await loadUsers();
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
        await loadUsers();
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

  return (
    <div className="space-y-6">
      {/* Toolbar */}
      <div className="rounded-2xl border border-slate-200/90 dark:border-slate-700/90 bg-white dark:bg-slate-900 p-4 shadow-sm ring-1 ring-slate-900/5 sm:p-5">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
          <div className="relative flex-1 min-w-0">
            <FaMagnifyingGlass
              className="pointer-events-none absolute left-3.5 top-1/2 -translate-y-1/2 text-slate-400 dark:text-slate-500"
              size={18}
              aria-hidden
            />
            <input
              type="search"
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              placeholder="Search by name, display code, member ID, legacy ID, phone, email…"
              className="w-full rounded-xl border border-slate-200 dark:border-slate-700 bg-slate-50/80 dark:bg-slate-800/50 py-3 pl-11 pr-4 text-sm text-slate-900 dark:text-slate-100 placeholder:text-slate-400 dark:placeholder:text-slate-500 transition-shadow focus:border-indigo-300 focus:bg-white focus:outline-none focus:ring-2 focus:ring-indigo-500/20"
              aria-label="Search users"
            />
          </div>
          <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-end shrink-0">
            {isAdmin && (
              <div className="relative">
                <span className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-slate-400 dark:text-slate-500" aria-hidden>
                  <FaUsers size={16} />
                </span>
                <select
                  value={accountFilter}
                  onChange={(e) => setAccountFilter(e.target.value)}
                  className="w-full sm:w-[200px] appearance-none rounded-xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900 py-3 pl-10 pr-10 text-sm font-medium text-slate-800 dark:text-slate-200 shadow-sm transition-colors focus:border-indigo-300 focus:outline-none focus:ring-2 focus:ring-indigo-500/20"
                  aria-label="Filter by account status"
                >
                  <option value="all">All accounts</option>
                  <option value="active">Active only</option>
                  <option value="inactive">Disabled only</option>
                </select>
                <span className="pointer-events-none absolute right-3 top-1/2 -translate-y-1/2 text-slate-400 dark:text-slate-500 text-xs">▾</span>
              </div>
            )}
            {onCreateNew && (
              <Button onClick={onCreateNew} variant="primary" icon={FaPlus} iconPosition="left" size="md" className="whitespace-nowrap shadow-md shadow-indigo-600/15">
                Add {role || 'user'}
              </Button>
            )}
          </div>
        </div>
        {!loading && total > 0 && (
          <p className="mt-3 text-xs font-medium text-slate-500 dark:text-slate-400">
            Showing{' '}
            <span className="text-slate-800 dark:text-slate-200">
              {(page - 1) * pageSize + 1}–{Math.min(page * pageSize, total)}
            </span>{' '}
            of <span className="text-slate-800 dark:text-slate-200">{total}</span>
            {total === 1 ? ' user' : ' users'}
            {appliedSearch ? ' matching your search' : ''}
          </p>
        )}
      </div>

      {/* Table */}
      {loading ? (
        <div className="flex flex-col items-center justify-center rounded-2xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900 py-20 shadow-sm">
          <div className="h-11 w-11 animate-spin rounded-full border-2 border-indigo-600 border-t-transparent" />
          <p className="mt-4 text-sm font-medium text-slate-600 dark:text-slate-400">Loading directory…</p>
        </div>
      ) : users.length === 0 ? (
        <div className="rounded-2xl border border-dashed border-slate-200 dark:border-slate-700 bg-slate-50/50 dark:bg-slate-800/50 px-6 py-16 text-center">
          <FaUsers className="mx-auto text-slate-300 mb-3" size={40} />
          <p className="text-slate-700 dark:text-slate-300 font-semibold">
            {searchTerm ? 'No matches' : `No ${role || 'users'} found`}
          </p>
          <p className="mt-1 text-sm text-slate-500 dark:text-slate-400 max-w-md mx-auto">
            {searchTerm ? 'Try a different search or clear filters.' : 'Add a user or adjust role filters above.'}
          </p>
        </div>
      ) : (
        <div className="overflow-hidden rounded-2xl border border-slate-200/90 dark:border-slate-700/90 bg-white dark:bg-slate-900 shadow-sm ring-1 ring-slate-900/5">
          <div className="overflow-x-auto">
            <table className="w-full min-w-[900px] text-left border-collapse">
              <thead>
                <tr className="border-b border-slate-200 dark:border-slate-700 bg-gradient-to-b from-slate-50 dark:from-slate-900 to-slate-50/80 dark:to-slate-900/80">
                  <th className="px-5 py-4 text-[11px] font-semibold uppercase tracking-wider text-slate-500 dark:text-slate-400">
                    User
                  </th>
                  <th className="px-5 py-4 text-[11px] font-semibold uppercase tracking-wider text-slate-500 dark:text-slate-400">
                    Contact
                  </th>
                  <th className="px-5 py-4 text-[11px] font-semibold uppercase tracking-wider text-slate-500 dark:text-slate-400">
                    Business
                  </th>
                  <th className="px-5 py-4 text-[11px] font-semibold uppercase tracking-wider text-slate-500 dark:text-slate-400">
                    Role
                  </th>
                  <th className="px-5 py-4 text-[11px] font-semibold uppercase tracking-wider text-slate-500 dark:text-slate-400">
                    Access
                  </th>
                  <th className="px-5 py-4 text-[11px] font-semibold uppercase tracking-wider text-slate-500 dark:text-slate-400">
                    Readiness
                  </th>
                  <th className="px-5 py-4 text-center text-[11px] font-semibold uppercase tracking-wider text-slate-500 dark:text-slate-400 w-[200px]">
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
                      className={`group transition-colors hover:bg-indigo-50/40 dark:hover:bg-indigo-950/60 ${!activeOk ? 'bg-slate-50/90 dark:bg-slate-800/50' : ''}`}
                    >
                      <td className="px-5 py-4 align-top">
                        <div className="font-semibold text-slate-900 dark:text-slate-100 capitalize tracking-tight">{fullName}</div>
                        <div className="mt-1 font-mono text-xs font-medium text-indigo-600 dark:text-indigo-400 tabular-nums">
                          {formatUserId(user)}
                        </div>
                      </td>
                      <td className="px-5 py-4 align-top text-sm text-slate-700 dark:text-slate-300">
                        <div className="flex items-start gap-2 max-w-[220px]">
                          <FaEnvelope className="mt-0.5 shrink-0 text-slate-400 dark:text-slate-500" size={14} aria-hidden />
                          <span className="break-all leading-snug">{user.email || '—'}</span>
                        </div>
                        <div className="mt-2 flex items-center gap-2 text-slate-600 dark:text-slate-400 tabular-nums">
                          <FaPhone className="shrink-0 text-slate-400 dark:text-slate-500" size={14} aria-hidden />
                          {user.phone || '—'}
                        </div>
                      </td>
                      <td className="px-5 py-4 align-top text-sm text-slate-700 dark:text-slate-300 max-w-[200px]">
                        <div className="flex items-start gap-2">
                          <FaBuilding className="mt-0.5 shrink-0 text-slate-400 dark:text-slate-500" size={14} aria-hidden />
                          <span className="line-clamp-2 leading-snug" title={businessName}>
                            {businessName}
                          </span>
                        </div>
                      </td>
                      <td className="px-5 py-4 align-top">
                        <span
                          className={`inline-flex max-w-[160px] truncate rounded-lg px-2.5 py-1 text-xs font-semibold ${roleBadgeClass(
                            user.role,
                          )}`}
                          title={user.role}
                        >
                          {user.role}
                        </span>
                      </td>
                      <td className="px-5 py-4 align-top">
                        <AccessStatusBadges user={user} />
                      </td>
                      <td className="px-5 py-4 align-top">
                        <div className="flex flex-col gap-1.5 text-xs">
                          <div className="flex items-center gap-2 text-slate-700 dark:text-slate-300" title="KYC">
                            {kycOk ? (
                              <FaCircleCheck className="text-emerald-600 dark:text-emerald-400 shrink-0" size={14} aria-hidden />
                            ) : kycRejected ? (
                              <FaBan className="text-red-500 shrink-0" size={14} aria-hidden />
                            ) : (
                              <FaClock className="text-amber-500 shrink-0" size={14} aria-hidden />
                            )}
                            <span className="font-medium">
                              KYC {kycLabel}
                            </span>
                          </div>
                          <div className="flex items-center gap-2 text-slate-700 dark:text-slate-300" title="MPIN">
                            {mpinOk ? (
                              <FaCircleCheck className="text-emerald-600 dark:text-emerald-400 shrink-0" size={14} aria-hidden />
                            ) : (
                              <FaClock className="text-amber-500 shrink-0" size={14} aria-hidden />
                            )}
                            <span className="font-medium">{mpinOk ? 'MPIN set' : 'MPIN pending'}</span>
                          </div>
                        </div>
                      </td>
                      <td className="px-5 py-4 align-middle">
                        <div className="flex flex-wrap items-center justify-center gap-2">
                          <button
                            type="button"
                            onClick={() => handleViewDetails(user)}
                            className="inline-flex items-center gap-1.5 rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900 px-3 py-2 text-xs font-semibold text-slate-700 dark:text-slate-300 shadow-sm transition-all hover:border-indigo-200 hover:bg-indigo-50 dark:hover:bg-indigo-950/60 hover:text-indigo-900 dark:hover:text-indigo-200"
                          >
                            <FaEye size={14} aria-hidden />
                            View
                          </button>
                          {isAdmin && !isSelf && (
                            <>
                              <button
                                type="button"
                                onClick={() => requestToggleAccountActive(user, !activeOk)}
                                disabled={activeStatusSaving || deleteSaving}
                                className={`inline-flex items-center gap-1.5 rounded-lg px-3 py-2 text-xs font-semibold shadow-sm transition-all disabled:opacity-50 ${
                                  activeOk
                                    ? 'border border-amber-200/90 dark:border-amber-800/90 bg-amber-50 dark:bg-amber-950/40 text-amber-900 dark:text-amber-300 hover:bg-amber-100 dark:hover:bg-amber-900/60'
                                    : 'border border-emerald-200/90 dark:border-emerald-800/90 bg-emerald-50 dark:bg-emerald-950/40 text-emerald-900 dark:text-emerald-300 hover:bg-emerald-100 dark:hover:bg-emerald-900/60'
                                }`}
                              >
                                {activeOk ? (
                                  <>
                                    <FaUserSlash size={14} aria-hidden />
                                    Disable
                                  </>
                                ) : (
                                  <>
                                    <FaUserCheck size={14} aria-hidden />
                                    Enable
                                  </>
                                )}
                              </button>
                              <button
                                type="button"
                                onClick={() => requestDeleteUser(user)}
                                disabled={deleteSaving || activeStatusSaving}
                                className="inline-flex items-center gap-1.5 rounded-lg border border-red-200/90 dark:border-red-800/90 bg-red-50 dark:bg-red-950/40 px-3 py-2 text-xs font-semibold text-red-800 dark:text-red-300 shadow-sm transition-all hover:bg-red-100 dark:hover:bg-red-900/60 disabled:opacity-50"
                              >
                                <FaTrash size={14} aria-hidden />
                                Delete
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
            <div className="flex flex-wrap items-center justify-between gap-3 border-t border-slate-100 dark:border-slate-800 px-4 py-3">
              <p className="text-xs text-slate-500 dark:text-slate-400">
                Page {page} of {Math.max(1, Math.ceil(total / pageSize))}
              </p>
              <div className="flex items-center gap-2">
                <button
                  type="button"
                  disabled={page <= 1 || loading}
                  onClick={() => setPage((p) => Math.max(1, p - 1))}
                  className="rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900 px-3 py-1.5 text-xs font-semibold text-slate-700 dark:text-slate-300 disabled:opacity-50"
                >
                  Previous
                </button>
                <button
                  type="button"
                  disabled={page >= Math.ceil(total / pageSize) || loading}
                  onClick={() => setPage((p) => p + 1)}
                  className="rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900 px-3 py-1.5 text-xs font-semibold text-slate-700 dark:text-slate-300 disabled:opacity-50"
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
