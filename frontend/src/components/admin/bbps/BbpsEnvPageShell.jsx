import React from 'react';
import { Link } from 'react-router-dom';

const ENV_META = {
  uat: {
    label: 'UAT',
    badgeClass: 'bg-amber-50 text-amber-900 ring-amber-300 dark:bg-amber-950/40 dark:text-amber-300',
    banner: null,
  },
  prod: {
    label: 'Production',
    badgeClass: 'bg-red-50 text-red-800 ring-red-300 dark:bg-red-950/40 dark:text-red-300',
    banner:
      'You are editing the Production MDM catalog. Sync, visibility, and delete actions affect live retailer data.',
  },
  production: {
    label: 'Production',
    badgeClass: 'bg-red-50 text-red-800 ring-red-300 dark:bg-red-950/40 dark:text-red-300',
    banner:
      'You are editing the Production MDM catalog. Sync, visibility, and delete actions affect live retailer data.',
  },
};

const BbpsEnvPageShell = ({
  title,
  subtitle,
  environment,
  breadcrumbs = [],
  children,
  actions = null,
}) => {
  const envKey = String(environment || 'uat').toLowerCase() === 'prod' ? 'prod' : String(environment || 'uat').toLowerCase();
  const meta = ENV_META[envKey] || ENV_META.uat;

  return (
    <div className="space-y-4">
      {breadcrumbs.length > 0 && (
        <nav className="flex flex-wrap items-center gap-1 text-xs text-slate-500 dark:text-slate-400">
          {breadcrumbs.map((crumb, idx) => (
            <span key={crumb.to || crumb.label} className="inline-flex items-center gap-1">
              {idx > 0 ? <span className="text-slate-300 dark:text-slate-600">/</span> : null}
              {crumb.to ? (
                <Link to={crumb.to} className="font-medium text-blue-600 hover:text-blue-800 dark:text-blue-400">
                  {crumb.label}
                </Link>
              ) : (
                <span className="font-medium text-slate-700 dark:text-slate-300">{crumb.label}</span>
              )}
            </span>
          ))}
        </nav>
      )}

      {meta.banner ? (
        <div className="rounded-lg border border-red-300 bg-red-50 px-4 py-2.5 text-sm font-medium text-red-800 dark:border-red-800 dark:bg-red-950/40 dark:text-red-300">
          {meta.banner}
        </div>
      ) : null}

      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <div className="mb-1 flex flex-wrap items-center gap-2">
            <span className={`rounded-full px-2.5 py-0.5 text-[11px] font-bold uppercase tracking-wide ring-1 ${meta.badgeClass}`}>
              {meta.label}
            </span>
          </div>
          <h2 className="text-xl font-bold text-slate-900 dark:text-slate-100">{title}</h2>
          {subtitle ? <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">{subtitle}</p> : null}
        </div>
        {actions ? <div className="flex flex-wrap gap-2">{actions}</div> : null}
      </div>

      {children}
    </div>
  );
};

export default BbpsEnvPageShell;
