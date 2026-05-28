import React, { useCallback, useEffect, useState } from 'react';
import { FaRotate, FaTriangleExclamation } from 'react-icons/fa6';
import { adminAPI } from '../../services/api';
import Button from '../common/Button';
import Card from '../common/Card';
import { normalizeMaintenance } from '../../utils/maintenanceMode';

const MODULES = [
  {
    key: 'pay_in',
    enabledField: 'pay_in_enabled',
    messageField: 'pay_in_message',
    label: 'Pay-in (Load Money)',
    description: 'Blocks new pay-in quotes, orders, and load-money for all users.',
  },
  {
    key: 'payout',
    enabledField: 'payout_enabled',
    messageField: 'payout_message',
    label: 'Payout',
    description: 'Blocks new bank payouts for all users.',
  },
  {
    key: 'bbps',
    enabledField: 'bbps_enabled',
    messageField: 'bbps_message',
    label: 'BBPS',
    description: 'Blocks BBPS payment quotes, bill pay, and main-to-BBPS wallet transfers.',
  },
];

const defaultForm = () => ({
  pay_in_enabled: true,
  payout_enabled: true,
  bbps_enabled: true,
  pay_in_message: '',
  payout_message: '',
  bbps_message: '',
  reason_internal: '',
});

const MaintenanceMode = () => {
  const [form, setForm] = useState(defaultForm);
  const [meta, setMeta] = useState({ updated_at: null, updated_by: null });
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const [confirmOff, setConfirmOff] = useState(null);

  const applyFromApi = useCallback((maintenance) => {
    const m = normalizeMaintenance(maintenance);
    setForm({
      pay_in_enabled: m.pay_in.enabled,
      payout_enabled: m.payout.enabled,
      bbps_enabled: m.bbps.enabled,
      pay_in_message: m.pay_in.message,
      payout_message: m.payout.message,
      bbps_message: m.bbps.message,
      reason_internal: m.reason_internal || '',
    });
    setMeta({ updated_at: m.updated_at, updated_by: m.updated_by });
  }, []);

  const load = useCallback(async () => {
    setLoading(true);
    setError('');
    const res = await adminAPI.getMaintenanceConfig();
    if (res.success && res.data?.maintenance) {
      applyFromApi(res.data.maintenance);
    } else {
      setError(res.message || 'Could not load maintenance settings');
    }
    setLoading(false);
  }, [applyFromApi]);

  useEffect(() => {
    load();
  }, [load]);

  const requestToggle = (mod, nextEnabled) => {
    if (!nextEnabled) {
      setConfirmOff(mod);
      return;
    }
    setForm((f) => ({ ...f, [mod.enabledField]: true }));
  };

  const save = async (overrideForm = null) => {
    const payload = overrideForm || form;
    setSaving(true);
    setError('');
    setSuccess('');
    const res = await adminAPI.updateMaintenanceConfig(payload);
    if (res.success && res.data?.maintenance) {
      applyFromApi(res.data.maintenance);
      setSuccess('Maintenance settings saved. Changes apply immediately for all users.');
      setConfirmOff(null);
    } else {
      setError(res.message || 'Failed to save maintenance settings');
    }
    setSaving(false);
  };

  const confirmDisable = () => {
    if (!confirmOff) return;
    const next = { ...form, [confirmOff.enabledField]: false };
    setForm(next);
    setConfirmOff(null);
    save(next);
  };

  if (loading) {
    return (
      <div className="p-6 text-slate-600 text-sm">Loading maintenance settings…</div>
    );
  }

  return (
    <div className="max-w-4xl mx-auto p-4 sm:p-6 space-y-6">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold text-slate-900">Maintenance mode</h1>
          <p className="text-sm text-slate-600 mt-1 max-w-2xl">
            Turn off Pay-in, Payout, or BBPS for all users during maintenance or fraud response.
            Login, onboarding, KYC, and reports stay available.
          </p>
        </div>
        <Button
          type="button"
          variant="outline"
          size="sm"
          icon={FaRotate}
          onClick={load}
          disabled={saving}
        >
          Refresh
        </Button>
      </div>

      {error && (
        <div className="rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800">
          {error}
        </div>
      )}
      {success && (
        <div className="rounded-xl border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-900">
          {success}
        </div>
      )}

      {meta.updated_at && (
        <p className="text-xs text-slate-500">
          Last updated
          {meta.updated_by?.name ? ` by ${meta.updated_by.name}` : ''}
          {meta.updated_at ? ` at ${new Date(meta.updated_at).toLocaleString('en-IN')}` : ''}
        </p>
      )}

      <Card className="p-4 sm:p-6 space-y-6">
        {MODULES.map((mod) => (
          <div
            key={mod.key}
            className="border border-slate-200 rounded-xl p-4 space-y-3"
          >
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div>
                <h2 className="font-semibold text-slate-900">{mod.label}</h2>
                <p className="text-xs text-slate-500 mt-0.5">{mod.description}</p>
              </div>
              <div className="flex items-center">
              <button
                type="button"
                role="switch"
                aria-checked={Boolean(form[mod.enabledField])}
                onClick={() => requestToggle(mod, !form[mod.enabledField])}
                className={`relative inline-flex h-6 w-11 shrink-0 rounded-full transition-colors ${
                  form[mod.enabledField] ? 'bg-emerald-500' : 'bg-slate-300'
                }`}
              >
                <span
                  className={`inline-block h-5 w-5 transform rounded-full bg-white shadow transition-transform mt-0.5 ${
                    form[mod.enabledField] ? 'translate-x-5' : 'translate-x-0.5'
                  }`}
                />
              </button>
              <span className="text-sm font-medium text-slate-700 ml-2">
                {form[mod.enabledField] ? 'Enabled' : 'Maintenance'}
              </span>
              </div>
            </div>
            <div>
              <label className="block text-xs font-medium text-slate-600 mb-1">
                Message for users (optional)
              </label>
              <textarea
                className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm min-h-[72px]"
                placeholder="This service is temporarily unavailable due to maintenance."
                value={form[mod.messageField]}
                onChange={(e) =>
                  setForm((f) => ({ ...f, [mod.messageField]: e.target.value }))
                }
              />
            </div>
          </div>
        ))}

        <div>
          <label className="block text-xs font-medium text-slate-600 mb-1">
            Internal reason (admin only)
          </label>
          <textarea
            className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm min-h-[80px]"
            placeholder="e.g. Razorpay outage, fraud review, planned maintenance window"
            value={form.reason_internal}
            onChange={(e) => setForm((f) => ({ ...f, reason_internal: e.target.value }))}
          />
        </div>

        <div className="flex justify-end">
          <Button type="button" onClick={() => save()} disabled={saving}>
            {saving ? 'Saving…' : 'Save settings'}
          </Button>
        </div>
      </Card>

      {confirmOff && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
          <div className="bg-white rounded-xl shadow-xl max-w-md w-full p-6 space-y-4">
            <div className="flex items-start gap-3 text-amber-700">
              <FaTriangleExclamation className="mt-0.5 shrink-0" size={22} />
              <div>
                <h3 className="font-semibold text-slate-900">Turn off {confirmOff.label}?</h3>
                <p className="text-sm text-slate-600 mt-1">
                  All users will be blocked from starting new activity in this module immediately.
                  Reports and login are not affected.
                </p>
              </div>
            </div>
            <div className="flex justify-end gap-2">
              <Button type="button" variant="outline" onClick={() => setConfirmOff(null)}>
                Cancel
              </Button>
              <Button type="button" onClick={confirmDisable} disabled={saving}>
                Turn off module
              </Button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default MaintenanceMode;
