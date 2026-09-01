import React, { useCallback, useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { bbpsAPI, billAvenueAdminAPI } from '../../../services/api';
import BbpsEnvPageShell from './BbpsEnvPageShell';

const BbpsSyncConsole = ({ embedded = false }) => {
  const [catalogEnv, setCatalogEnv] = useState('uat');
  const [syncUsage, setSyncUsage] = useState(null);
  const [syncInputIds, setSyncInputIds] = useState('');
  const [syncing, setSyncing] = useState(false);
  const [syncDiagnostics, setSyncDiagnostics] = useState(null);
  const [error, setError] = useState('');
  const [info, setInfo] = useState('');
  const [mdmImportJob, setMdmImportJob] = useState(null);
  const [mdmImportUploading, setMdmImportUploading] = useState(false);
  const [mdmImportProcessing, setMdmImportProcessing] = useState(false);

  const load = useCallback(async () => {
    const [usageRes, jobsRes] = await Promise.all([
      bbpsAPI.getSyncUsageToday(catalogEnv),
      bbpsAPI.listMdmImportJobs(),
    ]);
    if (usageRes.success) setSyncUsage(usageRes.data);
    if (jobsRes.success) {
      const jobs = jobsRes.data?.jobs || [];
      setMdmImportJob(jobs.find((j) => j.environment === catalogEnv) || jobs[0] || null);
    }
  }, [catalogEnv]);

  useEffect(() => {
    load();
  }, [load]);

  const runSync = async () => {
    setSyncing(true);
    setError('');
    setInfo('');
    const ids = syncInputIds.trim()
      ? [...new Set(syncInputIds.split(/[\s,\n]+/).map((x) => x.trim()).filter(Boolean))]
      : [];
    const res = await bbpsAPI.syncBillers(ids, catalogEnv);
    setSyncing(false);
    if (res.success) {
      setSyncDiagnostics(res.data || null);
      setInfo(res.message || 'Sync completed');
      load();
    } else {
      setError(res.message || res.error || 'Sync failed');
      setSyncDiagnostics(res.data || null);
    }
  };

  const refreshCache = async () => {
    const res = await billAvenueAdminAPI.refreshProviderCache();
    if (res.success) setInfo('Provider cache refreshed');
    else setError(res.message || 'Cache refresh failed');
  };

  const clearCatalog = async () => {
    const ok = window.confirm(
      `Clear ALL ${catalogEnv.toUpperCase()} billers from the catalog? This cannot be undone without re-sync.`,
    );
    if (!ok) return;
    const res = await billAvenueAdminAPI.clearAllBillerMaster(catalogEnv);
    if (res.success) {
      setInfo(`Cleared ${res.data?.cleared_count ?? 0} billers`);
      load();
    } else setError(res.message || 'Clear failed');
  };

  const uploadMdmExcel = async (e) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setMdmImportUploading(true);
    const res = await bbpsAPI.uploadMdmImport(file, catalogEnv);
    setMdmImportUploading(false);
    e.target.value = '';
    if (res.success) {
      setMdmImportJob(res.data?.job || null);
      setInfo('MDM import job created');
      load();
    } else setError(res.message || 'Upload failed');
  };

  const processMdmImport = async () => {
    if (!mdmImportJob?.id) return;
    setMdmImportProcessing(true);
    const res = await bbpsAPI.processMdmImportJob(mdmImportJob.id);
    setMdmImportProcessing(false);
    if (res.success) {
      setMdmImportJob(res.data?.job || mdmImportJob);
      setInfo('MDM import batch processed');
      load();
    } else setError(res.message || 'Process failed');
  };

  const syncUsagePercent = syncUsage?.max_calls_per_day
    ? Math.min(100, Math.round(((syncUsage?.used_calls_today || 0) / syncUsage.max_calls_per_day) * 100))
    : 0;

  const body = (
    <>
      {embedded ? (
        <div className="flex flex-wrap items-center justify-end gap-2">
          <label className="text-sm font-medium text-slate-600 dark:text-slate-400" htmlFor="sync-env">
            Target catalog
          </label>
          <select
            id="sync-env"
            value={catalogEnv}
            onChange={(e) => setCatalogEnv(e.target.value)}
            className="rounded-lg border border-slate-200 px-3 py-2 text-sm font-semibold dark:border-slate-700 dark:bg-slate-950"
          >
            <option value="uat">UAT</option>
            <option value="prod">Production</option>
          </select>
        </div>
      ) : null}

      {error ? <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-2 text-sm text-red-700">{error}</div> : null}
      {info ? <div className="rounded-lg border border-emerald-200 bg-emerald-50 px-4 py-2 text-sm text-emerald-800">{info}</div> : null}

      <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm dark:border-slate-700 dark:bg-slate-900">
        <h3 className="font-semibold text-slate-900 dark:text-slate-100">Biller sync</h3>
        <p className="mt-1 text-xs text-slate-500">
          Writes to the {catalogEnv.toUpperCase()} catalog only.{' '}
          <Link
            to={`/admin/bbps/catalog?tab=mdm&mdmEnv=${catalogEnv === 'prod' ? 'prod' : 'uat'}`}
            className="text-blue-600 underline"
          >
            Open MDM directory
          </Link>
        </p>
        <div className="mt-4 grid gap-2 lg:grid-cols-[1fr_auto_auto_auto]">
          <input
            value={syncInputIds}
            onChange={(e) => setSyncInputIds(e.target.value)}
            className="rounded-lg border border-slate-200 px-3 py-2 text-sm dark:border-slate-700 dark:bg-slate-950"
            placeholder="Optional biller IDs (comma/newline, max 2000)"
          />
          <button type="button" onClick={runSync} disabled={syncing} className="rounded-lg bg-blue-600 px-4 py-2 text-sm font-semibold text-white disabled:opacity-50">
            {syncing ? 'Syncing…' : `Sync ${catalogEnv.toUpperCase()}`}
          </button>
          <button type="button" onClick={refreshCache} className="rounded-lg border border-slate-200 px-4 py-2 text-sm dark:border-slate-700">
            Refresh cache
          </button>
          <button type="button" onClick={clearCatalog} className="rounded-lg border border-red-200 bg-red-50 px-4 py-2 text-sm text-red-700 dark:border-red-900 dark:bg-red-950/40">
            Clear catalog
          </button>
        </div>
        {syncUsage ? (
          <div className="mt-4 rounded-lg border border-slate-200 bg-slate-50 p-3 text-xs dark:border-slate-700 dark:bg-slate-800/50">
            <div className="flex justify-between">
              <span>Calls used today ({catalogEnv.toUpperCase()})</span>
              <strong>
                {syncUsage.used_calls_today}/{syncUsage.max_calls_per_day}
              </strong>
            </div>
            <div className="mt-2 h-2 w-full rounded-full bg-slate-200 dark:bg-slate-700">
              <div className="h-2 rounded-full bg-blue-600" style={{ width: `${syncUsagePercent}%` }} />
            </div>
          </div>
        ) : null}
        {syncDiagnostics ? (
          <div className="mt-3 grid grid-cols-2 gap-2 rounded-lg border border-slate-200 bg-slate-50 p-3 text-xs md:grid-cols-4 dark:border-slate-700 dark:bg-slate-800/50">
            <div>
              <strong>Updated:</strong> {syncDiagnostics.updated_count || 0}
            </div>
            <div>
              <strong>Source rows:</strong> {syncDiagnostics.biller_count || 0}
            </div>
            <div>
              <strong>Visibility apply:</strong>{' '}
              {syncDiagnostics.visibility_apply
                ? `hidden ${syncDiagnostics.visibility_apply.hidden}`
                : 'n/a'}
            </div>
          </div>
        ) : null}
      </div>

      <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm dark:border-slate-700 dark:bg-slate-900">
        <h3 className="font-semibold text-slate-900 dark:text-slate-100">Excel MDM import</h3>
        <div className="mt-3 flex flex-wrap gap-2">
          <label className="inline-flex cursor-pointer items-center rounded-lg bg-indigo-600 px-4 py-2 text-sm font-semibold text-white">
            <input type="file" accept=".xlsx,.xls,.xlsm" className="hidden" disabled={mdmImportUploading} onChange={uploadMdmExcel} />
            {mdmImportUploading ? 'Uploading…' : 'Choose Excel file'}
          </label>
          <button
            type="button"
            onClick={processMdmImport}
            disabled={mdmImportProcessing || !mdmImportJob?.id}
            className="rounded-lg border border-slate-200 px-4 py-2 text-sm dark:border-slate-700"
          >
            {mdmImportProcessing ? 'Processing…' : 'Process remaining'}
          </button>
        </div>
        {mdmImportJob ? (
          <p className="mt-2 text-xs text-slate-500">
            Job #{mdmImportJob.id} · {mdmImportJob.status} · synced {mdmImportJob.synced_ids}/{mdmImportJob.total_ids}
          </p>
        ) : (
          <p className="mt-2 text-xs text-slate-500">No import jobs for {catalogEnv.toUpperCase()}.</p>
        )}
      </div>
    </>
  );

  if (embedded) return <div className="space-y-4">{body}</div>;

  return (
    <BbpsEnvPageShell
      environment={catalogEnv}
      title="Catalog sync"
      subtitle="Sync BillAvenue MDM, import Excel, and refresh caches. Choose target environment below."
      breadcrumbs={[{ label: 'BBPS Console', to: '/admin/bbps' }, { label: 'Catalog sync' }]}
      actions={
        <div className="flex items-center gap-2">
          <label className="text-sm font-medium text-slate-600 dark:text-slate-400" htmlFor="sync-env">
            Target catalog
          </label>
          <select
            id="sync-env"
            value={catalogEnv}
            onChange={(e) => setCatalogEnv(e.target.value)}
            className="rounded-lg border border-slate-200 px-3 py-2 text-sm font-semibold dark:border-slate-700 dark:bg-slate-950"
          >
            <option value="uat">UAT</option>
            <option value="prod">Production</option>
          </select>
        </div>
      }
    >
      {body}
    </BbpsEnvPageShell>
  );
};

export default BbpsSyncConsole;
