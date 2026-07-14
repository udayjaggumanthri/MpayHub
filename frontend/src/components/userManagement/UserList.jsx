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
  FaXmark,
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
    Admin: 'bg-violet-50 text-violet-900 ring-1 ring-violet-200/90',
    'Super Distributor': 'bg-sky-50 text-sky-900 ring-1 ring-sky-200/90',
    'Master Distributor': 'bg-cyan-50 text-cyan-900 ring-1 ring-cyan-200/90',
    Distributor: 'bg-indigo-50 text-indigo-900 ring-1 ring-indigo-200/90',
    Retailer: 'bg-slate-50 text-slate-800 ring-1 ring-slate-200/90',
  };
  return map[r] || 'bg-slate-50 text-slate-800 ring-1 ring-slate-200/90';
};

const UserList = ({ role, onCreateNew, currentUserId, isAdmin = false }) => {
  const navigate = useNavigate();
  const [users, setUsers] = useState([]);
  const [searchTerm, setSearchTerm] = useState('');
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
      const params = {};
      if (role && role !== 'all') params.role = role;
      if (isAdmin && accountFilter === 'active') params.account_status = 'active';
      if (isAdmin && accountFilter === 'inactive') params.account_status = 'disabled';
      const result = await usersAPI.listUsers(params);

      if (result.success && result.data?.users) {
        const filtered = result.data.users.filter((u) => {
          const searchLower = searchTerm.toLowerCase();
          const firstName = (u.first_name || '').toLowerCase();
          const lastName = (u.last_name || '').toLowerCase();
          const fullName = `${firstName} ${lastName}`.trim();
          const userId = String(u.user_id ?? '').toLowerCase();
          const phone = (u.phone || '').toLowerCase();
          const email = (u.email || '').toLowerCase();
          const businessName = (u.profile?.business_name || '').toLowerCase();

          return (
            fullName.includes(searchLower) ||
            userId.includes(searchLower) ||
            phone.includes(searchTerm) ||
            email.includes(searchLower) ||
            businessName.includes(searchLower)
          );
        });
        setUsers(filtered);
      } else {
        setUsers([]);
        console.error('Error loading users:', result.message);
      }
    } catch (error) {
      console.error('Error loading users:', error);
      setUsers([]);
    } finally {
      setLoading(false);
    }
  }, [role, searchTerm, isAdmin, accountFilter]);

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
        accountConfirm.user.user_id || accountConfirm.user.id,
      )})`.trim()
    : '';

  return (
    <div className="space-y-6">
      {/* Toolbar */}
      <div className="rounded-2xl border border-slate-200/90 bg-white p-4 shadow-sm ring-1 ring-slate-900/5 sm:p-5">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
          <div className="relative flex-1 min-w-0">
            <FaMagnifyingGlass
              className="pointer-events-none absolute left-3.5 top-1/2 -translate-y-1/2 text-slate-400"
              size={18}
              aria-hidden
            />
            <input
              type="search"
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              placeholder="Search by name, user ID, phone, email, or business…"
              className="w-full rounded-xl border border-slate-200 bg-slate-50/80 py-3 pl-11 pr-4 text-sm text-slate-900 placeholder:text-slate-400 transition-shadow focus:border-indigo-300 focus:bg-white focus:outline-none focus:ring-2 focus:ring-indigo-500/20"
              aria-label="Search users"
            />
          </div>
          <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-end shrink-0">
            {isAdmin && (
              <div className="relative">
                <span className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" aria-hidden>
                  <FaUsers size={16} />
                </span>
                <select
                  value={accountFilter}
                  onChange={(e) => setAccountFilter(e.target.value)}
                  className="w-full sm:w-[200px] appearance-none rounded-xl border border-slate-200 bg-white py-3 pl-10 pr-10 text-sm font-medium text-slate-800 shadow-sm transition-colors focus:border-indigo-300 focus:outline-none focus:ring-2 focus:ring-indigo-500/20"
                  aria-label="Filter by account status"
                >
                  <option value="all">All accounts</option>
                  <option value="active">Active only</option>
                  <option value="inactive">Disabled only</option>
                </select>
                <span className="pointer-events-none absolute right-3 top-1/2 -translate-y-1/2 text-slate-400 text-xs">▾</span>
              </div>
            )}
            {onCreateNew && (
              <Button onClick={onCreateNew} variant="primary" icon={FaPlus} iconPosition="left" size="md" className="whitespace-nowrap shadow-md shadow-indigo-600/15">
                Add {role || 'user'}
              </Button>
            )}
          </div>
        </div>
        {!loading && users.length > 0 && (
          <p className="mt-3 text-xs font-medium text-slate-500">
            Showing <span className="text-slate-800">{users.length}</span>
            {users.length === 1 ? ' user' : ' users'}
            {searchTerm ? ' matching your search' : ''}
          </p>
        )}
      </div>

      {/* Table */}
      {loading ? (
        <div className="flex flex-col items-center justify-center rounded-2xl border border-slate-200 bg-white py-20 shadow-sm">
          <div className="h-11 w-11 animate-spin rounded-full border-2 border-indigo-600 border-t-transparent" />
          <p className="mt-4 text-sm font-medium text-slate-600">Loading directory…</p>
        </div>
      ) : users.length === 0 ? (
        <div className="rounded-2xl border border-dashed border-slate-200 bg-slate-50/50 px-6 py-16 text-center">
          <FaUsers className="mx-auto text-slate-300 mb-3" size={40} />
          <p className="text-slate-700 font-semibold">
            {searchTerm ? 'No matches' : `No ${role || 'users'} found`}
          </p>
          <p className="mt-1 text-sm text-slate-500 max-w-md mx-auto">
            {searchTerm ? 'Try a different search or clear filters.' : 'Add a user or adjust role filters above.'}
          </p>
        </div>
      ) : (
        <div className="overflow-hidden rounded-2xl border border-slate-200/90 bg-white shadow-sm ring-1 ring-slate-900/5">
          <div className="overflow-x-auto">
            <table className="w-full min-w-[900px] text-left border-collapse">
              <thead>
                <tr className="border-b border-slate-200 bg-gradient-to-b from-slate-50 to-slate-50/80">
                  <th className="px-5 py-4 text-[11px] font-semibold uppercase tracking-wider text-slate-500">
                    User
                  </th>
                  <th className="px-5 py-4 text-[11px] font-semibold uppercase tracking-wider text-slate-500">
                    Contact
                  </th>
                  <th className="px-5 py-4 text-[11px] font-semibold uppercase tracking-wider text-slate-500">
                    Business
                  </th>
                  <th className="px-5 py-4 text-[11px] font-semibold uppercase tracking-wider text-slate-500">
                    Role
                  </th>
                  <th className="px-5 py-4 text-[11px] font-semibold uppercase tracking-wider text-slate-500">
                    Access
                  </th>
                  <th className="px-5 py-4 text-[11px] font-semibold uppercase tracking-wider text-slate-500">
                    Readiness
                  </th>
                  <th className="px-5 py-4 text-center text-[11px] font-semibold uppercase tracking-wider text-slate-500 w-[200px]">
                    Actions
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {users.map((user) => {
                  const userId = user.user_id || user.id;
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
                      className={`group transition-colors hover:bg-indigo-50/40 ${!activeOk ? 'bg-slate-50/90' : ''}`}
                    >
                      <td className="px-5 py-4 align-top">
                        <div className="font-semibold text-slate-900 capitalize tracking-tight">{fullName}</div>
                        <div className="mt-1 font-mono text-xs font-medium text-indigo-600 tabular-nums">
                          {formatUserId(userId)}
                        </div>
                      </td>
                      <td className="px-5 py-4 align-top text-sm text-slate-700">
                        <div className="flex items-start gap-2 max-w-[220px]">
                          <FaEnvelope className="mt-0.5 shrink-0 text-slate-400" size={14} aria-hidden />
                          <span className="break-all leading-snug">{user.email || '—'}</span>
                        </div>
                        <div className="mt-2 flex items-center gap-2 text-slate-600 tabular-nums">
                          <FaPhone className="shrink-0 text-slate-400" size={14} aria-hidden />
                          {user.phone || '—'}
                        </div>
                      </td>
                      <td className="px-5 py-4 align-top text-sm text-slate-700 max-w-[200px]">
                        <div className="flex items-start gap-2">
                          <FaBuilding className="mt-0.5 shrink-0 text-slate-400" size={14} aria-hidden />
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
                          <div className="flex items-center gap-2 text-slate-700" title="KYC">
                            {kycOk ? (
                              <FaCircleCheck className="text-emerald-600 shrink-0" size={14} aria-hidden />
                            ) : kycRejected ? (
                              <FaBan className="text-red-500 shrink-0" size={14} aria-hidden />
                            ) : (
                              <FaClock className="text-amber-500 shrink-0" size={14} aria-hidden />
                            )}
                            <span className="font-medium">
                              KYC {kycLabel}
                            </span>
                          </div>
                          <div className="flex items-center gap-2 text-slate-700" title="MPIN">
                            {mpinOk ? (
                              <FaCircleCheck className="text-emerald-600 shrink-0" size={14} aria-hidden />
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
                            className="inline-flex items-center gap-1.5 rounded-lg border border-slate-200 bg-white px-3 py-2 text-xs font-semibold text-slate-700 shadow-sm transition-all hover:border-indigo-200 hover:bg-indigo-50 hover:text-indigo-900"
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
                                    ? 'border border-amber-200/90 bg-amber-50 text-amber-900 hover:bg-amber-100'
                                    : 'border border-emerald-200/90 bg-emerald-50 text-emerald-900 hover:bg-emerald-100'
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
                                className="inline-flex items-center gap-1.5 rounded-lg border border-red-200/90 bg-red-50 px-3 py-2 text-xs font-semibold text-red-800 shadow-sm transition-all hover:bg-red-100 disabled:opacity-50"
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
