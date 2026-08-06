import React, { useEffect, useState } from 'react';
import { NavLink, Route, Routes } from 'react-router-dom';
import {
  FaChartPie,
  FaGears,
  FaLayerGroup,
  FaScrewdriverWrench,
  FaTableList,
  FaWallet,
} from 'react-icons/fa6';
import { billAvenueAdminAPI } from '../../../services/api';
import BillAvenueSettings from '../BillAvenueSettings';
import BbpsOpsConsole from '../BbpsOpsConsole';
import BbpsProviderFloat from '../BbpsProviderFloat';
import BbpsProviderGovernance from '../BbpsProviderGovernance';
import BbpsOverview from './BbpsOverview';
import BillerDirectory from './BillerDirectory';

const NAV = [
  { to: '/admin/bbps', end: true, label: 'Overview', icon: FaChartPie },
  { to: '/admin/bbps/directory', label: 'Biller Directory', icon: FaTableList },
  { to: '/admin/bbps/catalog', label: 'Catalog & Sync', icon: FaLayerGroup },
  { to: '/admin/bbps/float', label: 'Provider Float', icon: FaWallet },
  { to: '/admin/bbps/ops', label: 'Ops Tools', icon: FaScrewdriverWrench },
  { to: '/admin/bbps/settings', label: 'BillAvenue Settings', icon: FaGears },
];

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
    <div className="-m-3 min-h-screen bg-slate-50 p-3 sm:-m-4 sm:p-4 md:-m-6 md:p-6 lg:-m-8 lg:p-8">
      <div className="mx-auto max-w-[1400px] space-y-5">
        <header className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
          <div>
            <p className="text-xs font-semibold uppercase tracking-[0.18em] text-blue-700">
              BBPS Configuration
            </p>
            <h1 className="mt-1 text-2xl font-bold tracking-tight text-slate-900 sm:text-3xl">
              BBPS Console
            </h1>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            {liveMode && (
              <span
                className={`rounded-full px-3 py-1 text-xs font-semibold ring-1 ${
                  isProd
                    ? 'bg-emerald-50 text-emerald-800 ring-emerald-300'
                    : 'bg-amber-50 text-amber-900 ring-amber-300'
                }`}
              >
                Live: {isProd ? 'Production' : 'UAT'}
              </span>
            )}
            {counts && (
              <span className="rounded-full bg-slate-100 px-3 py-1 text-xs font-semibold text-slate-700 ring-1 ring-slate-200">
                PROD {counts.prod ?? 0} · UAT {counts.uat ?? 0} billers
              </span>
            )}
          </div>
        </header>

        {/* Mobile horizontal nav */}
        <nav className="flex gap-2 overflow-x-auto pb-1 lg:hidden">
          {NAV.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.end}
              className={({ isActive }) =>
                `whitespace-nowrap rounded-full px-3 py-1.5 text-xs font-semibold ring-1 ${
                  isActive ? 'bg-blue-600 text-white ring-blue-600' : 'bg-white text-slate-700 ring-slate-200'
                }`
              }
            >
              {item.label}
            </NavLink>
          ))}
        </nav>

        {/* Section routes take the full width; navigation lives in the app sidebar
            (BBPS Console submenu). The pill strip above covers mobile. */}
        <main className="min-w-0">
          <Routes>
            <Route index element={<BbpsOverview />} />
            <Route path="directory" element={<BillerDirectory />} />
            <Route path="catalog" element={<BbpsProviderGovernance />} />
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
