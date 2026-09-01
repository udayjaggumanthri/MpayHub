import React, { useEffect, useState } from 'react';
import { Navigate, Route, Routes } from 'react-router-dom';
import { billAvenueAdminAPI } from '../../../services/api';
import BillAvenueSettings from '../BillAvenueSettings';
import BbpsOpsConsole from '../BbpsOpsConsole';
import BbpsProviderFloat from '../BbpsProviderFloat';
import BbpsOverview from './BbpsOverview';
import BbpsCatalogHub from './BbpsCatalogHub';

const CatalogRedirect = ({ tab, mdmEnv }) => {
  const params = new URLSearchParams({ tab });
  if (mdmEnv) params.set('mdmEnv', mdmEnv);
  return <Navigate to={`/admin/bbps/catalog?${params.toString()}`} replace />;
};

const BbpsConsole = () => {
  const [liveMode, setLiveMode] = useState('');
  const [counts, setCounts] = useState(null);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      const res = await billAvenueAdminAPI.getBillerCategoryCounts();
      if (cancelled || !res.success) return;
      setLiveMode(res.data?.live_mode || '');
      setCounts(res.data?.catalog_counts || null);
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  const isProd = String(liveMode).toLowerCase() === 'prod';

  return (
    <div className="-m-3 min-h-screen bg-slate-50 dark:bg-slate-800/50 p-3 sm:-m-4 sm:p-4 md:-m-6 md:p-6 lg:-m-8 lg:p-8">
      <div className="mx-auto max-w-[1400px] space-y-5">
        <header className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
          <div>
            <p className="text-xs font-semibold uppercase tracking-[0.18em] text-blue-700 dark:text-blue-300">
              BBPS Configuration
            </p>
            <h1 className="mt-1 text-2xl font-bold tracking-tight text-slate-900 dark:text-slate-100 sm:text-3xl">
              BBPS Console
            </h1>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            {liveMode && (
              <span
                className={`rounded-full px-3 py-1 text-xs font-semibold ring-1 ${
                  isProd
                    ? 'bg-emerald-50 dark:bg-emerald-950/40 text-emerald-800 dark:text-emerald-300 ring-emerald-300'
                    : 'bg-amber-50 dark:bg-amber-950/40 text-amber-900 dark:text-amber-300 ring-amber-300'
                }`}
              >
                Live: {isProd ? 'Production' : 'UAT'}
              </span>
            )}
            {counts && (
              <span className="rounded-full bg-slate-100 dark:bg-slate-800 px-3 py-1 text-xs font-semibold text-slate-700 dark:text-slate-300 ring-1 ring-slate-200 dark:ring-slate-700">
                PROD {counts.prod ?? 0} · UAT {counts.uat ?? 0} billers
              </span>
            )}
          </div>
        </header>

        <main className="min-w-0">
          <Routes>
            <Route index element={<BbpsOverview />} />
            <Route path="catalog" element={<BbpsCatalogHub />} />
            <Route path="partner-catalog" element={<CatalogRedirect tab="partner" />} />
            <Route path="catalog-visibility/hidden" element={<CatalogRedirect tab="visibility" />} />
            <Route path="catalog-visibility" element={<CatalogRedirect tab="visibility" />} />
            <Route path="directory/uat" element={<CatalogRedirect tab="mdm" mdmEnv="uat" />} />
            <Route path="directory/production" element={<CatalogRedirect tab="mdm" mdmEnv="prod" />} />
            <Route
              path="directory"
              element={<CatalogRedirect tab="mdm" mdmEnv={isProd ? 'prod' : 'uat'} />}
            />
            <Route path="sync" element={<CatalogRedirect tab="sync" />} />
            <Route path="float" element={<BbpsProviderFloat />} />
            <Route path="ops" element={<BbpsOpsConsole />} />
            <Route path="settings" element={<BillAvenueSettings />} />
          </Routes>
        </main>
      </div>
    </div>
  );
};

export default BbpsConsole;
