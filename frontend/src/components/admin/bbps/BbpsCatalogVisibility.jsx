import React, { useCallback, useEffect, useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import { bbpsAPI, billAvenueAdminAPI } from '../../../services/api';
import Badge from '../../common/Badge';
import BbpsAdminTable, { formatHiddenReason } from './BbpsAdminTable';
import BbpsEnvPageShell from './BbpsEnvPageShell';
import CashOnlyImpactModal from './CashOnlyImpactModal';

const BbpsCatalogVisibility = () => {
  const [summary, setSummary] = useState(null);
  const [settings, setSettings] = useState(null);
  const [loading, setLoading] = useState(true);
  const [toggling, setToggling] = useState(false);
  const [previewOpen, setPreviewOpen] = useState(false);
  const [preview, setPreview] = useState(null);
  const [previewLoading, setPreviewLoading] = useState(false);
  const [toast, setToast] = useState('');

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

  useEffect(() => {
    load();
  }, [load]);

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
      showToast(
        `Cash-only enabled. Hidden ${stats?.hidden ?? 0} biller(s). View details on Hidden Billers page.`,
      );
      load();
    } else {
      showToast(res.message || 'Failed to enable cash-only mode');
    }
  };

  const liveLabel = summary?.environment === 'prod' ? 'Production' : 'UAT';

  return (
    <BbpsEnvPageShell
      environment={summary?.environment}
      title="Catalog visibility"
      subtitle={`Cash-only (AGT + Cash) settings for the live partner catalog (${liveLabel}).`}
      breadcrumbs={[{ label: 'BBPS Console', to: '/admin/bbps' }, { label: 'Catalog visibility' }]}
      actions={
        <Link
          to="/admin/bbps/catalog-visibility/hidden"
          className="rounded-lg border border-slate-200 px-3 py-2 text-sm font-semibold text-blue-700 hover:bg-slate-50 dark:border-slate-700 dark:text-blue-300"
        >
          View hidden billers
        </Link>
      }
    >
      {toast ? (
        <div className="rounded-lg border border-emerald-200 bg-emerald-50 px-4 py-2 text-sm text-emerald-800 dark:border-emerald-900 dark:bg-emerald-950/40 dark:text-emerald-300">
          {toast}
        </div>
      ) : null}

      {loading ? (
        <p className="text-sm text-slate-500">Loading visibility summary…</p>
      ) : (
        <>
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
                  Applies to live partner catalog ({liveLabel}). Users see only AGT + Cash billers; payment method is
                  hidden automatically.
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

          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
            {[
              { label: 'MDM total', value: summary?.mdm_total },
              { label: 'Partner visible', value: summary?.partner_visible },
              { label: 'Cash-only hidden', value: summary?.cash_only_hidden },
              { label: 'Admin hidden', value: summary?.admin_hidden },
            ].map((card) => (
              <div
                key={card.label}
                className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm dark:border-slate-700 dark:bg-slate-900"
              >
                <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">{card.label}</p>
                <p className="mt-1 text-2xl font-bold text-slate-900 dark:text-slate-100">{card.value ?? '—'}</p>
              </div>
            ))}
          </div>
        </>
      )}

      <CashOnlyImpactModal
        open={previewOpen}
        preview={preview}
        loading={previewLoading || toggling}
        onCancel={() => setPreviewOpen(false)}
        onConfirm={confirmEnable}
      />
    </BbpsEnvPageShell>
  );
};

export default BbpsCatalogVisibility;
