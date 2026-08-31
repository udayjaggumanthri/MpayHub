import React, { useCallback, useEffect, useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import { adminAPI } from '../../services/api';
import {
  SMTP_PRESETS,
  applySmtpPreset,
  defaultSmtpForm,
  formatApiErrors,
  providerLabel,
} from './smtpPresets';
import { FaArrowLeft, FaFloppyDisk, FaPaperPlane } from 'react-icons/fa6';

const SmtpProfileForm = () => {
  const { id } = useParams();
  const isNew = !id || id === 'new';
  const navigate = useNavigate();
  const [form, setForm] = useState(defaultSmtpForm);
  const [presetKey, setPresetKey] = useState('');
  const [hasPassword, setHasPassword] = useState(false);
  const [password, setPassword] = useState('');
  const [testEmail, setTestEmail] = useState('');
  const [loading, setLoading] = useState(!isNew);
  const [saving, setSaving] = useState(false);
  const [msg, setMsg] = useState({ type: '', text: '' });

  const setBanner = (type, text) => setMsg({ type, text });

  const loadProfile = useCallback(async () => {
    if (isNew) return;
    setLoading(true);
    const res = await adminAPI.getSmtpConfigById(id);
    if (res.success && res.data?.config) {
      const c = res.data.config;
      setForm({
        name: c.name || '',
        host: c.host || '',
        port: Number(c.port) || 587,
        use_tls: !!c.use_tls,
        use_ssl: !!c.use_ssl,
        username: c.username || '',
        from_email: c.from_email || '',
        enabled: !!c.enabled,
        is_active: !!c.is_active,
      });
      setHasPassword(!!c.has_password);
    } else {
      setBanner('error', res.message || 'Profile not found');
      navigate('/admin/smtp-settings', { replace: true });
    }
    setLoading(false);
  }, [id, isNew, navigate]);

  useEffect(() => {
    loadProfile();
  }, [loadProfile]);

  const handlePresetChange = (e) => {
    const key = e.target.value;
    setPresetKey(key);
    if (key) applySmtpPreset(key, setForm);
  };

  const saveProfile = async (e) => {
    e.preventDefault();
    if (!form.name?.trim()) {
      setBanner('error', 'Profile name is required.');
      return;
    }
    if (!form.host?.trim()) {
      setBanner('error', 'SMTP host is required.');
      return;
    }
    setSaving(true);
    setBanner('info', 'Saving profile...');
    const payload = {
      ...form,
      name: form.name.trim(),
      port: Number(form.port) || 587,
    };
    const res = isNew
      ? await adminAPI.createSmtpConfig(payload)
      : await adminAPI.updateSmtpConfig(id, payload);
    if (res.success) {
      const saved = res.data?.config;
      setBanner('success', res.message || 'Profile saved');
      if (isNew && saved?.id) {
        navigate(`/admin/smtp-settings/${saved.id}/edit`, { replace: true });
      } else {
        await loadProfile();
      }
    } else {
      const detail = formatApiErrors(res.errors);
      setBanner('error', `${res.message || 'Save failed'}${detail ? ` — ${detail}` : ''}`);
    }
    setSaving(false);
  };

  const savePassword = async () => {
    if (isNew) {
      setBanner('error', 'Save the profile first, then set the password.');
      return;
    }
    if (!password.trim()) {
      setBanner('error', 'Enter a password to save.');
      return;
    }
    setSaving(true);
    const res = await adminAPI.updateSmtpSecrets(id, { password: password.trim() });
    if (res.success) {
      setBanner('success', res.message || 'Password saved');
      setPassword('');
      setHasPassword(true);
    } else {
      setBanner('error', res.message || 'Failed to save password');
    }
    setSaving(false);
  };

  const sendTest = async () => {
    if (isNew) {
      setBanner('error', 'Save the profile before sending a test email.');
      return;
    }
    setSaving(true);
    setBanner('info', 'Sending test email...');
    const res = await adminAPI.testSmtp(id, testEmail.trim());
    if (res.success) {
      setBanner('success', res.message || 'Test email sent');
    } else {
      setBanner('error', res.message || 'Test email failed');
    }
    setSaving(false);
  };

  if (loading) {
    return (
      <div className="max-w-3xl mx-auto p-12 text-center text-gray-500 dark:text-slate-400">Loading profile...</div>
    );
  }

  return (
    <div className="space-y-6 max-w-3xl mx-auto">
      <div className="flex items-center gap-3">
        <Link
          to="/admin/smtp-settings"
          className="inline-flex items-center gap-1.5 text-sm text-gray-600 dark:text-slate-400 hover:text-gray-900 dark:hover:text-slate-100"
        >
          <FaArrowLeft className="w-3.5 h-3.5" /> Back to profiles
        </Link>
      </div>

      {msg.text && (
        <div
          className={`text-sm border rounded-lg px-4 py-3 ${
            msg.type === 'success'
              ? 'bg-green-50 dark:bg-green-950/40 border-green-200 dark:border-green-800 text-green-800 dark:text-green-300'
              : msg.type === 'error'
                ? 'bg-red-50 dark:bg-red-950/40 border-red-200 dark:border-red-800 text-red-800 dark:text-red-300'
                : 'bg-blue-50 dark:bg-blue-950/40 border-blue-200 dark:border-blue-800 text-blue-800 dark:text-blue-300'
          }`}
        >
          {msg.text}
        </div>
      )}

      <form onSubmit={saveProfile} className="bg-white dark:bg-slate-900 rounded-xl border border-gray-200 dark:border-slate-700 p-6 shadow-sm space-y-6">
        <div>
          <h1 className="text-xl font-semibold text-gray-900 dark:text-slate-100">
            {isNew ? 'New SMTP profile' : `Edit: ${form.name}`}
          </h1>
          <p className="text-sm text-gray-500 dark:text-slate-400 mt-1">
            {isNew
              ? 'Create a new SMTP account. Activate it from the list when ready.'
              : `${providerLabel(form)} — ${form.is_active ? 'Active for OTP email' : 'Not active'}`}
          </p>
        </div>

        <div>
          <label className="block text-xs font-medium text-gray-600 dark:text-slate-400 mb-1">Apply provider preset</label>
          <select
            className="w-full max-w-md border border-gray-300 dark:border-slate-600 rounded-lg px-3 py-2 text-sm bg-white dark:bg-slate-900"
            value={presetKey}
            onChange={handlePresetChange}
          >
            <option value="">Custom — enter host/port manually</option>
            {Object.entries(SMTP_PRESETS).map(([key, preset]) => (
              <option key={key} value={key}>
                {preset.label}
              </option>
            ))}
          </select>
        </div>

        <div className="grid md:grid-cols-2 gap-4">
          <div>
            <label className="block text-xs font-medium text-gray-600 dark:text-slate-400 mb-1">Profile name (unique)</label>
            <input
              required
              className="w-full border border-gray-300 dark:border-slate-600 rounded-lg px-3 py-2 text-sm"
              placeholder="e.g. gmail-noreply"
              value={form.name}
              onChange={(e) => setForm((p) => ({ ...p, name: e.target.value }))}
            />
          </div>
          <div>
            <label className="block text-xs font-medium text-gray-600 dark:text-slate-400 mb-1">SMTP host</label>
            <input
              required
              className="w-full border border-gray-300 dark:border-slate-600 rounded-lg px-3 py-2 text-sm"
              value={form.host}
              onChange={(e) => {
                setPresetKey('');
                setForm((p) => ({ ...p, host: e.target.value }));
              }}
            />
          </div>
          <div>
            <label className="block text-xs font-medium text-gray-600 dark:text-slate-400 mb-1">Port</label>
            <input
              type="number"
              className="w-full border border-gray-300 dark:border-slate-600 rounded-lg px-3 py-2 text-sm"
              value={form.port}
              onChange={(e) => {
                setPresetKey('');
                setForm((p) => ({ ...p, port: Number(e.target.value) || 587 }));
              }}
            />
          </div>
          <div>
            <label className="block text-xs font-medium text-gray-600 dark:text-slate-400 mb-1">Username</label>
            <input
              className="w-full border border-gray-300 dark:border-slate-600 rounded-lg px-3 py-2 text-sm"
              autoComplete="off"
              value={form.username}
              onChange={(e) => setForm((p) => ({ ...p, username: e.target.value }))}
            />
          </div>
          <div className="md:col-span-2">
            <label className="block text-xs font-medium text-gray-600 dark:text-slate-400 mb-1">From email</label>
            <input
              type="email"
              className="w-full border border-gray-300 dark:border-slate-600 rounded-lg px-3 py-2 text-sm"
              value={form.from_email}
              onChange={(e) => setForm((p) => ({ ...p, from_email: e.target.value }))}
            />
          </div>
          <div className="flex flex-wrap items-center gap-6 md:col-span-2">
            <label className="flex items-center gap-2 text-sm">
              <input
                type="checkbox"
                checked={form.use_tls}
                onChange={(e) => {
                  setPresetKey('');
                  const on = e.target.checked;
                  setForm((p) => ({
                    ...p,
                    use_tls: on,
                    use_ssl: on ? false : p.use_ssl,
                    port: on ? 587 : p.port,
                  }));
                }}
              />
              TLS (587)
            </label>
            <label className="flex items-center gap-2 text-sm">
              <input
                type="checkbox"
                checked={form.use_ssl}
                onChange={(e) => {
                  setPresetKey('');
                  const on = e.target.checked;
                  setForm((p) => ({
                    ...p,
                    use_ssl: on,
                    use_tls: on ? false : p.use_tls,
                    port: on ? 465 : p.port,
                  }));
                }}
              />
              SSL (465)
            </label>
            <label className="flex items-center gap-2 text-sm">
              <input
                type="checkbox"
                checked={form.enabled}
                onChange={(e) => setForm((p) => ({ ...p, enabled: e.target.checked }))}
              />
              Enabled
            </label>
            {isNew && (
              <label className="flex items-center gap-2 text-sm text-gray-600 dark:text-slate-400">
                <input
                  type="checkbox"
                  checked={form.is_active}
                  onChange={(e) => setForm((p) => ({ ...p, is_active: e.target.checked }))}
                />
                Set as active after save
              </label>
            )}
          </div>
        </div>

        <div className="flex gap-3">
          <button
            type="submit"
            disabled={saving}
            className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-blue-600 text-white text-sm font-medium hover:bg-blue-700 disabled:opacity-50"
          >
            <FaFloppyDisk /> {saving ? 'Saving...' : isNew ? 'Create profile' : 'Save changes'}
          </button>
          <Link
            to="/admin/smtp-settings"
            className="px-4 py-2 rounded-lg border border-gray-300 dark:border-slate-600 text-sm font-medium text-gray-700 dark:text-slate-300 hover:bg-gray-50 dark:hover:bg-slate-800"
          >
            Cancel
          </Link>
        </div>
      </form>

      {!isNew && (
        <>
          <div className="bg-white dark:bg-slate-900 rounded-xl border border-gray-200 dark:border-slate-700 p-6 shadow-sm space-y-4">
            <h2 className="text-lg font-semibold text-gray-900 dark:text-slate-100">SMTP password</h2>
            <p className="text-sm text-gray-500 dark:text-slate-400">
              {hasPassword
                ? 'Password stored (encrypted). Enter a new value to replace.'
                : 'Required before you can activate or test this profile.'}
            </p>
            <div className="flex flex-col sm:flex-row gap-3">
              <input
                type="password"
                className="flex-1 border border-gray-300 dark:border-slate-600 rounded-lg px-3 py-2 text-sm"
                placeholder="SMTP password or app password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                autoComplete="new-password"
              />
              <button
                type="button"
                disabled={saving}
                onClick={savePassword}
                className="px-4 py-2 rounded-lg border border-gray-300 dark:border-slate-600 text-sm font-medium hover:bg-gray-50 dark:hover:bg-slate-800 disabled:opacity-50"
              >
                Update password
              </button>
            </div>
          </div>

          <div className="bg-white dark:bg-slate-900 rounded-xl border border-gray-200 dark:border-slate-700 p-6 shadow-sm space-y-4">
            <h2 className="text-lg font-semibold text-gray-900 dark:text-slate-100">Test this profile</h2>
            <p className="text-sm text-gray-500 dark:text-slate-400">
              Sends using this profile&apos;s settings (not only if active). Leave recipient blank to use your admin
              email.
            </p>
            <div className="flex flex-col sm:flex-row gap-3">
              <input
                type="email"
                className="flex-1 border border-gray-300 dark:border-slate-600 rounded-lg px-3 py-2 text-sm"
                placeholder="recipient@example.com (optional)"
                value={testEmail}
                onChange={(e) => setTestEmail(e.target.value)}
              />
              <button
                type="button"
                disabled={saving}
                onClick={sendTest}
                className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-indigo-600 text-white text-sm font-medium hover:bg-indigo-700 disabled:opacity-50"
              >
                <FaPaperPlane /> Send test email
              </button>
            </div>
          </div>
        </>
      )}
    </div>
  );
};

export default SmtpProfileForm;
