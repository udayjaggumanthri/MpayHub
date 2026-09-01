import React, { lazy, Suspense, useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { FaChevronDown, FaChevronUp } from 'react-icons/fa6';
import { bbpsAPI, billAvenueAdminAPI } from '../../../services/api';
import Badge from '../../common/Badge';
import LoadingSpinner from '../../common/LoadingSpinner';
import BbpsAdminTable, { formatHiddenReason } from './BbpsAdminTable';
import CashOnlyImpactModal from './CashOnlyImpactModal';

const BbpsPartnerCatalog = lazy(() => import('./BbpsPartnerCatalog'));
const BillerDirectory = lazy(() => import('./BillerDirectory'));
const BbpsSyncConsole = lazy(() => import('./BbpsSyncConsole'));

const TABS = [
  { id: 'partner', label: 'Partner view' },
  { id: 'mdm', label: 'MDM directory' },
  { id: 'visibility', label: 'Visibility' },
  { id: 'sync', label: 'Sync & import' },
];

const PanelFallback = () => (
  <div className="flex justify-center py-16">
    <LoadingSpinner size="md" />
  </div>
);

const VisibilityPanel = () => {
  const [summary, setSummary] = useState(null);
  const [settings, setSettings] = useState(null);
  const [loading, setLoading] = useState(true);
  const [toggling, setToggling] = useState(false);
  const [previewOpen, setPreviewOpen] = useState(false);
  const [preview, setPreview] = useState(null);
  const [previewLoading, setPreviewLoading] = useState(false);
  const [toast, setToast] = useState('');
  const [hiddenOpen, setHiddenOpen] = useState(false);
  const [hiddenRows, setHiddenRows] = useState([]);
  const [hiddenPagination, setHiddenPagination] = useState(null);
  const [hiddenLoading, setHiddenLoading] = useState(false);
  const [qInput, setQInput] = useState('');
  const [q, setQ] = useState('');
  const [reason, setReason] = useState('');
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(25);
  const debounceRef = useRef(null);

  const load = useCallback(async () => {
    setLoading(true);
    const [sumRes, setRes] = await Promise.all([
      bbpsAPI.getCatalogVisibilitySummary(),
      bbpsAPI.getCatalogUxSettings(),
    ]);
    if (sumRes.success) setSummary(sumRes.data);
    if (setRes.success) setSettings(setRes.data);
    setLoading(false);
  }, []);

  const loadHidden = useCallback(async () => {
    if (!summary?.environment) return;
    setHiddenLoading(true);
    const res = await bbpsAPI.listCatalogHiddenBillers({
      page,
      page_size: pageSize,
      q: q || undefined,
      reason: reason || undefined,
      environment: summary.environment,
    });
    if (res.success) {
      setHiddenRows(res.data?.billers || []);
      setHiddenPagination(res.data?.pagination || null);
    }
    setHiddenLoading(false);
  }, [page, pageSize, q, reason, summary?.environment]);

  useEffect(() => {
    load();
  }, [load]);

  useEffect(() => {
    if (hiddenOpen && summary) loadHidden();
  }, [hiddenOpen, summary, loadHidden]);

  const showToast = (text) => {
    setToast(text);
    setTimeout(() => setToast(''), 6000);
  };

  const requestToggle = async (next) => {
    if (next) {
      setPreviewOpen(true);
      setPreviewLoading(true);
      const res = await bbpsAPI.previewCatalogVisibility({
        environment: summary?.environment,
        cash_only_for_users: true,
      });
      if (res.success) setPreview(res.data);
      setPreviewLoading(false);
      return;
    }
    setToggling(true);
    const res = await bbpsAPI.updateCatalogUxSettings({
      environment: summary?.environment,
      cash_only_for_users: false,
    });
    setToggling(false);
    if (res.success) {
      showToast('Cash-only disabled. Auto-hidden billers were restored.');
      load();
      if (hiddenOpen) loadHidden();
    } else {
      showToast(res.message || 'Failed to update catalog settings');
    }
  };

  const confirmEnable = async () => {
    setToggling(true);
    const res = await bbpsAPI.updateCatalogUxSettings({
      environment: summary?.environment,
      cash_only_for_users: true,
    });
    setToggling(false);
    setPreviewOpen(false);
    if (res.success) {
      const stats = res.data?.apply_stats;
      showToast(`Cash-only enabled. Hidden ${stats?.hidden ?? 0} biller(s).`);
      load();
      if (hiddenOpen) loadHidden();
    } else {
      showToast(res.message || 'Failed to enable cash-only mode');
    }
  };

  const onSearchChange = (value) => {
    setQInput(value);
    if (debounceRef.current) clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(() => {
      setQ(value.trim());
      setPage(1);
    }, 400);
  };

  const hiddenColumns = [
    {
      key: 'biller',
      label: 'Biller',
      render: (row) => (
        <div>
          <div className="font-medium text-slate-900 dark:text-slate-100">{row.biller_name}</div>
          <div className="font-mono text-xs text-slate-500">{row.biller_id}</div>
        </div>
      ),
    },
    { key: 'biller_category', label: 'Category' },
    {
      key: 'hold',
      label: 'Hold',
      render: (row) => (
        <Badge variant={row.local_visibility_hold === 'admin' ? 'warning' : 'default'} size="sm">
          {row.local_visibility_hold || '—'}
        </Badge>
      ),
    },
    {
      key: 'reasons',
      label: 'Reasons',
      render: (row) => (
        <div className="flex flex-wrap gap-1">
          {(row.hidden_reasons || []).map((r) => (
            <Badge key={r} variant="default" size="sm">
              {formatHiddenReason(r)}
            </Badge>
          ))}
        </div>
      ),
    },
  ];

  const liveLabel = summary?.environment === 'prod' ? 'Production' : 'UAT';

  if (loading) {
    return <p className="text-sm text-slate-500">Loading visibility summary…</p>;
  }

  return (
    <div className="space-y-4">
      {toast ? (
        <div className="rounded-lg border border-emerald-200 bg-emerald-50 px-4 py-2 text-sm text-emerald-800 dark:border-emerald-900 dark:bg-emerald-950/40 dark:text-emerald-300">
          {toast}
        </div>
      ) : null}

      <div className="rounded-xl border border-emerald-200 bg-emerald-50/80 p-4 dark:border-emerald-900 dark:bg-emerald-950/30">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <div className="flex items-center gap-2">
              <h3 className="font-semibold text-slate-900 dark:text-slate-100">Cash-only for end users</h3>
              <Badge variant={settings?.cash_only_for_users ? 'success' : 'default'} size="sm">
                {settings?.cash_only_for_users ? 'ACTIVE' : 'OFF'}
              </Badge>
            </div>
            <p className="mt-1 max-w-2xl text-sm text-slate-600 dark:text-slate-400">
              Applies to live partner catalog ({liveLabel}). Users see only AGT + Cash billers; payment method is hidden
              automatically.
            </p>
          </div>
          <label className="inline-flex cursor-pointer items-center gap-2">
            <input
              type="checkbox"
              className="h-5 w-5 rounded border-slate-300"
              checked={!!settings?.cash_only_for_users}
              disabled={toggling}
              onChange={(e) => requestToggle(e.target.checked)}
            />
            <span className="text-sm font-medium text-slate-700 dark:text-slate-300">
              {settings?.cash_only_for_users ? 'Enabled' : 'Disabled'}
            </span>
          </label>
        </div>
      </div>

      <div className="grid gap-3 sm:grid-cols-2">
        <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm dark:border-slate-700 dark:bg-slate-900">
          <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">Partners see</p>
          <p className="mt-1 text-3xl font-bold text-slate-900 dark:text-slate-100">
            {summary?.partner_visible ?? '—'}
          </p>
          <p className="mt-1 text-sm text-slate-500">billers on the live catalog</p>
        </div>
        <button
          type="button"
          onClick={() => setHiddenOpen((v) => !v)}
          className="rounded-xl border border-slate-200 bg-white p-4 text-left shadow-sm transition hover:border-blue-300 dark:border-slate-700 dark:bg-slate-900 dark:hover:border-blue-700"
        >
          <div className="flex items-center justify-between gap-2">
            <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">Hidden from partners</p>
            {hiddenOpen ? <FaChevronUp className="text-slate-400" /> : <FaChevronDown className="text-slate-400" />}
          </div>
          <p className="mt-1 text-3xl font-bold text-slate-900 dark:text-slate-100">
            {summary?.hidden_from_partners ?? '—'}
          </p>
          <p className="mt-1 text-sm text-slate-500">
            {summary?.cash_only_hidden ?? 0} by cash-only policy · {summary?.admin_hidden ?? 0} by admin
          </p>
          <p className="mt-2 text-xs font-medium text-blue-600 dark:text-blue-400">
            {hiddenOpen ? 'Collapse list' : 'Click to expand hidden billers'}
          </p>
        </button>
      </div>

      {hiddenOpen ? (
        <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm dark:border-slate-700 dark:bg-slate-900">
          <BbpsAdminTable
            rows={hiddenRows}
            columns={hiddenColumns}
            loading={hiddenLoading}
            pagination={hiddenPagination}
            onPageChange={setPage}
            pageSize={pageSize}
            onPageSizeChange={(size) => {
              setPageSize(size);
              setPage(1);
            }}
            qInput={qInput}
            onSearchChange={onSearchChange}
            filters={
              <select
                value={reason}
                onChange={(e) => {
                  setReason(e.target.value);
                  setPage(1);
                }}
                className="rounded-lg border border-slate-200 px-3 py-2 text-sm dark:border-slate-700 dark:bg-slate-950"
              >
                <option value="">All reasons</option>
                <option value="cash_only">Cash-only hold</option>
                <option value="admin">Admin hold</option>
              </select>
            }
            emptyMessage="No hidden billers for the current filters."
          />
        </div>
      ) : null}

      <CashOnlyImpactModal
        open={previewOpen}
        preview={preview}
        loading={previewLoading || toggling}
        onCancel={() => setPreviewOpen(false)}
        onConfirm={confirmEnable}
      />
    </div>
  );
};

const BbpsCatalogHub = () => {
  const [searchParams, setSearchParams] = useSearchParams();
  const [liveMode, setLiveMode] = useState('');
  const [catalogCounts, setCatalogCounts] = useState(null);
  const [visSummary, setVisSummary] = useState(null);

  const tab = TABS.some((t) => t.id === searchParams.get('tab')) ? searchParams.get('tab') : 'partner';
  const mdmEnv = searchParams.get('mdmEnv') === 'prod' ? 'prod' : 'uat';

  useEffect(() => {
    let cancelled = false;
    (async () => {
      const [catRes, visRes] = await Promise.all([
        billAvenueAdminAPI.getBillerCategoryCounts(),
        bbpsAPI.getCatalogVisibilitySummary(),
      ]);
      if (cancelled) return;
      if (catRes.success) {
        setLiveMode(catRes.data?.live_mode || '');
        setCatalogCounts(catRes.data?.catalog_counts || null);
      }
      if (visRes.success) setVisSummary(visRes.data);
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  const setTab = (nextTab) => {
    const next = new URLSearchParams(searchParams);
    next.set('tab', nextTab);
    if (nextTab === 'mdm' && !next.get('mdmEnv')) next.set('mdmEnv', 'uat');
    setSearchParams(next, { replace: true });
  };

  const setMdmEnv = (env) => {
    const next = new URLSearchParams(searchParams);
    next.set('tab', 'mdm');
    next.set('mdmEnv', env);
    setSearchParams(next, { replace: true });
  };

  const isProdLive = String(liveMode).toLowerCase() === 'prod';
  const liveLabel = isProdLive ? 'Production' : 'UAT';
  const mdmIsProd = mdmEnv === 'prod';

  const checklist = useMemo(() => {
    const mdmTotal = catalogCounts?.[mdmEnv] ?? visSummary?.mdm_total ?? 0;
    const partnerVisible = visSummary?.partner_visible ?? 0;
    return [
      {
        id: 'sync',
        label: 'Sync MDM',
        done: mdmTotal > 0,
        tab: 'sync',
      },
      {
        id: 'mdm',
        label: 'Review MDM directory',
        done: mdmTotal > 0,
        tab: 'mdm',
      },
      {
        id: 'visibility',
        label: 'Set visibility (cash-only)',
        done: Boolean(visSummary?.cash_only_for_users) || (visSummary?.admin_hidden ?? 0) > 0,
        tab: 'visibility',
      },
      {
        id: 'partner',
        label: 'Verify partner view',
        done: partnerVisible > 0,
        tab: 'partner',
      },
    ];
  }, [catalogCounts, mdmEnv, visSummary]);

  return (
    <div className="space-y-4">
      <div className="sticky top-0 z-10 -mx-1 space-y-3 border-b border-slate-200 bg-slate-50/95 px-1 pb-3 backdrop-blur dark:border-slate-700 dark:bg-slate-800/95">
        <div className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
          <div>
            <nav className="flex flex-wrap items-center gap-1 text-xs text-slate-500 dark:text-slate-400">
              <Link to="/admin/bbps" className="font-medium text-blue-600 hover:text-blue-800 dark:text-blue-400">
                BBPS Console
              </Link>
              <span className="text-slate-300 dark:text-slate-600">/</span>
              <span className="font-medium text-slate-700 dark:text-slate-300">Catalog</span>
            </nav>
            <h2 className="mt-1 text-xl font-bold text-slate-900 dark:text-slate-100">Catalog Hub</h2>
            <p className="text-sm text-slate-500 dark:text-slate-400">
              Partner catalog, MDM directory, visibility, and sync in one workspace.
            </p>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <span
              className={`rounded-full px-3 py-1 text-xs font-semibold ring-1 ${
                isProdLive
                  ? 'bg-emerald-50 text-emerald-800 ring-emerald-300 dark:bg-emerald-950/40 dark:text-emerald-300'
                  : 'bg-amber-50 text-amber-900 ring-amber-300 dark:bg-amber-950/40 dark:text-amber-300'
              }`}
            >
              Live: {liveLabel}
            </span>
            {catalogCounts ? (
              <span className="rounded-full bg-slate-100 px-3 py-1 text-xs font-semibold text-slate-700 ring-1 ring-slate-200 dark:bg-slate-800 dark:text-slate-300 dark:ring-slate-700">
                PROD {catalogCounts.prod ?? 0} · UAT {catalogCounts.uat ?? 0}
              </span>
            ) : null}
            <Link
              to="/admin/bbps/settings"
              className="rounded-lg border border-slate-200 px-3 py-1.5 text-xs font-semibold text-slate-700 hover:bg-white dark:border-slate-700 dark:text-slate-300 dark:hover:bg-slate-900"
            >
              Settings
            </Link>
          </div>
        </div>

        <div className="flex flex-wrap gap-2">
          {checklist.map((item) => (
            <button
              key={item.id}
              type="button"
              onClick={() => setTab(item.tab)}
              className={`inline-flex items-center gap-2 rounded-full px-3 py-1 text-xs font-medium ring-1 transition ${
                item.done
                  ? 'bg-emerald-50 text-emerald-800 ring-emerald-200 dark:bg-emerald-950/30 dark:text-emerald-300 dark:ring-emerald-900'
                  : 'bg-white text-slate-600 ring-slate-200 hover:ring-blue-300 dark:bg-slate-900 dark:text-slate-400 dark:ring-slate-700'
              }`}
            >
              <span
                className={`flex h-4 w-4 items-center justify-center rounded-full text-[10px] font-bold ${
                  item.done ? 'bg-emerald-600 text-white' : 'bg-slate-200 text-slate-600 dark:bg-slate-700 dark:text-slate-300'
                }`}
              >
                {item.done ? '✓' : item.id === 'sync' ? '1' : item.id === 'mdm' ? '2' : item.id === 'visibility' ? '3' : '4'}
              </span>
              {item.label}
            </button>
          ))}
        </div>

        <div className="flex gap-1 overflow-x-auto border-b border-slate-200 dark:border-slate-700">
          {TABS.map((t) => (
            <button
              key={t.id}
              type="button"
              onClick={() => setTab(t.id)}
              className={`whitespace-nowrap border-b-2 px-4 py-2 text-sm font-semibold transition ${
                tab === t.id
                  ? 'border-blue-600 text-blue-700 dark:border-blue-400 dark:text-blue-300'
                  : 'border-transparent text-slate-500 hover:text-slate-800 dark:text-slate-400 dark:hover:text-slate-200'
              }`}
            >
              {t.label}
            </button>
          ))}
        </div>
      </div>

      {tab === 'mdm' ? (
        <div className="space-y-3">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <div className="inline-flex rounded-lg border border-slate-200 bg-white p-0.5 dark:border-slate-700 dark:bg-slate-900">
              {['uat', 'prod'].map((env) => (
                <button
                  key={env}
                  type="button"
                  onClick={() => setMdmEnv(env)}
                  className={`rounded-md px-4 py-1.5 text-sm font-semibold transition ${
                    mdmEnv === env
                      ? env === 'prod'
                        ? 'bg-red-600 text-white'
                        : 'bg-blue-600 text-white'
                      : 'text-slate-600 hover:bg-slate-50 dark:text-slate-400 dark:hover:bg-slate-800'
                  }`}
                >
                  {env === 'prod' ? 'Production' : 'UAT'}
                </button>
              ))}
            </div>
            {mdmIsProd ? (
              <p className="text-xs font-medium text-red-700 dark:text-red-300">
                Production MDM — changes affect live retailer data.
              </p>
            ) : null}
          </div>
          {mdmIsProd ? (
            <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-2 text-sm text-red-800 dark:border-red-900 dark:bg-red-950/30 dark:text-red-300">
              You are editing the Production MDM catalog. Sync, visibility, and delete actions affect live retailer data.
            </div>
          ) : null}
        </div>
      ) : null}

      <Suspense fallback={<PanelFallback />}>
        {tab === 'partner' ? <BbpsPartnerCatalog embedded /> : null}
        {tab === 'mdm' ? <BillerDirectory lockedEnvironment={mdmEnv} embedded /> : null}
        {tab === 'visibility' ? <VisibilityPanel /> : null}
        {tab === 'sync' ? <BbpsSyncConsole embedded /> : null}
      </Suspense>
    </div>
  );
};

export default BbpsCatalogHub;
