import React, { useCallback, useEffect, useState } from 'react';
import { FaRotate, FaTriangleExclamation } from 'react-icons/fa6';
import { adminAPI } from '../../services/api';
import Button from '../common/Button';
import Card from '../common/Card';

const defaultForm = () => ({
  test_usage_mode_enabled: false,
  test_usage_title: 'Test usage mode',
  test_usage_message:
    'The portal is currently in test usage mode. Contact your administrator.',
});

const TestUsageMode = () => {
  const [form, setForm] = useState(defaultForm);
  const [meta, setMeta] = useState({ updated_at: null, updated_by: null });
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');

  const applyFromApi = useCallback((portal) => {
    setForm({
      test_usage_mode_enabled: Boolean(portal?.test_usage_mode_enabled),
      test_usage_title: portal?.test_usage_title || defaultForm().test_usage_title,
      test_usage_message: portal?.test_usage_message || defaultForm().test_usage_message,
    });
    setMeta({ updated_at: portal?.updated_at, updated_by: portal?.updated_by });
  }, []);

  const load = useCallback(async () => {
    setLoading(true);
    setError('');
    const res = await adminAPI.getTestUsageConfig();
    if (res.success && res.data?.portal_access) {
      applyFromApi(res.data.portal_access);
    } else {
      setError(res.message || 'Could not load test usage settings');
    }
    setLoading(false);
  }, [applyFromApi]);

  useEffect(() => {
    load();
  }, [load]);

  const save = async () => {
    setSaving(true);
    setError('');
    setSuccess('');
    const res = await adminAPI.updateTestUsageConfig(form);
    if (res.success && res.data?.portal_access) {
      applyFromApi(res.data.portal_access);
      setSuccess('Test usage settings saved.');
    } else {
      setError(res.message || 'Save failed');
    }
    setSaving(false);
  };

  return (
    <div className="space-y-6">
      <div className="flex items-start justify-between gap-4 flex-wrap">
        <div>
          <h1 className="text-2xl font-semibold text-slate-900 dark:text-white">Test usage mode</h1>
          <p className="mt-1 text-sm text-slate-600 dark:text-slate-400 max-w-2xl">
            When enabled, only Super Admin and users marked as test users can sign in. Super Admin
            always bypasses this gate so you can turn the mode off.
          </p>
        </div>
        <Button type="button" variant="secondary" onClick={load} disabled={loading || saving}>
          <FaRotate className="mr-2 inline" />
          Refresh
        </Button>
      </div>

      {error ? (
        <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800 dark:border-red-900/50 dark:bg-red-950/40 dark:text-red-200">
          {error}
        </div>
      ) : null}
      {success ? (
        <div className="rounded-lg border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-800 dark:border-emerald-900/50 dark:bg-emerald-950/40 dark:text-emerald-200">
          {success}
        </div>
      ) : null}

      <Card>
        {loading ? (
          <p className="text-sm text-slate-500">Loading…</p>
        ) : (
          <div className="space-y-5">
            <label className="flex items-start gap-3 cursor-pointer">
              <input
                type="checkbox"
                className="mt-1 h-4 w-4 rounded border-slate-300"
                checked={form.test_usage_mode_enabled}
                onChange={(e) =>
                  setForm((f) => ({ ...f, test_usage_mode_enabled: e.target.checked }))
                }
              />
              <span>
                <span className="block font-medium text-slate-900 dark:text-white">
                  Enable test usage mode
                </span>
                <span className="block text-sm text-slate-600 dark:text-slate-400">
                  Non-test users see your custom title and message at login.
                </span>
              </span>
            </label>

            {form.test_usage_mode_enabled ? (
              <div className="flex items-start gap-2 rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-900 dark:border-amber-900/40 dark:bg-amber-950/30 dark:text-amber-100">
                <FaTriangleExclamation className="mt-0.5 shrink-0" />
                <span>
                  Real users will be blocked from logging in until you disable this or mark them as
                  test users.
                </span>
              </div>
            ) : null}

            <div>
              <label className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-1">
                Login popup title
              </label>
              <input
                type="text"
                className="w-full rounded-lg border border-slate-300 dark:border-slate-600 bg-white dark:bg-slate-900 px-3 py-2 text-sm"
                value={form.test_usage_title}
                onChange={(e) => setForm((f) => ({ ...f, test_usage_title: e.target.value }))}
                maxLength={200}
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-1">
                Login popup message
              </label>
              <textarea
                className="w-full rounded-lg border border-slate-300 dark:border-slate-600 bg-white dark:bg-slate-900 px-3 py-2 text-sm min-h-[100px]"
                value={form.test_usage_message}
                onChange={(e) => setForm((f) => ({ ...f, test_usage_message: e.target.value }))}
              />
            </div>

            <div className="flex items-center gap-3">
              <Button type="button" onClick={save} disabled={saving}>
                {saving ? 'Saving…' : 'Save settings'}
              </Button>
              {meta.updated_at ? (
                <span className="text-xs text-slate-500">
                  Last updated {new Date(meta.updated_at).toLocaleString()}
                </span>
              ) : null}
            </div>
          </div>
        )}
      </Card>
    </div>
  );
};

export default TestUsageMode;
