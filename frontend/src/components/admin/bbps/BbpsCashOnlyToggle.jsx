import React, { useCallback, useEffect, useState } from 'react';
import { bbpsAPI } from '../../../services/api';

/**
 * Shared toggle for BBPS catalog cash-only user mode (per UAT/PROD environment).
 */
const BbpsCashOnlyToggle = ({ environment, className = '' }) => {
  const [enabled, setEnabled] = useState(false);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');

  const load = useCallback(async () => {
    if (!environment) return;
    setLoading(true);
    setError('');
    const res = await bbpsAPI.getCatalogUxSettings(environment);
    setLoading(false);
    if (res.success) {
      setEnabled(Boolean(res.data?.cash_only_for_users));
    } else {
      setError(res.message || 'Could not load catalog UX settings');
    }
  }, [environment]);

  useEffect(() => {
    load();
  }, [load]);

  const onToggle = async () => {
    if (!environment || saving) return;
    const next = !enabled;
    setSaving(true);
    setError('');
    const res = await bbpsAPI.updateCatalogUxSettings({
      environment,
      cash_only_for_users: next,
    });
    setSaving(false);
    if (res.success) {
      setEnabled(Boolean(res.data?.cash_only_for_users));
    } else {
      setError(res.message || 'Could not update setting');
    }
  };

  return (
    <div
      className={`rounded-lg border border-emerald-200 dark:border-emerald-800 bg-emerald-50/60 dark:bg-emerald-950/30 p-3 flex flex-wrap items-center justify-between gap-3 ${className}`}
    >
      <div className="min-w-0 flex-1">
        <p className="text-sm font-semibold text-emerald-900 dark:text-emerald-200">
          Cash-only for end users
          {enabled ? (
            <span className="ml-2 inline-flex rounded-full bg-emerald-600 text-white text-[10px] font-bold px-2 py-0.5 uppercase">
              Active
            </span>
          ) : null}
        </p>
        <p className="text-xs text-emerald-800/80 dark:text-emerald-300/80 mt-0.5">
          Users see only cash-capable billers. Payment method is hidden; Cash (AGT) is used automatically.
        </p>
        {error ? <p className="text-xs text-red-600 mt-1">{error}</p> : null}
      </div>
      <button
        type="button"
        disabled={loading || saving || !environment}
        onClick={onToggle}
        className={`shrink-0 relative inline-flex h-7 w-12 items-center rounded-full transition-colors disabled:opacity-50 ${
          enabled ? 'bg-emerald-600' : 'bg-slate-300 dark:bg-slate-600'
        }`}
        aria-pressed={enabled}
        aria-label="Toggle cash-only mode for end users"
      >
        <span
          className={`inline-block h-5 w-5 transform rounded-full bg-white shadow transition-transform ${
            enabled ? 'translate-x-6' : 'translate-x-1'
          }`}
        />
      </button>
    </div>
  );
};

export default BbpsCashOnlyToggle;
