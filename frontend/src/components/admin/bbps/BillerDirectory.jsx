import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import {
  FaArrowsRotate,
  FaCheck,
  FaChevronRight,
  FaCopy,
  FaEye,
  FaEyeSlash,
  FaMagnifyingGlass,
  FaTrash,
  FaXmark,
} from 'react-icons/fa6';
import { bbpsAPI, billAvenueAdminAPI } from '../../../services/api';
import Badge from '../../common/Badge';
import Button from '../../common/Button';
import LoadingSpinner from '../../common/LoadingSpinner';
import Tabs from '../../common/Tabs';

const PAGE_SIZES = [25, 50, 100];

function timeAgo(iso) {
  if (!iso) return 'Never';
  const diff = Date.now() - new Date(iso).getTime();
  const mins = Math.floor(diff / 60000);
  if (mins < 1) return 'Just now';
  if (mins < 60) return `${mins}m ago`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return `${hrs}h ago`;
  const days = Math.floor(hrs / 24);
  if (days < 30) return `${days}d ago`;
  return new Date(iso).toLocaleDateString('en-IN', { day: '2-digit', month: 'short', year: 'numeric' });
}

const CopyId = ({ value }) => {
  const [copied, setCopied] = useState(false);
  return (
    <span className="inline-flex items-center gap-1.5 font-mono text-xs text-slate-600">
      {value}
      <button
        type="button"
        className="text-slate-400 hover:text-blue-600"
        title="Copy biller ID"
        onClick={(e) => {
          e.stopPropagation();
          navigator.clipboard?.writeText(value);
          setCopied(true);
          setTimeout(() => setCopied(false), 1200);
        }}
      >
        {copied ? <FaCheck size={11} className="text-emerald-600" /> : <FaCopy size={11} />}
      </button>
    </span>
  );
};

const MappingBadge = ({ status }) => {
  if (status === 'approved') return <Badge variant="success" size="sm">Mapped</Badge>;
  if (status === 'pending') return <Badge variant="warning" size="sm">Pending</Badge>;
  return <Badge variant="default" size="sm">Unmapped</Badge>;
};

/* ---------------- Quick-view drawer ---------------- */

const BillerDrawer = ({ row, onClose }) => {
  const [detail, setDetail] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!row) return undefined;
    let cancelled = false;
    setLoading(true);
    setDetail(null);
    (async () => {
      const res = await billAvenueAdminAPI.getBillerMasterDetails(row.id);
      if (!cancelled) {
        if (res.success) setDetail(res.data?.biller || null);
        setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [row]);

  if (!row) return null;
  const b = detail || row;
  const inputParams = detail?.input_params || [];
  const paymentModes = detail?.payment_modes || [];
  const channels = detail?.payment_acceptance_matrix?.payment_channels_supported || [];

  return (
    <>
      <div className="fixed inset-0 z-40 bg-slate-900/40" onClick={onClose} />
      <aside className="fixed inset-y-0 right-0 z-50 flex w-full max-w-md flex-col bg-white shadow-2xl">
        <div className="flex items-start justify-between border-b border-slate-200 px-5 py-4">
          <div className="min-w-0">
            <h2 className="truncate text-lg font-bold text-slate-900">{b.biller_name}</h2>
            <div className="mt-1 flex flex-wrap items-center gap-2">
              <CopyId value={b.biller_id} />
              <Badge variant={b.is_active_local ? 'success' : 'default'} size="sm">
                {b.is_active_local ? 'Visible' : 'Hidden'}
              </Badge>
              <Badge variant={String(b.biller_status).toUpperCase() === 'ACTIVE' ? 'success' : 'warning'} size="sm">
                BA: {b.biller_status || '—'}
              </Badge>
            </div>
          </div>
          <button type="button" onClick={onClose} className="rounded-lg p-2 text-slate-400 hover:bg-slate-100 hover:text-slate-700">
            <FaXmark size={16} />
          </button>
        </div>

        <div className="flex-1 space-y-5 overflow-y-auto px-5 py-4">
          {loading ? (
            <div className="flex justify-center py-16">
              <LoadingSpinner size="md" />
            </div>
          ) : (
            <>
              <section>
                <h3 className="text-xs font-semibold uppercase tracking-wide text-slate-500">Overview</h3>
                <dl className="mt-2 grid grid-cols-2 gap-x-4 gap-y-2 text-sm">
                  <div>
                    <dt className="text-xs text-slate-500">Category</dt>
                    <dd className="font-medium text-slate-800">{b.biller_category || '—'}</dd>
                  </div>
                  <div>
                    <dt className="text-xs text-slate-500">Environment</dt>
                    <dd className="font-medium uppercase text-slate-800">{b.environment || '—'}</dd>
                  </div>
                  <div>
                    <dt className="text-xs text-slate-500">Coverage</dt>
                    <dd className="font-medium text-slate-800">{detail?.biller_coverage || '—'}</dd>
                  </div>
                  <div>
                    <dt className="text-xs text-slate-500">Fetch requirement</dt>
                    <dd className="font-medium text-slate-800">{detail?.biller_fetch_requiremet || detail?.biller_fetch_requirement || '—'}</dd>
                  </div>
                  <div>
                    <dt className="text-xs text-slate-500">Last synced</dt>
                    <dd className="font-medium text-slate-800">{timeAgo(b.last_synced_at)}</dd>
                  </div>
                  <div>
                    <dt className="text-xs text-slate-500">Sync status</dt>
                    <dd className="font-medium text-slate-800">{b.last_sync_status || '—'}</dd>
                  </div>
                </dl>
              </section>

              <section>
                <h3 className="text-xs font-semibold uppercase tracking-wide text-slate-500">
                  Input schema ({inputParams.length})
                </h3>
                {inputParams.length === 0 ? (
                  <p className="mt-2 text-sm text-slate-500">No input parameters recorded.</p>
                ) : (
                  <ul className="mt-2 space-y-1.5">
                    {inputParams.slice(0, 8).map((p) => (
                      <li key={p.param_name} className="flex items-center justify-between rounded-lg bg-slate-50 px-3 py-1.5 text-sm">
                        <span className="font-medium text-slate-800">{p.param_name}</span>
                        <span className="text-xs text-slate-500">
                          {p.data_type || 'TEXT'} · {p.is_optional ? 'optional' : 'required'}
                        </span>
                      </li>
                    ))}
                    {inputParams.length > 8 && (
                      <li className="text-xs text-slate-400">+{inputParams.length - 8} more…</li>
                    )}
                  </ul>
                )}
              </section>

              <section>
                <h3 className="text-xs font-semibold uppercase tracking-wide text-slate-500">
                  Payment modes ({paymentModes.length})
                </h3>
                {paymentModes.length === 0 ? (
                  <p className="mt-2 text-sm text-slate-500">No payment mode limits recorded.</p>
                ) : (
                  <div className="mt-2 flex flex-wrap gap-1.5">
                    {paymentModes.map((m) => (
                      <span
                        key={m.payment_mode}
                        className={`rounded-full px-2.5 py-1 text-xs font-medium ${
                          m.is_active ? 'bg-blue-50 text-blue-700' : 'bg-slate-100 text-slate-400 line-through'
                        }`}
                      >
                        {m.payment_mode}
                      </span>
                    ))}
                  </div>
                )}
                {channels.length > 0 && (
                  <p className="mt-2 text-xs text-slate-500">Channels: {channels.join(', ')}</p>
                )}
              </section>
            </>
          )}
        </div>

        <div className="border-t border-slate-200 px-5 py-3">
          <Link
            to={`/admin/bbps-governance/biller/${row.id}`}
            className="flex w-full items-center justify-center gap-2 rounded-lg bg-blue-600 px-4 py-2.5 text-sm font-semibold text-white transition hover:bg-blue-700"
          >
            Open full details
            <FaChevronRight size={12} />
          </Link>
        </div>
      </aside>
    </>
  );
};

/* ---------------- Directory ---------------- */

const BillerDirectory = () => {
  const [searchParams, setSearchParams] = useSearchParams();
  const [env, setEnv] = useState('');
  const [liveMode, setLiveMode] = useState('');
  const [catalogCounts, setCatalogCounts] = useState(null);
  const [categories, setCategories] = useState([]);
  const [totals, setTotals] = useState(null);
  const [category, setCategory] = useState(searchParams.get('category') || '');
  const [q, setQ] = useState('');
  const [qInput, setQInput] = useState('');
  const [active, setActive] = useState('');
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(25);
  const [rows, setRows] = useState([]);
  const [pagination, setPagination] = useState(null);
  const [loadingRows, setLoadingRows] = useState(true);
  const [loadingCats, setLoadingCats] = useState(true);
  const [selected, setSelected] = useState(new Set());
  const [mapStatus, setMapStatus] = useState({});
  const [drawerRow, setDrawerRow] = useState(null);
  const [busy, setBusy] = useState('');
  const [notice, setNotice] = useState(null);
  const [confirmAction, setConfirmAction] = useState(null);
  const debounceRef = useRef(null);

  const showNotice = (type, text) => {
    setNotice({ type, text });
    setTimeout(() => setNotice(null), 6000);
  };

  const loadCategories = useCallback(async (targetEnv) => {
    setLoadingCats(true);
    const res = await billAvenueAdminAPI.getBillerCategoryCounts(targetEnv ? { environment: targetEnv } : {});
    if (res.success) {
      setCategories(res.data?.categories || []);
      setTotals(res.data?.totals || null);
      setLiveMode(res.data?.live_mode || '');
      setCatalogCounts(res.data?.catalog_counts || null);
      if (!targetEnv) setEnv(res.data?.catalog_environment || '');
    }
    setLoadingCats(false);
  }, []);

  const loadRows = useCallback(async (params) => {
    setLoadingRows(true);
    const res = await billAvenueAdminAPI.listBillerMaster(params);
    if (res.success) {
      setRows(res.data?.billers || []);
      setPagination(res.data?.pagination || null);
      if (!params.environment) setEnv(res.data?.catalog_environment || '');
      setCatalogCounts(res.data?.catalog_counts || null);
    }
    setLoadingRows(false);
  }, []);

  useEffect(() => {
    loadCategories('');
    (async () => {
      const res = await billAvenueAdminAPI.listProviderBillerMaps();
      if (res.success) {
        const byBiller = {};
        (res.data?.maps || []).forEach((m) => {
          const key = String(m.biller_id || '');
          if (!key) return;
          const st = m.approval_status || 'pending';
          // approved wins over pending for display
          if (byBiller[key] !== 'approved') byBiller[key] = st;
        });
        setMapStatus(byBiller);
      }
    })();
  }, [loadCategories]);

  useEffect(() => {
    const params = { page, page_size: pageSize };
    if (env) params.environment = env;
    if (category) params.category = category;
    if (q) params.q = q;
    if (active) params.active = active;
    loadRows(params);
    setSelected(new Set());
  }, [env, category, q, active, page, pageSize, loadRows]);

  // Debounced server-side search
  const onSearchChange = (value) => {
    setQInput(value);
    if (debounceRef.current) clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(() => {
      setQ(value.trim());
      setPage(1);
    }, 400);
  };

  const pickCategory = (name) => {
    setCategory(name);
    setPage(1);
    const next = new URLSearchParams(searchParams);
    if (name) next.set('category', name);
    else next.delete('category');
    setSearchParams(next, { replace: true });
  };

  const switchEnv = (nextEnv) => {
    setEnv(nextEnv);
    setCategory('');
    setPage(1);
    loadCategories(nextEnv);
  };

  const toggleRow = (id) => {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const allOnPageSelected = rows.length > 0 && rows.every((r) => selected.has(r.id));
  const toggleAll = () => {
    setSelected((prev) => {
      const next = new Set(prev);
      if (allOnPageSelected) rows.forEach((r) => next.delete(r.id));
      else rows.forEach((r) => next.add(r.id));
      return next;
    });
  };

  const selectedRows = useMemo(() => rows.filter((r) => selected.has(r.id)), [rows, selected]);

  const refreshAfterAction = () => {
    const params = { page, page_size: pageSize };
    if (env) params.environment = env;
    if (category) params.category = category;
    if (q) params.q = q;
    if (active) params.active = active;
    loadRows(params);
    loadCategories(env);
    setSelected(new Set());
  };

  const runBulk = async (action) => {
    const ids = selectedRows.map((r) => r.biller_id);
    const pks = selectedRows.map((r) => r.id);
    if (ids.length === 0) return;
    setBusy(action);
    try {
      if (action === 'sync') {
        const res = await bbpsAPI.syncBillers(ids, env || undefined);
        if (res.success) showNotice('success', res.message || `Sync started for ${ids.length} billers`);
        else showNotice('error', res.error || res.message || 'Sync failed');
      } else if (action === 'enable' || action === 'disable') {
        const fn = action === 'enable' ? billAvenueAdminAPI.enableBillerMaster : billAvenueAdminAPI.disableBillerMaster;
        const results = await Promise.all(pks.map((pk) => fn(pk)));
        const ok = results.filter((r) => r.success).length;
        showNotice(ok === pks.length ? 'success' : 'error', `${ok}/${pks.length} billers ${action}d`);
      } else if (action === 'delete') {
        const res = await billAvenueAdminAPI.bulkDeleteBillerMaster({ environment: env || undefined, billerIds: ids });
        if (res.success) showNotice('success', res.message || `${ids.length} billers deleted`);
        else showNotice('error', res.error || res.message || 'Delete failed');
      }
    } finally {
      setBusy('');
      setConfirmAction(null);
      refreshAfterAction();
    }
  };

  const isProdEnv = String(env).toLowerCase() === 'prod';
  const totalPages = pagination?.total_pages || 1;

  return (
    <div className="space-y-4">
      {isProdEnv && (
        <div className="rounded-lg border border-emerald-300 bg-emerald-50 px-4 py-2 text-xs font-semibold text-emerald-800">
          You are viewing the PRODUCTION catalog. Bulk actions here affect live retailers.
        </div>
      )}

      {notice && (
        <div
          className={`rounded-lg px-4 py-2.5 text-sm font-medium ${
            notice.type === 'success' ? 'bg-emerald-50 text-emerald-800' : 'bg-red-50 text-red-700'
          }`}
        >
          {notice.text}
        </div>
      )}

      <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h2 className="text-lg font-bold text-slate-900">Biller Directory</h2>
          <p className="text-sm text-slate-500">
            {totals ? `${totals.total} billers · ${totals.visible} visible · ${totals.hidden} hidden` : 'Loading catalog…'}
          </p>
        </div>
        <Tabs
          tabs={[
            { id: 'uat', label: 'UAT', count: catalogCounts?.uat ?? undefined },
            { id: 'prod', label: 'PROD', count: catalogCounts?.prod ?? undefined },
          ]}
          active={env || liveMode}
          onChange={switchEnv}
        />
      </div>

      <div className="grid gap-4 lg:grid-cols-[230px_1fr]">
        {/* Category tree */}
        <aside className="h-fit rounded-xl border border-slate-200 bg-white p-2 shadow-sm lg:sticky lg:top-4">
          {loadingCats ? (
            <div className="flex justify-center py-8">
              <LoadingSpinner size="sm" />
            </div>
          ) : (
            <nav className="flex max-h-[70vh] flex-col gap-0.5 overflow-y-auto">
              <button
                type="button"
                onClick={() => pickCategory('')}
                className={`flex items-center justify-between rounded-lg px-3 py-2 text-sm font-medium transition ${
                  !category ? 'bg-blue-600 text-white' : 'text-slate-600 hover:bg-slate-50'
                }`}
              >
                All categories
                <span className={`text-xs font-semibold ${!category ? 'text-blue-100' : 'text-slate-400'}`}>
                  {totals?.total ?? 0}
                </span>
              </button>
              {categories.map((c) => {
                const isActive = category === c.category;
                return (
                  <button
                    key={c.category}
                    type="button"
                    onClick={() => pickCategory(c.category)}
                    className={`flex items-center justify-between gap-2 rounded-lg px-3 py-2 text-left text-sm font-medium transition ${
                      isActive ? 'bg-blue-600 text-white' : 'text-slate-600 hover:bg-slate-50'
                    }`}
                    title={`${c.category}: ${c.visible} visible, ${c.hidden} hidden`}
                  >
                    <span className="truncate">{c.category}</span>
                    <span className={`shrink-0 text-xs font-semibold ${isActive ? 'text-blue-100' : 'text-slate-400'}`}>
                      {c.total}
                    </span>
                  </button>
                );
              })}
            </nav>
          )}
        </aside>

        {/* Table area */}
        <div className="min-w-0 space-y-3">
          {/* Filter bar */}
          <div className="flex flex-wrap items-center gap-2 rounded-xl border border-slate-200 bg-white px-3 py-2.5 shadow-sm">
            <div className="relative min-w-[220px] flex-1">
              <FaMagnifyingGlass className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" size={13} />
              <input
                type="text"
                value={qInput}
                onChange={(e) => onSearchChange(e.target.value)}
                placeholder="Search biller name or ID…"
                className="w-full rounded-lg border border-slate-200 py-2 pl-9 pr-3 text-sm focus:border-blue-400 focus:outline-none focus:ring-2 focus:ring-blue-100"
              />
            </div>
            <select
              value={active}
              onChange={(e) => {
                setActive(e.target.value);
                setPage(1);
              }}
              className="rounded-lg border border-slate-200 px-3 py-2 text-sm focus:border-blue-400 focus:outline-none"
            >
              <option value="">All visibility</option>
              <option value="true">Visible only</option>
              <option value="false">Hidden only</option>
            </select>
            <select
              value={pageSize}
              onChange={(e) => {
                setPageSize(Number(e.target.value));
                setPage(1);
              }}
              className="rounded-lg border border-slate-200 px-3 py-2 text-sm focus:border-blue-400 focus:outline-none"
            >
              {PAGE_SIZES.map((s) => (
                <option key={s} value={s}>
                  {s} / page
                </option>
              ))}
            </select>
            {(category || q || active) && (
              <button
                type="button"
                onClick={() => {
                  pickCategory('');
                  setQ('');
                  setQInput('');
                  setActive('');
                  setPage(1);
                }}
                className="text-sm font-medium text-blue-600 hover:text-blue-800"
              >
                Clear filters
              </button>
            )}
          </div>

          {/* Bulk bar */}
          {selected.size > 0 && (
            <div className="flex flex-wrap items-center gap-2 rounded-xl border border-blue-200 bg-blue-50 px-3 py-2">
              <span className="text-sm font-semibold text-blue-900">{selected.size} selected</span>
              <div className="ml-auto flex flex-wrap gap-2">
                <Button size="sm" variant="outline" onClick={() => runBulk('sync')} disabled={!!busy}>
                  <FaArrowsRotate className="mr-1.5" size={12} />
                  {busy === 'sync' ? 'Syncing…' : 'Sync'}
                </Button>
                <Button size="sm" variant="outline" onClick={() => runBulk('enable')} disabled={!!busy}>
                  <FaEye className="mr-1.5" size={12} />
                  {busy === 'enable' ? 'Enabling…' : 'Enable'}
                </Button>
                <Button size="sm" variant="outline" onClick={() => runBulk('disable')} disabled={!!busy}>
                  <FaEyeSlash className="mr-1.5" size={12} />
                  {busy === 'disable' ? 'Disabling…' : 'Disable'}
                </Button>
                <Button size="sm" variant="danger" onClick={() => setConfirmAction('delete')} disabled={!!busy}>
                  <FaTrash className="mr-1.5" size={12} />
                  Delete
                </Button>
                <Button size="sm" variant="ghost" onClick={() => setSelected(new Set())} disabled={!!busy}>
                  Clear
                </Button>
              </div>
            </div>
          )}

          {/* Table */}
          <div className="overflow-hidden rounded-xl border border-slate-200 bg-white shadow-sm">
            <div className="max-h-[65vh] overflow-auto">
              <table className="min-w-full divide-y divide-slate-200 text-sm">
                <thead className="sticky top-0 z-10 bg-slate-50">
                  <tr>
                    <th className="w-10 px-3 py-2.5">
                      <input type="checkbox" checked={allOnPageSelected} onChange={toggleAll} className="rounded" />
                    </th>
                    <th className="px-3 py-2.5 text-left text-xs font-semibold uppercase tracking-wide text-slate-500">Biller</th>
                    <th className="px-3 py-2.5 text-left text-xs font-semibold uppercase tracking-wide text-slate-500">Biller ID</th>
                    <th className="px-3 py-2.5 text-left text-xs font-semibold uppercase tracking-wide text-slate-500">Category</th>
                    <th className="px-3 py-2.5 text-left text-xs font-semibold uppercase tracking-wide text-slate-500">Mapping</th>
                    <th className="px-3 py-2.5 text-left text-xs font-semibold uppercase tracking-wide text-slate-500">BA status</th>
                    <th className="px-3 py-2.5 text-left text-xs font-semibold uppercase tracking-wide text-slate-500">Visibility</th>
                    <th className="px-3 py-2.5 text-left text-xs font-semibold uppercase tracking-wide text-slate-500">Last sync</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {loadingRows ? (
                    Array.from({ length: 8 }).map((_, i) => (
                      <tr key={i}>
                        <td className="px-3 py-3" colSpan={8}>
                          <div className="h-4 w-full animate-pulse rounded bg-slate-100" />
                        </td>
                      </tr>
                    ))
                  ) : rows.length === 0 ? (
                    <tr>
                      <td colSpan={8} className="px-3 py-14 text-center text-sm text-slate-500">
                        No billers match the current filters.
                      </td>
                    </tr>
                  ) : (
                    rows.map((r) => (
                      <tr
                        key={r.id}
                        onClick={() => setDrawerRow(r)}
                        className="cursor-pointer transition hover:bg-blue-50/40"
                      >
                        <td className="px-3 py-2.5" onClick={(e) => e.stopPropagation()}>
                          <input
                            type="checkbox"
                            checked={selected.has(r.id)}
                            onChange={() => toggleRow(r.id)}
                            className="rounded"
                          />
                        </td>
                        <td className="max-w-[260px] px-3 py-2.5">
                          <div className="truncate font-medium text-slate-800" title={r.biller_name}>
                            {r.biller_name}
                          </div>
                        </td>
                        <td className="px-3 py-2.5 whitespace-nowrap">
                          <CopyId value={r.biller_id} />
                        </td>
                        <td className="max-w-[160px] truncate px-3 py-2.5 text-slate-600" title={r.biller_category}>
                          {r.biller_category || '—'}
                        </td>
                        <td className="px-3 py-2.5">
                          <MappingBadge status={mapStatus[String(r.biller_id)]} />
                        </td>
                        <td className="px-3 py-2.5">
                          <Badge
                            variant={String(r.biller_status).toUpperCase() === 'ACTIVE' ? 'success' : 'warning'}
                            size="sm"
                          >
                            {r.biller_status || '—'}
                          </Badge>
                        </td>
                        <td className="px-3 py-2.5">
                          <Badge variant={r.is_active_local ? 'success' : 'default'} size="sm">
                            {r.is_active_local ? 'Visible' : 'Hidden'}
                          </Badge>
                        </td>
                        <td className="whitespace-nowrap px-3 py-2.5 text-xs text-slate-500">
                          {timeAgo(r.last_synced_at)}
                        </td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>

            {/* Pagination */}
            <div className="flex flex-wrap items-center justify-between gap-2 border-t border-slate-200 px-3 py-2.5">
              <span className="text-xs text-slate-500">
                {pagination
                  ? `Page ${pagination.page} of ${totalPages} · ${pagination.total} billers`
                  : '—'}
              </span>
              <div className="flex gap-1.5">
                <Button size="sm" variant="outline" disabled={page <= 1 || loadingRows} onClick={() => setPage((p) => p - 1)}>
                  Previous
                </Button>
                <Button
                  size="sm"
                  variant="outline"
                  disabled={page >= totalPages || loadingRows}
                  onClick={() => setPage((p) => p + 1)}
                >
                  Next
                </Button>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Delete confirm modal */}
      {confirmAction === 'delete' && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/50 p-4">
          <div className="w-full max-w-md rounded-xl bg-white p-6 shadow-2xl">
            <h3 className="text-lg font-bold text-slate-900">Delete {selected.size} billers?</h3>
            <p className="mt-2 text-sm text-slate-600">
              This removes them from the <strong className="uppercase">{env || liveMode}</strong> catalog. They can be
              restored by re-syncing from BillAvenue.
            </p>
            <div className="mt-5 flex justify-end gap-2">
              <Button variant="outline" onClick={() => setConfirmAction(null)} disabled={busy === 'delete'}>
                Cancel
              </Button>
              <Button variant="danger" onClick={() => runBulk('delete')} disabled={busy === 'delete'}>
                {busy === 'delete' ? 'Deleting…' : 'Delete billers'}
              </Button>
            </div>
          </div>
        </div>
      )}

      <BillerDrawer row={drawerRow} onClose={() => setDrawerRow(null)} />
    </div>
  );
};

export default BillerDirectory;
