import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { bbpsAPI, billAvenueAdminAPI } from '../../services/api';

const TABS = [
  { id: 'readiness', label: 'Setup & Sync' },
  { id: 'directory', label: 'Biller Directory' },
];

const emptyMapForm = { provider: '', biller_master: '', priority: 0 };

const toLower = (value) => String(value || '').toLowerCase();
const toTitle = (value) => String(value || '').replace(/[_-]+/g, ' ').replace(/\b\w/g, (m) => m.toUpperCase());

const BbpsProviderGovernance = () => {
  const [activeTab, setActiveTab] = useState('readiness');
  const [catalogEnv, setCatalogEnv] = useState('uat'); // which catalog admin is browsing
  const [liveMode, setLiveMode] = useState('uat');
  const [catalogCounts, setCatalogCounts] = useState({ uat: 0, prod: 0 });
  const [loading, setLoading] = useState(false);
  const [syncing, setSyncing] = useState(false);
  const [switchingLive, setSwitchingLive] = useState(false);
  const [error, setError] = useState('');
  const [info, setInfo] = useState('');
  const [syncDiagnostics, setSyncDiagnostics] = useState(null);
  const [syncUsage, setSyncUsage] = useState(null);
  const [syncUsageHistory, setSyncUsageHistory] = useState([]);
  const [syncInputIds, setSyncInputIds] = useState('');
  const [syncInvalidIds, setSyncInvalidIds] = useState([]);
  const [opsSummary, setOpsSummary] = useState(null);
  const [observability, setObservability] = useState(null);
  const [categories, setCategories] = useState([]);
  const [providers, setProviders] = useState([]);
  const [maps, setMaps] = useState([]);
  const [audits, setAudits] = useState([]);
  const [billerMaster, setBillerMaster] = useState([]);
  const [categoryForm, setCategoryForm] = useState({ code: '', name: '', description: '' });
  const [providerForm, setProviderForm] = useState({
    code: '',
    name: '',
    provider_type: 'operator',
    category: '',
    priority: 0,
  });
  const [mapForm, setMapForm] = useState(emptyMapForm);
  const [mapSearch, setMapSearch] = useState('');
  const [directorySearch, setDirectorySearch] = useState('');
  const [directoryCategory, setDirectoryCategory] = useState('all');
  const [directoryPage, setDirectoryPage] = useState(1);
  const [directoryPageSize, setDirectoryPageSize] = useState(25);
  const [directoryPagination, setDirectoryPagination] = useState({ page: 1, page_size: 25, total: 0, total_pages: 1 });
  const [selectedDirectoryBillerIds, setSelectedDirectoryBillerIds] = useState([]);
  const [mdmImportJob, setMdmImportJob] = useState(null);
  const [mdmImportUploading, setMdmImportUploading] = useState(false);
  const [mdmImportProcessing, setMdmImportProcessing] = useState(false);
  const [mdmImportDestroying, setMdmImportDestroying] = useState(false);
  const [mdmImportFileName, setMdmImportFileName] = useState('');
  const navigate = useNavigate();

  const visibleServicesCount = useMemo(
    () => billerMaster.filter((b) => b.is_active_local && !b.soft_deleted_at).length,
    [billerMaster],
  );

  const selectedProvider = useMemo(
    () => providers.find((p) => String(p.id) === String(mapForm.provider)),
    [providers, mapForm.provider],
  );

  const providerScopedBillers = useMemo(() => {
    if (!selectedProvider) return billerMaster;
    const categoryCode = toLower(selectedProvider.category_code);
    return billerMaster.filter((b) => toLower(b.biller_category) === categoryCode);
  }, [billerMaster, selectedProvider]);

  

  const filteredOpsMaps = useMemo(() => {
    const q = toLower(mapSearch.trim());
    if (!q) return maps;
    return maps.filter((m) => (
      toLower(m.provider_name).includes(q)
      || toLower(m.category_name || m.category_code).includes(q)
      || toLower(m.biller_name).includes(q)
      || toLower(m.biller_id).includes(q)
    ));
  }, [maps, mapSearch]);

  const directoryCategories = useMemo(() => {
    const uniq = new Set();
    billerMaster.forEach((b) => {
      const c = String(b.biller_category || '').trim();
      if (c) uniq.add(c);
    });
    return Array.from(uniq).sort((a, b) => a.localeCompare(b));
  }, [billerMaster]);

  const filteredDirectoryBillers = billerMaster;
  const allVisibleDirectoryIds = useMemo(
    () => filteredDirectoryBillers.map((b) => String(b.biller_id || '').trim()).filter(Boolean),
    [filteredDirectoryBillers],
  );

  const uatSteps = useMemo(() => [
    {
      id: 'sync',
      label: 'Run biller sync',
      done: Number(syncDiagnostics?.synced || billerMaster.length || 0) > 0,
      tab: 'readiness',
    },
    {
      id: 'directory',
      label: 'Review billers and service inputs',
      done: billerMaster.length > 0,
      tab: 'directory',
    },
  ], [billerMaster.length, syncDiagnostics]);

  const loadAll = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      const [
        catRes,
        provRes,
        mapRes,
        auditRes,
        billerRes,
        opsRes,
        obsRes,
        syncUsageRes,
        syncHistoryRes,
      ] = await Promise.all([
        billAvenueAdminAPI.listServiceCategories(),
        billAvenueAdminAPI.listServiceProviders(),
        billAvenueAdminAPI.listProviderBillerMaps(),
        billAvenueAdminAPI.listCommissionAudit(),
        billAvenueAdminAPI.listBillerMaster({
          environment: catalogEnv,
          q: directorySearch || undefined,
          category: directoryCategory !== 'all' ? directoryCategory : undefined,
          page: directoryPage,
          page_size: directoryPageSize,
        }),
        billAvenueAdminAPI.getGovernanceOpsSummary(),
        billAvenueAdminAPI.getGovernanceObservability(),
        bbpsAPI.getSyncUsageToday(catalogEnv),
        bbpsAPI.getSyncUsageHistory(),
      ]);
      setCategories(catRes.data?.categories || []);
      setProviders(provRes.data?.providers || []);
      setMaps(mapRes.data?.maps || []);
      setAudits(auditRes.data?.audits || []);
      setBillerMaster(billerRes.data?.billers || []);
      setDirectoryPagination(billerRes.data?.pagination || { page: 1, page_size: 25, total: 0, total_pages: 1 });
      setOpsSummary(opsRes.data || null);
      setObservability(obsRes.data || null);
      const quota = syncUsageRes.data || billerRes.data?.quota || null;
      setSyncUsage(quota);
      const nextLive = (billerRes.data?.live_mode || quota?.live_mode || 'uat').toString().toLowerCase();
      setLiveMode(nextLive === 'prod' ? 'prod' : 'uat');
      setCatalogCounts(billerRes.data?.catalog_counts || quota?.catalog_counts || { uat: 0, prod: 0 });
      setSyncUsageHistory(syncHistoryRes.data?.history || []);
    } catch (e) {
      setError('Failed to load governance data.');
    } finally {
      setLoading(false);
    }
  }, [catalogEnv, directoryCategory, directoryPage, directoryPageSize, directorySearch]);

  useEffect(() => {
    loadAll();
  }, [loadAll]);

  useEffect(() => {
    const visibleSet = new Set(allVisibleDirectoryIds);
    setSelectedDirectoryBillerIds((prev) => prev.filter((id) => visibleSet.has(id)));
  }, [allVisibleDirectoryIds]);

  const setPartnerLive = async (mode) => {
    if (mode === liveMode) return;
    const label = mode === 'prod' ? 'Production' : 'UAT';
    if (mode === 'prod') {
      const ok = window.confirm('Switch partners to Production credentials and catalog?');
      if (!ok) return;
    }
    setSwitchingLive(true);
    setError('');
    setInfo('');
    const res = await billAvenueAdminAPI.activateLiveEnvironment(mode);
    if (!res.success) {
      setError(res.message || `Failed to switch live environment to ${label}`);
      setSwitchingLive(false);
      return;
    }
    setLiveMode(mode);
    setInfo(`Partners now use ${label}.`);
    setSwitchingLive(false);
    await loadAll();
  };

  const selectCatalogEnv = (env) => {
    setCatalogEnv(env);
    setDirectoryPage(1);
    setSelectedDirectoryBillerIds([]);
    setMdmImportJob(null);
    setMdmImportFileName('');
    setInfo('');
    setError('');
  };

  const refreshMdmImportJob = useCallback(async (jobId) => {
    if (!jobId) return null;
    const res = await bbpsAPI.getMdmImportJob(jobId);
    if (res.success && res.data?.job) {
      setMdmImportJob(res.data.job);
      if (res.data.job.quota) setSyncUsage(res.data.job.quota);
      return res.data.job;
    }
    return null;
  }, []);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      const res = await bbpsAPI.listMdmImportJobs(catalogEnv);
      if (cancelled || !res.success) return;
      const jobs = res.data?.jobs || [];
      if (jobs.length) setMdmImportJob(jobs[0]);
      if (res.data?.quota) setSyncUsage(res.data.quota);
    })();
    return () => { cancelled = true; };
  }, [catalogEnv]);

  useEffect(() => {
    const job = mdmImportJob;
    if (!job?.id) return undefined;
    const active = (job.status === 'processing' || job.status === 'partial' || job.status === 'queued')
      && Number(job.pending_ids || 0) > 0;
    if (!active) return undefined;
    const timer = setInterval(() => {
      refreshMdmImportJob(job.id);
    }, 8000);
    return () => clearInterval(timer);
  }, [mdmImportJob, refreshMdmImportJob]);

  const uploadMdmExcel = async (event) => {
    const file = event.target.files?.[0];
    event.target.value = '';
    if (!file) return;
    setMdmImportUploading(true);
    setError('');
    setInfo('');
    setMdmImportFileName(file.name || '');
    const res = await bbpsAPI.uploadMdmImport(file, catalogEnv, { autoDrain: true });
    setMdmImportUploading(false);
    if (!res.success) {
      setError(res.message || 'Excel MDM import failed');
      return;
    }
    const job = res.data?.job || null;
    setMdmImportJob(job);
    if (res.data?.quota) setSyncUsage(res.data.quota);
    setInfo(res.message || `Queued Excel import for ${catalogEnv.toUpperCase()}.`);
    await loadAll();
  };

  const processMdmImportRemaining = async () => {
    if (!mdmImportJob?.id) return;
    setMdmImportProcessing(true);
    setError('');
    setInfo('');
    const res = await bbpsAPI.processMdmImportJob(mdmImportJob.id);
    setMdmImportProcessing(false);
    if (!res.success) {
      setError(res.message || 'Failed to process remaining MDM import');
      return;
    }
    if (res.data?.job) setMdmImportJob(res.data.job);
    if (res.data?.drain?.quota) setSyncUsage(res.data.drain.quota);
    setInfo(res.message || 'Processed remaining MDM import batches for today.');
    await loadAll();
  };

  const destroyMdmImportJob = async () => {
    if (!mdmImportJob?.id) return;
    const jobId = mdmImportJob.id;
    const ok = window.confirm(
      `Destroy MDM import Job #${jobId}?\n\n`
      + `This stops processing permanently.\n`
      + `Pending IDs (${mdmImportJob.pending_ids || 0}) will not be synced.\n`
      + `Already synced billers stay in the catalog.`,
    );
    if (!ok) return;
    setMdmImportDestroying(true);
    setError('');
    setInfo('');
    const res = await bbpsAPI.destroyMdmImportJob(jobId);
    setMdmImportDestroying(false);
    if (!res.success) {
      setError(res.message || 'Failed to destroy MDM import job');
      return;
    }
    setMdmImportJob(null);
    setMdmImportFileName('');
    const list = await bbpsAPI.listMdmImportJobs(catalogEnv);
    if (list.success) {
      const jobs = list.data?.jobs || [];
      setMdmImportJob(jobs[0] || null);
      if (list.data?.quota) setSyncUsage(list.data.quota);
    }
    setInfo(res.message || `Import job #${jobId} destroyed.`);
  };

  const runSync = async () => {
    setSyncing(true);
    setError('');
    setInfo('');
    try {
      const parsed = syncInputIds.split(/[\s,\n]+/).map((x) => x.trim()).filter(Boolean);
      const validRe = /^[A-Za-z0-9\-_]+$/;
      const invalid = parsed.filter((x) => !validRe.test(x));
      if (invalid.length) {
        setSyncInvalidIds(invalid.slice(0, 20));
        setError(`Invalid biller ID format for ${invalid.length} entr${invalid.length > 1 ? 'ies' : 'y'}. Use only letters, numbers, '-' and '_'.`);
        setSyncing(false);
        return;
      }
      const ids = [...new Set(parsed)];
      if (parsed.length && ids.length === 0) {
        setError('No valid biller IDs found in input.');
        setSyncing(false);
        return;
      }
      if (ids.length > 2000) {
        setError('Maximum 2000 biller IDs are allowed per sync call.');
        setSyncing(false);
        return;
      }
      setSyncInvalidIds([]);
      const res = await bbpsAPI.syncBillers(ids, catalogEnv);
      if (!res.success) {
        const code = String(res.data?.billavenue_code || '').trim();
        if (code === '001' || code === '205' || code === 'PARSE' || code === '202') {
          const cached = Number(res.data?.mdm_cached_count || 0);
          const hint = String(res.data?.hint || '').trim();
          setInfo(
            [
              `Live BillAvenue sync is temporarily unavailable (code=${code}).`,
              hint,
              cached > 0 ? `Continuing with ${cached} cached ${(res.data?.quota?.environment || 'live').toUpperCase()} biller(s).` : '',
              `UAT and Production catalogs stay separate.`,
            ].filter(Boolean).join(' '),
          );
          setSyncDiagnostics(res.data || null);
          await loadAll();
          return;
        }
        const fieldErrors = Array.isArray(res.errors) ? res.errors.join(' | ') : '';
        const hint = res.data?.actionable_hint ? ` ${res.data.actionable_hint}` : '';
        setError(`${res.message || 'Sync failed'}${hint}${fieldErrors ? ` Details: ${fieldErrors}` : ''}`);
        return;
      }
      setSyncDiagnostics(res.data || null);
      setSyncInputIds('');
      setInfo(`Biller sync completed for ${catalogEnv.toUpperCase()} catalog only.`);
      await loadAll();
    } catch (e) {
      setError('Failed to run biller sync. Please retry.');
    } finally {
      setSyncing(false);
    }
  };

  const refreshCache = async () => {
    setError('');
    const out = await billAvenueAdminAPI.refreshProviderCache({});
    if (!out.success) {
      setError(out.message || 'Cache refresh failed');
      return;
    }
    setInfo('Provider cache refreshed.');
    loadAll();
  };

  

  const saveCategory = async (e) => {
    e.preventDefault();
    setError('');
    const out = await billAvenueAdminAPI.saveServiceCategory(categoryForm);
    if (!out.success) return setError(out.message || 'Failed to save category');
    setInfo('Category saved.');
    setCategoryForm({ code: '', name: '', description: '' });
    loadAll();
  };

  const saveProvider = async (e) => {
    e.preventDefault();
    setError('');
    const out = await billAvenueAdminAPI.saveServiceProvider(providerForm);
    if (!out.success) return setError(out.message || 'Failed to save provider');
    setInfo('Provider saved.');
    setProviderForm({ code: '', name: '', provider_type: 'operator', category: '', priority: 0 });
    loadAll();
  };

  const saveMap = async (e) => {
    e.preventDefault();
    setError('');
    const out = await billAvenueAdminAPI.saveProviderBillerMap(mapForm);
    if (!out.success) return setError(out.message || 'Failed to save map');
    setInfo(mapForm.id ? 'Map updated.' : 'Map saved.');
    setMapForm(emptyMapForm);
    loadAll();
  };

  const editMap = (m) => {
    setMapForm({
      id: m.id,
      provider: m.provider,
      biller_master: m.biller_master,
      priority: m.priority || 0,
    });
    setActiveTab('operations');
  };

  const openDirectoryBiller = (biller) => navigate(`/admin/bbps-governance/biller/${biller.id}`);

  const toggleDirectoryRowSelection = (billerId) => {
    const bid = String(billerId || '').trim();
    if (!bid) return;
    setSelectedDirectoryBillerIds((prev) => (
      prev.includes(bid) ? prev.filter((x) => x !== bid) : [...prev, bid]
    ));
  };

  const toggleSelectAllDirectoryRows = () => {
    const all = allVisibleDirectoryIds;
    if (!all.length) return;
    setSelectedDirectoryBillerIds((prev) => (
      prev.length === all.length ? [] : all
    ));
  };

  const syncSelectedDirectoryBillers = async () => {
    const ids = selectedDirectoryBillerIds.filter(Boolean);
    if (ids.length < 1) {
      setError('Select at least 1 biller ID to sync.');
      return;
    }
    const remainingCalls = Number(syncUsage?.remaining_calls_today ?? 0);
    if (remainingCalls < 1) {
      setError('No MDM sync calls remaining today for this environment.');
      return;
    }
    const batchSize = 2000;
    const maxIdsToday = remainingCalls * batchSize;
    const queue = ids.slice(0, maxIdsToday);
    const skipped = ids.length - queue.length;

    setSyncing(true);
    setError('');
    setInfo('');
    let syncedCount = 0;
    let lastData = null;
    let failedMessage = '';

    for (let i = 0; i < queue.length; i += batchSize) {
      const chunk = queue.slice(i, i + batchSize);
      const res = await bbpsAPI.syncBillers(chunk, catalogEnv);
      if (!res.success) {
        const details = Array.isArray(res.errors) && res.errors.length ? ` Details: ${res.errors.join(' | ')}` : '';
        const hint = res.data?.actionable_hint ? ` ${res.data.actionable_hint}` : '';
        failedMessage = `${res.message || 'Failed to sync selected billers.'}${hint}${details}`;
        if (res.data?.remaining_calls_today != null || res.data?.quota) {
          setSyncUsage(res.data.quota || res.data);
        }
        break;
      }
      syncedCount += chunk.length;
      lastData = res.data || null;
      if (res.data?.quota) setSyncUsage(res.data.quota);
    }

    setSyncing(false);
    if (failedMessage && syncedCount === 0) {
      setError(failedMessage);
      return;
    }
    if (lastData) setSyncDiagnostics(lastData);
    const parts = [
      `Synced ${syncedCount} selected biller ID(s) into ${catalogEnv.toUpperCase()} catalog`,
    ];
    if (failedMessage) parts.push(`stopped early: ${failedMessage}`);
    if (skipped > 0) {
      parts.push(`${skipped} left unsynced (daily MDM call quota). Use Process remaining / try again tomorrow.`);
    }
    setInfo(`${parts.join(' — ')}`);
    await loadAll();
  };

  const toggleLocalBillerState = async (biller) => {
    const call = biller.is_active_local
      ? billAvenueAdminAPI.disableBillerMaster(biller.id)
      : billAvenueAdminAPI.enableBillerMaster(biller.id);
    const out = await call;
    if (!out.success) {
      setError(out.message || 'Failed to update biller state');
      return;
    }
    setInfo(`Biller ${biller.is_active_local ? 'disabled' : 'enabled'}.`);
    loadAll();
  };

  const softDeleteBiller = async (biller) => {
    const name = biller.biller_name || biller.biller_id || 'this biller';
    const ok = window.confirm(`Delete ${name} from the ${catalogEnv.toUpperCase()} catalog?`);
    if (!ok) return;
    setError('');
    setInfo('');
    if (!biller?.id) {
      setError('Cannot delete: missing biller record id.');
      return;
    }
    const out = await billAvenueAdminAPI.deleteBillerMaster(biller.id);
    if (!out.success) {
      setError(out.message || 'Failed to delete biller');
      return;
    }
    setSelectedDirectoryBillerIds((prev) => prev.filter((id) => id !== String(biller.biller_id || '').trim()));
    setInfo(`Deleted ${name} from ${catalogEnv.toUpperCase()} catalog.`);
    await loadAll();
  };

  const deleteSelectedDirectoryBillers = async () => {
    const ids = selectedDirectoryBillerIds.filter(Boolean);
    if (!ids.length) {
      setError('Select at least one biller to delete.');
      return;
    }
    const ok = window.confirm(
      `Delete ${ids.length} selected biller(s) from the ${catalogEnv.toUpperCase()} catalog only?`,
    );
    if (!ok) return;
    setError('');
    setInfo('');
    const out = await billAvenueAdminAPI.bulkDeleteBillerMaster({
      environment: catalogEnv,
      billerIds: ids,
    });
    if (!out.success) {
      setError(out.message || 'Failed to delete selected billers');
      return;
    }
    setSelectedDirectoryBillerIds([]);
    setInfo(`Deleted ${out.data?.deleted_count || ids.length} biller(s) from ${catalogEnv.toUpperCase()}.`);
    await loadAll();
  };

  const clearAllBillers = async () => {
    const envLabel = catalogEnv.toUpperCase();
    const ok = window.confirm(
      `This will remove all ${envLabel} billers from the ${envLabel} catalog only. The other environment is preserved. Continue?`,
    );
    if (!ok) return;
    setError('');
    const out = await billAvenueAdminAPI.clearAllBillerMaster(catalogEnv);
    if (!out.success) {
      setError(out.message || 'Failed to clear billers');
      return;
    }
    setInfo(`Removed ${out.data?.cleared_count || 0} ${(out.data?.environment || envLabel).toUpperCase()} billers.`);
    setDirectoryPage(1);
    loadAll();
  };

  const mapCount = visibleServicesCount;
  const hiddenServicesCount = Math.max(0, billerMaster.length - visibleServicesCount);
  const syncUsagePercent = syncUsage?.max_calls_per_day
    ? Math.min(100, Math.round(((syncUsage?.used_calls_today || 0) / syncUsage.max_calls_per_day) * 100))
    : 0;

  return (
    <div className="max-w-7xl mx-auto space-y-4">
      <div className="bg-white rounded-xl border border-gray-200 p-5 space-y-4">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <h1 className="text-xl font-semibold text-gray-900">Provider Governance</h1>
            <p className="text-sm text-gray-500 mt-0.5">Manage UAT and Production biller catalogs separately.</p>
          </div>
          <Link className="text-sm text-blue-700 underline" to="/admin/billavenue-settings">
            BillAvenue credentials
          </Link>
        </div>

        <div className="rounded-lg border border-slate-200 bg-slate-50 p-3 flex flex-wrap items-center gap-3">
          <span className="text-sm font-medium text-slate-800">Partners use</span>
          <div className="inline-flex rounded-lg border border-slate-300 overflow-hidden bg-white">
            {['uat', 'prod'].map((mode) => (
              <button
                key={mode}
                type="button"
                disabled={switchingLive}
                onClick={() => setPartnerLive(mode)}
                className={`px-4 py-2 text-sm font-medium disabled:opacity-50 ${
                  liveMode === mode ? 'bg-emerald-700 text-white' : 'text-slate-700 hover:bg-slate-100'
                }`}
              >
                {mode === 'uat' ? 'UAT' : 'Production'}
                {liveMode === mode ? ' · live' : ''}
              </button>
            ))}
          </div>
          {switchingLive ? <span className="text-xs text-slate-500">Switching…</span> : null}
        </div>

        <div className="flex flex-wrap items-center gap-2">
          <span className="text-sm font-medium text-slate-800 mr-1">Biller catalog</span>
          {['uat', 'prod'].map((env) => {
            const active = catalogEnv === env;
            return (
              <button
                key={env}
                type="button"
                onClick={() => selectCatalogEnv(env)}
                className={`px-4 py-2 text-sm rounded-lg border ${
                  active ? 'bg-blue-600 text-white border-blue-600' : 'bg-white text-gray-700 border-gray-300 hover:bg-gray-50'
                }`}
              >
                {env === 'uat' ? 'UAT' : 'Production'}
                {' · '}
                {env === 'uat' ? catalogCounts.uat ?? 0 : catalogCounts.prod ?? 0}
              </button>
            );
          })}
          <span className="text-xs text-slate-500 ml-2">
            Sync and directory apply to <strong>{catalogEnv.toUpperCase()}</strong> only
          </span>
        </div>

        <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
          <div className="rounded-lg border border-blue-100 bg-blue-50 p-3">
            <p className="text-xs text-blue-700">{catalogEnv.toUpperCase()} billers</p>
            <p className="text-lg font-semibold text-blue-900">{directoryPagination.total || billerMaster.length}</p>
          </div>
          <div className="rounded-lg border border-green-100 bg-green-50 p-3">
            <p className="text-xs text-green-700">Visible on this page</p>
            <p className="text-lg font-semibold text-green-900">{visibleServicesCount}</p>
          </div>
          <div className="rounded-lg border border-amber-100 bg-amber-50 p-3">
            <p className="text-xs text-amber-700">Hidden on this page</p>
            <p className="text-lg font-semibold text-amber-900">{hiddenServicesCount}</p>
          </div>
        </div>
      </div>

      <div className="bg-white rounded-xl border border-gray-200 p-2 flex flex-wrap gap-2">
        {TABS.map((tab) => (
          <button
            type="button"
            key={tab.id}
            onClick={() => setActiveTab(tab.id)}
            className={`px-3 py-1.5 text-sm rounded border ${
              activeTab === tab.id ? 'bg-blue-600 text-white border-blue-600' : 'bg-white text-gray-700 border-gray-300'
            }`}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {error && <div className="bg-red-50 border border-red-200 text-red-700 rounded-lg p-3 text-sm">{error}</div>}
      {info && <div className="bg-green-50 border border-green-200 text-green-700 rounded-lg p-3 text-sm">{info}</div>}

      {activeTab === 'readiness' && (
        <div className="space-y-4">
        <div className="bg-white rounded-xl border border-gray-200 p-5 space-y-4">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div>
              <h2 className="font-semibold text-gray-900">Sync {catalogEnv.toUpperCase()} billers</h2>
              <p className="text-xs text-gray-500 mt-1">
                Uses {catalogEnv.toUpperCase()} credentials and writes only to the {catalogEnv.toUpperCase()} catalog.
              </p>
            </div>
            {syncUsage ? (
              <div className="text-right text-xs text-gray-600">
                <div><strong>{syncUsage.used_calls_today}/{syncUsage.max_calls_per_day}</strong> calls used today ({catalogEnv.toUpperCase()})</div>
                <div>{syncUsage.remaining_calls_today} remaining</div>
              </div>
            ) : null}
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-[1fr_auto_auto_auto] gap-2 items-center">
            <input
              value={syncInputIds}
              onChange={(e) => setSyncInputIds(e.target.value)}
              className="px-3 py-2 border rounded text-sm"
              placeholder="Optional biller IDs (comma/newline, max 2000)"
            />
          <button
            type="button"
            onClick={runSync}
            disabled={syncing}
            className="px-4 py-2 bg-blue-600 text-white text-sm rounded disabled:opacity-50"
          >
            {syncing ? 'Running sync...' : `Sync ${catalogEnv.toUpperCase()}`}
          </button>
          <button
            type="button"
            onClick={refreshCache}
            className="px-4 py-2 bg-slate-100 text-slate-800 text-sm rounded border border-slate-300"
          >
              Refresh Cache
            </button>
            <button
              type="button"
              onClick={clearAllBillers}
              className="px-4 py-2 bg-red-50 text-red-700 text-sm rounded border border-red-200"
            >
              Clear {catalogEnv.toUpperCase()}
          </button>
        </div>
          {syncInputIds.trim() ? (
            <div className="text-xs border rounded p-3 bg-slate-50 space-y-1">
              <div>
                Parsed IDs: <strong>{[...new Set(syncInputIds.split(/[\s,\n]+/).map((x) => x.trim()).filter(Boolean))].length}</strong>
              </div>
              {syncInvalidIds.length ? (
                <div className="text-red-700">
                  Invalid IDs ({syncInvalidIds.length} shown): {syncInvalidIds.join(', ')}
                </div>
              ) : (
                <div className="text-emerald-700">Input format looks valid.</div>
              )}
            </div>
          ) : null}

          {syncUsage && (
            <div className="text-xs border rounded p-3 bg-slate-50 space-y-2">
              <div className="flex items-center justify-between">
                <span>Calls used today</span>
                <strong>{syncUsage.used_calls_today}/{syncUsage.max_calls_per_day}</strong>
              </div>
              <div className="w-full bg-slate-200 rounded-full h-2">
                <div className="h-2 rounded-full bg-blue-600" style={{ width: `${syncUsagePercent}%` }} />
              </div>
              <div>Remaining calls today: <strong>{syncUsage.remaining_calls_today}</strong></div>
            </div>
          )}

        {syncDiagnostics && (
            <div className="rounded-lg border border-slate-200 bg-slate-50 p-3 text-xs grid grid-cols-2 md:grid-cols-4 gap-2">
              <div><strong>Updated:</strong> {syncDiagnostics.updated_count || 0}</div>
              <div><strong>Source Rows:</strong> {syncDiagnostics.biller_count || 0}</div>
              <div><strong>Status Code:</strong> {syncDiagnostics.upstream_status_code || 'n/a'}</div>
              <div><strong>Retry Used:</strong> {syncDiagnostics.retry_without_agent_used ? 'Yes' : 'No'}</div>
              {syncDiagnostics.warning ? <div className="col-span-2 md:col-span-4 text-amber-700"><strong>Warning:</strong> {syncDiagnostics.warning}</div> : null}
            </div>
        )}
      </div>

        <div className="bg-white rounded-xl border border-gray-200 p-5 space-y-4">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div>
              <h2 className="font-semibold text-gray-900">Excel MDM import</h2>
              <p className="text-xs text-gray-500 mt-1">
                Upload BillAvenue MDM sheet into the {catalogEnv.toUpperCase()} catalog.
                Up to 2000 IDs per BillAvenue call · 15 calls/day · remainder stays queued.
              </p>
            </div>
            <span className="text-[11px] px-2 py-1 rounded border border-slate-200 bg-slate-50 text-slate-700">
              {catalogEnv.toUpperCase()}
            </span>
          </div>

          <div className="flex flex-wrap items-center gap-3">
            <label className="inline-flex items-center gap-2 px-4 py-2 bg-indigo-600 text-white text-sm rounded cursor-pointer disabled:opacity-50">
              <input
                type="file"
                accept=".xlsx,.xls,.xlsm"
                className="hidden"
                disabled={mdmImportUploading}
                onChange={uploadMdmExcel}
              />
              {mdmImportUploading ? 'Uploading…' : 'Choose Excel file'}
            </label>
            {mdmImportFileName ? (
              <span className="text-xs text-gray-600 truncate max-w-[240px]">{mdmImportFileName}</span>
            ) : null}
            <button
              type="button"
              onClick={processMdmImportRemaining}
              disabled={mdmImportProcessing || mdmImportDestroying || !mdmImportJob?.id || !(Number(mdmImportJob?.pending_ids || 0) > 0)}
              className="px-4 py-2 bg-slate-100 text-slate-800 text-sm rounded border border-slate-300 disabled:opacity-50"
            >
              {mdmImportProcessing ? 'Processing…' : 'Process remaining today'}
            </button>
            <button
              type="button"
              onClick={destroyMdmImportJob}
              disabled={mdmImportDestroying || mdmImportProcessing || !mdmImportJob?.id}
              className="px-4 py-2 bg-red-50 text-red-700 text-sm rounded border border-red-300 disabled:opacity-50"
              title="Stop this job and remove it from the queue"
            >
              {mdmImportDestroying ? 'Destroying…' : 'Destroy job'}
            </button>
          </div>

          {mdmImportJob ? (
            <div className="text-xs border rounded p-3 bg-slate-50 space-y-2">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <div>
                  Job #{mdmImportJob.id} · <strong>{mdmImportJob.status}</strong>
                  {mdmImportJob.original_filename ? ` · ${mdmImportJob.original_filename}` : ''}
                </div>
                <div className="flex flex-wrap items-center gap-3 text-gray-600">
                  <span>
                    Synced {mdmImportJob.synced_ids || 0} / {mdmImportJob.total_ids || 0}
                    {' · '}Pending {mdmImportJob.pending_ids || 0}
                    {' · '}Failed {mdmImportJob.failed_ids || 0}
                  </span>
                  <button
                    type="button"
                    onClick={destroyMdmImportJob}
                    disabled={mdmImportDestroying || mdmImportProcessing}
                    className="text-red-700 hover:underline font-semibold disabled:opacity-50"
                  >
                    {mdmImportDestroying ? 'Destroying…' : 'Destroy'}
                  </button>
                </div>
              </div>
              <div className="w-full bg-slate-200 rounded-full h-2">
                <div
                  className="h-2 rounded-full bg-indigo-600"
                  style={{
                    width: `${Math.min(100, Math.round(
                      ((Number(mdmImportJob.synced_ids || 0) + Number(mdmImportJob.failed_ids || 0))
                        / Math.max(1, Number(mdmImportJob.total_ids || 0))) * 100,
                    ))}%`,
                  }}
                />
              </div>
              {syncUsage ? (
                <div>Quota remaining today ({catalogEnv.toUpperCase()}): <strong>{syncUsage.remaining_calls_today}</strong></div>
              ) : null}
              {mdmImportJob.error_summary ? (
                <div className="text-amber-700">{mdmImportJob.error_summary}</div>
              ) : null}
            </div>
          ) : (
            <p className="text-xs text-gray-500">No import jobs yet for {catalogEnv.toUpperCase()}.</p>
          )}
        </div>
        </div>
      )}

      {activeTab === 'directory' && (
        <div className="bg-white rounded-xl border border-gray-200 p-5 space-y-4">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div>
              <h2 className="font-semibold">BillAvenue Biller Directory</h2>
              <p className="text-xs text-gray-500">Enterprise directory view with searchable pagination and detailed drill-down.</p>
            </div>
            <span className="text-xs text-gray-500">
              {catalogEnv.toUpperCase()} total: {directoryPagination.total}
            </span>
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-[1fr_auto_auto_auto] gap-2">
            <input
              value={directorySearch}
              onChange={(e) => setDirectorySearch(e.target.value)}
              placeholder="Search by biller name, biller ID, category"
              className="px-3 py-2 border rounded text-sm"
            />
            <button
              type="button"
              onClick={() => { setDirectoryPage(1); loadAll(); }}
              className="px-3 py-2 border rounded text-sm bg-slate-50"
            >
              Search
            </button>
            <select
              value={directoryCategory}
              onChange={(e) => { setDirectoryCategory(e.target.value); setDirectoryPage(1); }}
              className="px-3 py-2 border rounded text-sm"
            >
              <option value="all">All categories</option>
              {directoryCategories.map((c) => (
                <option key={c} value={c}>{c}</option>
              ))}
            </select>
            <select
              value={directoryPageSize}
              onChange={(e) => { setDirectoryPageSize(Number(e.target.value)); setDirectoryPage(1); }}
              className="px-3 py-2 border rounded text-sm"
            >
              <option value={10}>10 / page</option>
              <option value={25}>25 / page</option>
              <option value={50}>50 / page</option>
              <option value={100}>100 / page</option>
              <option value={50000}>All</option>
            </select>
          </div>

          <div className="flex flex-wrap items-center justify-between gap-2 border rounded p-2 bg-slate-50 text-xs">
            <div>
              Selected billers: <strong>{selectedDirectoryBillerIds.length}</strong>
              {selectedDirectoryBillerIds.length ? ` (${selectedDirectoryBillerIds.slice(0, 5).join(', ')}${selectedDirectoryBillerIds.length > 5 ? ', ...' : ''})` : ''}
            </div>
            <div className="flex flex-wrap gap-2">
              <button
                type="button"
                onClick={syncSelectedDirectoryBillers}
                disabled={syncing || selectedDirectoryBillerIds.length < 1}
                className="px-3 py-1.5 bg-blue-600 text-white rounded disabled:opacity-50"
              >
                {syncing ? 'Syncing selected...' : 'Sync selected'}
              </button>
              <button
                type="button"
                onClick={deleteSelectedDirectoryBillers}
                disabled={selectedDirectoryBillerIds.length < 1}
                className="px-3 py-1.5 bg-red-600 text-white rounded disabled:opacity-50"
              >
                Delete selected
              </button>
            </div>
          </div>

          <div className="overflow-auto border rounded-lg">
            <table className="w-full text-sm">
              <thead className="bg-gray-50">
                <tr>
                  <th className="text-left p-2">
                    <input
                      type="checkbox"
                      checked={allVisibleDirectoryIds.length > 0 && selectedDirectoryBillerIds.length === allVisibleDirectoryIds.length}
                      onChange={toggleSelectAllDirectoryRows}
                    />
                  </th>
                  <th className="text-left p-2">Env</th>
                  <th className="text-left p-2">Biller</th>
                  <th className="text-left p-2">Biller ID</th>
                  <th className="text-left p-2">Category</th>
                  <th className="text-left p-2">Status</th>
                  <th className="text-left p-2">Local State</th>
                  <th className="text-left p-2">Last Sync</th>
                  <th className="text-left p-2">Actions</th>
                </tr>
              </thead>
              <tbody>
                {filteredDirectoryBillers.map((b) => (
                  <tr key={b.id} className="border-t">
                    <td className="p-2">
                      <input
                        type="checkbox"
                        checked={selectedDirectoryBillerIds.includes(String(b.biller_id || '').trim())}
                        onChange={() => toggleDirectoryRowSelection(b.biller_id)}
                      />
                    </td>
                    <td className="p-2">
                      <span
                        className={`text-[10px] px-1.5 py-0.5 rounded border ${
                          (b.environment || catalogEnv) === 'prod'
                            ? 'bg-violet-50 border-violet-200 text-violet-900'
                            : 'bg-sky-50 border-sky-200 text-sky-900'
                        }`}
                      >
                        {(b.environment || catalogEnv || '').toUpperCase()}
                      </span>
                    </td>
                    <td className="p-2 font-medium">{b.biller_name || '—'}</td>
                    <td className="p-2 font-mono text-xs">{b.biller_id}</td>
                    <td className="p-2">{b.biller_category || '—'}</td>
                    <td className="p-2">{b.biller_status || '—'}</td>
                    <td className="p-2 text-xs">{b.is_active_local ? 'Visible to everyone' : 'Hidden from users'}</td>
                    <td className="p-2 text-xs">{b.last_synced_at ? new Date(b.last_synced_at).toLocaleString() : '-'}</td>
                    <td className="p-2">
                      <button
                        type="button"
                        className="px-2 py-1 text-xs border rounded"
                        onClick={() => openDirectoryBiller(b)}
                      >
                        View details
                      </button>
                      <button
                        type="button"
                        className="px-2 py-1 text-xs border rounded ml-1"
                        onClick={() => toggleLocalBillerState(b)}
                      >
                        {b.is_active_local ? 'Disable Visibility' : 'Enable Visibility'}
                      </button>
                      <button
                        type="button"
                        className="px-2 py-1 text-xs border rounded ml-1 text-red-700"
                        onClick={() => softDeleteBiller(b)}
                      >
                        Delete
                      </button>
                    </td>
                  </tr>
                ))}
                {filteredDirectoryBillers.length === 0 ? (
                  <tr>
                    <td colSpan={8} className="p-4 text-center text-sm text-gray-500">No billers found for this filter.</td>
                  </tr>
                ) : null}
              </tbody>
            </table>
          </div>

          <div className="flex items-center justify-between text-xs text-gray-600">
            <span>
              Page {directoryPagination.page} / {directoryPagination.total_pages} · Showing {filteredDirectoryBillers.length} · Total {directoryPagination.total}
            </span>
            <div className="space-x-2">
              <button
                type="button"
                disabled={directoryPagination.page <= 1}
                onClick={() => setDirectoryPage((p) => Math.max(1, p - 1))}
                className="px-2 py-1 border rounded disabled:opacity-50"
              >
                Prev
              </button>
              <button
                type="button"
                disabled={directoryPagination.page >= directoryPagination.total_pages}
                onClick={() => setDirectoryPage((p) => p + 1)}
                className="px-2 py-1 border rounded disabled:opacity-50"
              >
                Next
              </button>
            </div>
          </div>
        </div>
      )}

      {activeTab === 'operations' && (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
          <div className="bg-white rounded-xl border border-gray-200 p-5 space-y-4">
            <h2 className="font-semibold">Master Setup</h2>
            <form onSubmit={saveCategory} className="space-y-2">
              <p className="text-sm font-medium">Create Category</p>
              <input className="w-full border rounded px-3 py-2 text-sm" placeholder="code" value={categoryForm.code} onChange={(e) => setCategoryForm((s) => ({ ...s, code: e.target.value }))} required />
          <input className="w-full border rounded px-3 py-2 text-sm" placeholder="name" value={categoryForm.name} onChange={(e) => setCategoryForm((s) => ({ ...s, name: e.target.value }))} required />
              <button type="submit" className="px-3 py-1.5 bg-blue-600 text-white text-sm rounded">Save category</button>
        </form>

            <form onSubmit={saveProvider} className="space-y-2">
              <p className="text-sm font-medium">Create Provider</p>
          <select className="w-full border rounded px-3 py-2 text-sm" value={providerForm.category} onChange={(e) => setProviderForm((s) => ({ ...s, category: e.target.value }))} required>
            <option value="">Select category</option>
            {categories.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
          </select>
          <input className="w-full border rounded px-3 py-2 text-sm" placeholder="provider code" value={providerForm.code} onChange={(e) => setProviderForm((s) => ({ ...s, code: e.target.value }))} required />
          <input className="w-full border rounded px-3 py-2 text-sm" placeholder="provider name" value={providerForm.name} onChange={(e) => setProviderForm((s) => ({ ...s, name: e.target.value }))} required />
              <button type="submit" className="px-3 py-1.5 bg-blue-600 text-white text-sm rounded">Save provider</button>
        </form>

            <form onSubmit={saveMap} className="space-y-2">
              <p className="text-sm font-medium">{mapForm.id ? 'Update Provider-Biller Map' : 'Create Provider-Biller Map'}</p>
          <select className="w-full border rounded px-3 py-2 text-sm" value={mapForm.provider} onChange={(e) => setMapForm((s) => ({ ...s, provider: e.target.value }))} required>
            <option value="">Select provider</option>
                {providers.map((p) => <option key={p.id} value={p.id}>{p.name} ({p.category_code})</option>)}
          </select>
          <select className="w-full border rounded px-3 py-2 text-sm" value={mapForm.biller_master} onChange={(e) => setMapForm((s) => ({ ...s, biller_master: e.target.value }))} required>
            <option value="">Select biller</option>
                {providerScopedBillers.map((b) => <option key={b.id} value={b.id}>{b.biller_name} ({b.biller_id}) - {b.biller_category}</option>)}
          </select>
              <button type="submit" className="px-3 py-1.5 bg-blue-600 text-white text-sm rounded">
                {mapForm.id ? 'Update map' : 'Save map'}
              </button>
              {mapForm.id ? (
                <button type="button" className="px-3 py-1.5 border text-sm rounded ml-2" onClick={() => setMapForm(emptyMapForm)}>
                  Cancel edit
                </button>
              ) : null}
        </form>
      </div>

          <div className="bg-white rounded-xl border border-gray-200 p-5 space-y-3">
            <h2 className="font-semibold">Ops Summary & Existing Mappings</h2>
            {opsSummary && (
              <div className="grid grid-cols-2 gap-2 text-sm">
                <div className="border rounded p-2">Stale Billers: <strong>{opsSummary.stale_billers}</strong></div>
                <div className="border rounded p-2">Unmapped: <strong>{opsSummary.unmapped_billers}</strong></div>
                <div className="border rounded p-2">Inactive Categories: <strong>{opsSummary.inactive_categories}</strong></div>
                <div className="border rounded p-2">Conflicting Rules: <strong>{opsSummary.conflicting_rule_windows}</strong></div>
              </div>
            )}
            <div className="flex items-center justify-between">
              <h3 className="text-sm font-semibold">Existing Provider-Biller Mappings</h3>
              <input
                value={mapSearch}
                onChange={(e) => setMapSearch(e.target.value)}
                className="px-2 py-1 border rounded text-xs"
                placeholder="Search provider/biller/category"
              />
        </div>
            <div className="max-h-72 overflow-auto border rounded">
              <table className="w-full text-xs">
            <thead className="bg-gray-50">
              <tr>
                    <th className="text-left p-2">Category</th>
                <th className="text-left p-2">Provider</th>
                <th className="text-left p-2">Biller</th>
                    <th className="text-left p-2">Biller ID</th>
                    <th className="text-left p-2">Action</th>
              </tr>
            </thead>
            <tbody>
                  {filteredOpsMaps.slice(0, 100).map((m) => (
                <tr key={m.id} className="border-t">
                      <td className="p-2">{m.category_name || m.category_code || '—'}</td>
                  <td className="p-2">{m.provider_name || m.provider_code}</td>
                      <td className="p-2">{m.biller_name || '—'}</td>
                      <td className="p-2">{m.biller_id || '—'}</td>
                  <td className="p-2">
                        <button type="button" className="px-2 py-1 border rounded" onClick={() => editMap(m)}>Edit</button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
            <p className="text-[11px] text-gray-500">Showing {Math.min(filteredOpsMaps.length, 100)} of {filteredOpsMaps.length} mappings.</p>
          </div>
        </div>
      )}

      <div className="text-xs text-gray-400">
        {loading
          ? 'Loading governance data...'
          : `Billers: ${billerMaster.length}, Visible: ${visibleServicesCount}, Hidden: ${hiddenServicesCount}, Categories: ${categories.length}`}
      </div>

      {audits.length > 0 || observability ? (
        <div className="bg-white rounded-xl border border-gray-200 p-5 space-y-3">
          <h2 className="font-semibold">Audit & Observability</h2>
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-3">
            <div className="rounded-lg border border-slate-200">
              <div className="px-3 py-2 bg-slate-100 text-xs font-medium text-slate-700">Recent changes</div>
              <div className="max-h-56 overflow-auto text-xs">
                {audits.slice(0, 10).map((a) => (
                  <div key={a.id} className="px-3 py-2 border-t first:border-t-0">
                    <p><strong>{a.action || 'update'}</strong> · Rule: {a.rule_code || 'n/a'}</p>
                    <p className="text-slate-500">{a.reason || 'No reason provided'}</p>
                  </div>
                ))}
              </div>
            </div>
            <div className="rounded-lg border border-slate-200">
              <div className="px-3 py-2 bg-slate-100 text-xs font-medium text-slate-700">API health</div>
              <div className="max-h-56 overflow-auto text-xs">
                {Object.entries(observability?.endpoint_counts || {}).map(([k, v]) => (
                  <div key={k} className="px-3 py-2 border-t first:border-t-0 flex items-center justify-between">
                    <span>{toTitle(k)}</span>
                    <span className="text-slate-600">Total {v.total || 0} · Failed {v.failed || 0}</span>
                  </div>
                ))}
                {Object.keys(observability?.endpoint_counts || {}).length === 0 ? (
                  <div className="px-3 py-3 text-slate-500">No endpoint telemetry available.</div>
                ) : null}
              </div>
            </div>
          </div>
          {syncUsageHistory.length > 0 ? (
            <div className="rounded-lg border border-slate-200">
              <div className="px-3 py-2 bg-slate-100 text-xs font-medium text-slate-700">Sync usage history</div>
              <div className="max-h-56 overflow-auto">
                <table className="w-full text-xs">
                  <thead className="bg-white">
                    <tr>
                      <th className="text-left p-2">Date</th>
                      <th className="text-left p-2">Calls</th>
                      <th className="text-left p-2">IDs</th>
                      <th className="text-left p-2">Status</th>
              </tr>
            </thead>
            <tbody>
                    {syncUsageHistory.slice(0, 15).map((row) => (
                      <tr key={row.id} className="border-t">
                        <td className="p-2">{row.usage_date || '-'}</td>
                        <td className="p-2">{row.call_count || 0}</td>
                        <td className="p-2">{row.requested_ids_count || 0}</td>
                        <td className="p-2">{toTitle(row.last_status || 'n/a')}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
          ) : null}
        </div>
      ) : null}
    </div>
  );
};

export default BbpsProviderGovernance;
