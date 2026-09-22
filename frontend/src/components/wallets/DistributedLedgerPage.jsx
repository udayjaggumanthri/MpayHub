import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { Link, useNavigate, useSearchParams } from 'react-router-dom';
import { FiArrowLeft, FiSearch, FiUsers, FiInfo } from 'react-icons/fi';
import { FaNetworkWired } from 'react-icons/fa6';
import { walletsAPI } from '../../services/api';
import { formatCurrency } from '../../utils/formatters';
import ReportPagination from '../common/ReportPagination';

const DEFAULT_PAGE_SIZE = 25;

const DistributedLedgerPage = () => {
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();

  const managerId = searchParams.get('manager') || '';
  const role = searchParams.get('role') || '';
  const searchQ = searchParams.get('q') || '';
  const page = Math.max(1, parseInt(searchParams.get('page') || '1', 10) || 1);
  const directOnly = searchParams.get('direct') === '1';

  const [searchInput, setSearchInput] = useState(searchQ);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [rows, setRows] = useState([]);
  const [total, setTotal] = useState(0);
  const [summary, setSummary] = useState(null);
  const [manager, setManager] = useState(null);
  const [roles, setRoles] = useState([]);
  const [pageSize] = useState(DEFAULT_PAGE_SIZE);

  const isNetworkView = Boolean(managerId);

  const updateParams = useCallback(
    (patch, { replace = false } = {}) => {
      const next = new URLSearchParams(searchParams);
      Object.entries(patch).forEach(([key, value]) => {
        if (value === null || value === undefined || value === '' || value === false) {
          next.delete(key);
        } else {
          next.set(key, String(value));
        }
      });
      setSearchParams(next, { replace });
    },
    [searchParams, setSearchParams]
  );

  const load = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      const params = {
        page,
        page_size: pageSize,
      };
      if (role) params.role = role;
      if (searchQ.trim()) params.search = searchQ.trim();
      if (directOnly) params.direct_only = true;

      const res = isNetworkView
        ? await walletsAPI.getDistributedNetwork(managerId, params)
        : await walletsAPI.getDistributedLedger(params);

      if (!res.success) {
        setRows([]);
        setTotal(0);
        setSummary(null);
        setManager(null);
        setError(res.message || 'Unable to load distributed ledger.');
        return;
      }

      const data = res.data || {};
      setRows(data.users || []);
      setTotal(Number(data.total) || 0);
      setSummary(data.summary || null);
      setManager(data.manager || null);
      setRoles(data.roles || []);

      // If URL has a role that isn't available in this network, clear it.
      if (isNetworkView && role) {
        const allowed = data.roles || data.summary?.available_roles || [];
        const isOperatorRole = role === 'Admin' || role === 'Super Admin';
        if (isOperatorRole || (allowed.length && !allowed.includes(role))) {
          // Keep the request so empty_reason shows once; chips won't offer invalid roles next render.
        }
      }
    } catch (e) {
      setError('Unable to load distributed ledger.');
      setRows([]);
      setTotal(0);
    } finally {
      setLoading(false);
    }
  }, [isNetworkView, managerId, role, searchQ, page, pageSize, directOnly]);

  useEffect(() => {
    load();
  }, [load]);

  useEffect(() => {
    setSearchInput(searchQ);
  }, [searchQ]);

  // When entering network view with Admin/Super Admin filter stuck in URL, reset to All.
  useEffect(() => {
    if (!isNetworkView) return;
    if (role === 'Admin' || role === 'Super Admin') {
      updateParams({ role: null, page: 1 }, { replace: true });
    }
  }, [isNetworkView, role, updateParams]);

  const title = isNetworkView
    ? manager
      ? `Network · ${manager.name}`
      : 'Network ledger'
    : 'Distributed Balance Ledger';

  const subtitle = isNetworkView
    ? manager
      ? `${manager.user_id} · ${manager.role}`
      : 'People managed under this user'
    : 'Channel wallets that make up Distributed Balance. Admin logins share one platform treasury.';

  const headerBalance = isNetworkView
    ? parseFloat(summary?.network_balance || 0) || 0
    : role && summary?.shared_wallet
      ? parseFloat(summary?.treasury_balance || summary?.filtered_balance || 0) || 0
      : role
        ? parseFloat(summary?.filtered_balance || 0) || 0
        : parseFloat(summary?.network_balance || 0) || 0;

  const headerLabel = isNetworkView
    ? 'Network total'
    : role && summary?.shared_wallet
      ? 'Shared platform wallet'
      : role
        ? 'Filtered total'
        : 'Distributed total';

  const roleChips = useMemo(() => {
    const list = roles.length
      ? roles
      : isNetworkView
        ? ['Super Distributor', 'Master Distributor', 'Distributor', 'Retailer']
        : ['Admin', 'Super Distributor', 'Master Distributor', 'Distributor', 'Retailer'];
    return ['', ...list];
  }, [roles, isNetworkView]);

  const applySearch = (e) => {
    e?.preventDefault?.();
    updateParams({ q: searchInput.trim(), page: 1 });
  };

  const openNetwork = (user) => {
    if (!user?.id || !user?.has_network) return;
    navigate(`/wallets/distributed?manager=${user.id}`);
  };

  const openProfile = (user) => {
    if (!user?.id) return;
    navigate(user.profile_path || `/user-management/users/${user.id}`);
  };

  const emptyMessage =
    summary?.empty_reason ||
    (role
      ? `No ${role} users here. Switch to All roles or another filter.`
      : 'No users found for this filter.');

  return (
    <div className="min-h-[calc(100vh-6rem)] bg-slate-50 dark:bg-slate-950">
      <div className="mx-auto w-full max-w-[1400px] space-y-4 px-3 py-4 sm:px-5 lg:px-6">
        {/* Header */}
        <div className="flex flex-col gap-3 rounded-2xl border border-slate-200/90 bg-white p-4 shadow-sm dark:border-slate-700 dark:bg-slate-900 lg:flex-row lg:items-center lg:justify-between lg:p-5">
          <div className="flex min-w-0 items-start gap-3">
            <button
              type="button"
              onClick={() => {
                if (isNetworkView) {
                  navigate('/wallets/distributed');
                } else {
                  navigate('/dashboard');
                }
              }}
              className="mt-0.5 flex h-10 w-10 shrink-0 items-center justify-center rounded-xl border border-slate-200 bg-white text-slate-600 hover:bg-slate-50 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-300"
              aria-label="Back"
            >
              <FiArrowLeft size={16} />
            </button>
            <div className="min-w-0">
              <p className="text-[11px] font-bold uppercase tracking-wider text-cyan-700 dark:text-cyan-400">
                {isNetworkView ? 'Downline network' : 'Distributed Balance'}
              </p>
              <h1 className="truncate text-xl font-bold tracking-tight text-slate-900 dark:text-slate-100 sm:text-2xl">
                {title}
              </h1>
              <p className="mt-0.5 text-sm text-slate-600 dark:text-slate-400">{subtitle}</p>
            </div>
          </div>
          <div className="grid w-full grid-cols-2 gap-2 sm:w-auto sm:min-w-[280px]">
            <div className="rounded-xl border border-cyan-200 bg-cyan-50/80 px-3 py-2.5 dark:border-cyan-900 dark:bg-cyan-950/40">
              <p className="text-[10px] font-bold uppercase tracking-wider text-cyan-800 dark:text-cyan-300">
                {headerLabel}
              </p>
              <p className="mt-0.5 text-lg font-bold tabular-nums text-cyan-950 dark:text-cyan-100">
                {formatCurrency(headerBalance)}
              </p>
            </div>
            <div className="rounded-xl border border-slate-200 bg-slate-50 px-3 py-2.5 dark:border-slate-700 dark:bg-slate-800/60">
              <p className="text-[10px] font-bold uppercase tracking-wider text-slate-500">Users</p>
              <p className="mt-0.5 text-lg font-bold tabular-nums text-slate-900 dark:text-slate-100">
                {summary?.network_user_count ?? summary?.filtered_count ?? total}
              </p>
            </div>
          </div>
        </div>

        {isNetworkView && manager ? (
          <div className="flex flex-col gap-3 rounded-xl border border-slate-200 bg-white px-4 py-3 dark:border-slate-700 dark:bg-slate-900 sm:flex-row sm:items-center sm:justify-between">
            <div className="min-w-0">
              <p className="text-sm text-slate-600 dark:text-slate-400">
                Manager{' '}
                <button
                  type="button"
                  onClick={() => openProfile(manager)}
                  className="font-semibold text-cyan-700 hover:underline dark:text-cyan-400"
                >
                  {manager.name}
                </button>
                <span className="ml-2 font-mono text-xs text-slate-500">
                  {manager.user_id} · {formatCurrency(parseFloat(manager.main_balance) || 0)}
                </span>
              </p>
            </div>
            <div className="flex flex-wrap gap-2">
              <button
                type="button"
                onClick={() => updateParams({ direct: directOnly ? null : '1', page: 1 })}
                className={`rounded-lg border px-3 py-1.5 text-xs font-semibold ${
                  directOnly
                    ? 'border-cyan-600 bg-cyan-600 text-white'
                    : 'border-slate-200 bg-white text-slate-700 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-300'
                }`}
              >
                {directOnly ? 'Direct reports' : 'Full network'}
              </button>
              <button
                type="button"
                onClick={() => openProfile(manager)}
                className="rounded-lg border border-slate-200 bg-white px-3 py-1.5 text-xs font-semibold text-slate-700 hover:bg-slate-50 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-300"
              >
                Open profile
              </button>
            </div>
          </div>
        ) : null}

        {summary?.shared_wallet ? (
          <div className="flex items-start gap-2 rounded-xl border border-violet-200 bg-violet-50 px-4 py-3 text-sm text-violet-900 dark:border-violet-900 dark:bg-violet-950/40 dark:text-violet-200">
            <FiInfo className="mt-0.5 shrink-0" size={16} />
            <p>
              Admin and Super Admin are login accounts for one <strong>shared platform wallet</strong>
              {summary.treasury_balance
                ? ` (${formatCurrency(parseFloat(summary.treasury_balance) || 0)})`
                : ''}
              . They are not part of Distributed Balance and have no channel Network.
            </p>
          </div>
        ) : null}

        {/* Filters + table */}
        <div className="rounded-2xl border border-slate-200/90 bg-white shadow-sm dark:border-slate-700 dark:bg-slate-900">
          <div className="border-b border-slate-100 px-4 py-3 dark:border-slate-800 sm:px-5">
            <div className="mb-3 flex flex-wrap gap-1.5">
              {roleChips.map((r) => {
                const active = (r || '') === (role || '');
                const label = r || 'All roles';
                return (
                  <button
                    key={label}
                    type="button"
                    onClick={() => updateParams({ role: r || null, page: 1 })}
                    className={`rounded-full border px-3 py-1.5 text-xs font-semibold transition ${
                      active
                        ? 'border-cyan-600 bg-cyan-600 text-white shadow-sm'
                        : 'border-slate-200 bg-white text-slate-700 hover:border-cyan-400 dark:border-slate-600 dark:bg-slate-800 dark:text-slate-200 dark:hover:border-cyan-500'
                    }`}
                  >
                    {label}
                  </button>
                );
              })}
            </div>

            <form onSubmit={applySearch} className="flex flex-col gap-2 sm:flex-row">
              <div className="relative flex-1">
                <FiSearch
                  className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-slate-400"
                  size={16}
                />
                <input
                  type="search"
                  value={searchInput}
                  onChange={(e) => setSearchInput(e.target.value)}
                  placeholder="Search ID, name, mobile, email…"
                  className="w-full rounded-xl border border-slate-200 bg-white py-2 pl-10 pr-3 text-sm text-slate-900 outline-none ring-cyan-500/30 focus:ring-2 dark:border-slate-600 dark:bg-slate-950 dark:text-slate-100"
                />
              </div>
              <button
                type="submit"
                className="rounded-xl bg-cyan-600 px-4 py-2 text-sm font-semibold text-white hover:bg-cyan-700"
              >
                Search
              </button>
              {(role || searchQ) && (
                <button
                  type="button"
                  onClick={() => {
                    setSearchInput('');
                    updateParams({ role: null, q: null, page: 1 });
                  }}
                  className="rounded-xl border border-slate-200 px-4 py-2 text-sm font-semibold text-slate-600 hover:bg-slate-50 dark:border-slate-600 dark:text-slate-300 dark:hover:bg-slate-800"
                >
                  Clear
                </button>
              )}
            </form>

            {summary?.by_role && Object.keys(summary.by_role).length > 0 ? (
              <div className="mt-3 flex flex-wrap gap-1.5">
                {Object.entries(summary.by_role).map(([r, info]) => (
                  <button
                    key={r}
                    type="button"
                    onClick={() => updateParams({ role: r, page: 1 })}
                    className="inline-flex items-center gap-2 rounded-lg bg-slate-50 px-2.5 py-1 text-xs text-slate-600 ring-1 ring-slate-200 hover:ring-cyan-400 dark:bg-slate-800 dark:text-slate-300 dark:ring-slate-700"
                  >
                    <span className="font-semibold">{r}</span>
                    <span className="tabular-nums">{info.count}</span>
                    <span className="tabular-nums text-cyan-700 dark:text-cyan-400">
                      {formatCurrency(parseFloat(info.balance) || 0)}
                    </span>
                  </button>
                ))}
              </div>
            ) : null}
          </div>

          {error ? (
            <div className="mx-4 mt-3 rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700 dark:border-red-900 dark:bg-red-950/40 dark:text-red-300 sm:mx-5">
              {error}
            </div>
          ) : null}

          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-slate-200 text-sm dark:divide-slate-700">
              <thead className="bg-slate-50/90 dark:bg-slate-800/80">
                <tr>
                  <th className="px-4 py-2.5 text-left text-[11px] font-semibold uppercase tracking-wide text-slate-500 sm:px-5">
                    User ID
                  </th>
                  <th className="px-4 py-2.5 text-left text-[11px] font-semibold uppercase tracking-wide text-slate-500 sm:px-5">
                    Name
                  </th>
                  <th className="px-4 py-2.5 text-left text-[11px] font-semibold uppercase tracking-wide text-slate-500 sm:px-5">
                    Role
                  </th>
                  <th className="px-4 py-2.5 text-right text-[11px] font-semibold uppercase tracking-wide text-slate-500 sm:px-5">
                    Main balance
                  </th>
                  <th className="px-4 py-2.5 text-right text-[11px] font-semibold uppercase tracking-wide text-slate-500 sm:px-5">
                    Actions
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
                {loading ? (
                  <tr>
                    <td colSpan={5} className="px-5 py-16 text-center text-slate-500">
                      Loading…
                    </td>
                  </tr>
                ) : rows.length === 0 ? (
                  <tr>
                    <td colSpan={5} className="px-5 py-14 text-center">
                      <p className="text-sm font-medium text-slate-700 dark:text-slate-300">{emptyMessage}</p>
                      {role ? (
                        <button
                          type="button"
                          onClick={() => updateParams({ role: null, page: 1 })}
                          className="mt-3 rounded-lg bg-cyan-600 px-3 py-1.5 text-xs font-semibold text-white hover:bg-cyan-700"
                        >
                          Show all roles
                        </button>
                      ) : null}
                    </td>
                  </tr>
                ) : (
                  rows.map((u) => (
                    <tr key={u.id} className="hover:bg-cyan-50/50 dark:hover:bg-cyan-950/20">
                      <td className="whitespace-nowrap px-4 py-2.5 font-mono text-xs text-slate-600 dark:text-slate-400 sm:px-5">
                        {u.user_id || '—'}
                      </td>
                      <td className="px-4 py-2.5 sm:px-5">
                        <button
                          type="button"
                          onClick={() => openProfile(u)}
                          className="text-left font-semibold text-cyan-800 hover:underline dark:text-cyan-300"
                        >
                          {u.name || '—'}
                        </button>
                        {u.phone ? (
                          <p className="mt-0.5 font-mono text-[11px] text-slate-400">{u.phone}</p>
                        ) : null}
                        {u.shared_wallet ? (
                          <span className="mt-1 inline-flex rounded bg-violet-100 px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-violet-800 dark:bg-violet-900/50 dark:text-violet-200">
                            Shared wallet
                          </span>
                        ) : null}
                      </td>
                      <td className="px-4 py-2.5 sm:px-5">
                        <span className="inline-flex rounded-md bg-slate-100 px-2 py-0.5 text-xs font-medium text-slate-700 dark:bg-slate-800 dark:text-slate-300">
                          {u.role || '—'}
                        </span>
                      </td>
                      <td className="whitespace-nowrap px-4 py-2.5 text-right font-semibold tabular-nums text-slate-900 dark:text-slate-100 sm:px-5">
                        {formatCurrency(parseFloat(u.main_balance) || 0)}
                      </td>
                      <td className="px-4 py-2.5 sm:px-5">
                        <div className="flex flex-wrap items-center justify-end gap-1.5">
                          <Link
                            to={u.profile_path || `/user-management/users/${u.id}`}
                            className="rounded-lg border border-slate-200 px-2.5 py-1 text-xs font-semibold text-slate-700 hover:bg-slate-50 dark:border-slate-600 dark:text-slate-300 dark:hover:bg-slate-800"
                          >
                            Profile
                          </Link>
                          {u.has_network ? (
                            <button
                              type="button"
                              onClick={() => openNetwork(u)}
                              className="inline-flex items-center gap-1 rounded-lg bg-cyan-600 px-2.5 py-1 text-xs font-semibold text-white hover:bg-cyan-700"
                            >
                              <FiUsers size={12} />
                              Network
                            </button>
                          ) : null}
                        </div>
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>

          <div className="border-t border-slate-100 px-4 py-2 dark:border-slate-800 sm:px-5">
            <ReportPagination
              page={page}
              pageSize={pageSize}
              total={total}
              onPageChange={(p) => updateParams({ page: p })}
            />
          </div>
        </div>

        <p className="flex items-center gap-2 px-1 text-xs text-slate-500 dark:text-slate-400">
          <FaNetworkWired className="shrink-0 text-cyan-600" />
          Click a name for User Management. Network is only for Super Distributor, Master Distributor,
          and Distributor.
        </p>
      </div>
    </div>
  );
};

export default DistributedLedgerPage;
