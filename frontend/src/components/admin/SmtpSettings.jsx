import React, { useCallback, useEffect, useState } from 'react';
import { adminAPI } from '../../services/api';

const SMTP_PRESETS = {
  gmail_tls: {
    label: 'Gmail — 587 TLS',
    host: 'smtp.gmail.com',
    port: 587,
    use_tls: true,
    use_ssl: false,
  },
  gmail_ssl: {
    label: 'Gmail — 465 SSL',
    host: 'smtp.gmail.com',
    port: 465,
    use_tls: false,
    use_ssl: true,
  },
  zoho_tls: {
    label: 'Zoho — 587 TLS',
    host: 'smtppro.zoho.in',
    port: 587,
    use_tls: true,
    use_ssl: false,
  },
  zoho_ssl: {
    label: 'Zoho — 465 SSL',
    host: 'smtppro.zoho.in',
    port: 465,
    use_tls: false,
    use_ssl: true,
  },
  outlook: {
    label: 'Outlook / Microsoft 365 — 587 TLS',
    host: 'smtp.office365.com',
    port: 587,
    use_tls: true,
    use_ssl: false,
  },
};

const defaultForm = {
  name: 'default',
  host: '',
  port: 587,
  use_tls: true,
  use_ssl: false,
  username: '',
  from_email: '',
  enabled: false,
  is_active: false,
};

const applyPreset = (presetKey, setForm) => {
  const preset = SMTP_PRESETS[presetKey];
  if (!preset) return;
  setForm((p) => ({
    ...p,
    host: preset.host,
    port: preset.port,
    use_tls: preset.use_tls,
    use_ssl: preset.use_ssl,
  }));
};

const SmtpSettings = () => {
  const [form, setForm] = useState(defaultForm);
  const [presetKey, setPresetKey] = useState('');
  const [configId, setConfigId] = useState(null);
  const [hasPassword, setHasPassword] = useState(false);
  const [password, setPassword] = useState('');
  const [testEmail, setTestEmail] = useState('');
  const [msg, setMsg] = useState({ type: 'info', text: '' });
  const [saving, setSaving] = useState(false);

  const setBanner = (type, text) => setMsg({ type, text });

  const load = useCallback(async () => {
    const res = await adminAPI.getSmtpConfig();
    if (res.success && res.data?.config) {
      const c = res.data.config;
      setConfigId(c.id);
      setForm((prev) => ({
        ...prev,
        ...c,
        port: Number(c.port) || 587,
        use_tls: !!c.use_tls,
        use_ssl: !!c.use_ssl,
      }));
      setHasPassword(!!c.has_password);
    } else if (!res.success) {
      setBanner('error', res.message || 'Failed to load SMTP config');
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const handlePresetChange = (e) => {
    const key = e.target.value;
    setPresetKey(key);
    if (key) {
      applyPreset(key, setForm);
    }
  };

  const saveConfig = async (e) => {
    e.preventDefault();
    setSaving(true);
    setBanner('info', 'Saving...');
    const res = await adminAPI.saveSmtpConfig(form);
    if (res.success) {
      setBanner('success', res.message || 'SMTP config saved.');
      const c = res.data?.config;
      if (c) {
        setConfigId(c.id);
        setHasPassword(!!c.has_password);
      }
      await load();
    } else {
      const detail =
        res.errors && typeof res.errors === 'object' ? JSON.stringify(res.errors) : '';
      setBanner('error', `${res.message || 'Failed to save'}${detail ? `: ${detail}` : ''}`);
    }
    setSaving(false);
  };

  const savePassword = async () => {
    if (!password.trim()) {
      setBanner('error', 'Enter a password to save.');
      return;
    }
    setSaving(true);
    const res = await adminAPI.updateSmtpSecrets({ password: password.trim() });
    if (res.success) {
      setBanner('success', res.message || 'SMTP password saved.');
      setPassword('');
      setHasPassword(true);
      await load();
    } else {
      setBanner('error', res.message || 'Failed to save password.');
    }
    setSaving(false);
  };

  const sendTest = async () => {
    setSaving(true);
    setBanner('info', 'Sending test email...');
    const res = await adminAPI.testSmtp(testEmail.trim());
    if (res.success) {
      setBanner('success', res.message || 'Test email sent.');
    } else {
      setBanner('error', res.message || 'Test email failed.');
    }
    setSaving(false);
  };

  return (
    <div className="space-y-8 max-w-3xl mx-auto">
      {msg.text && (
        <div
          className={`text-sm border rounded px-4 py-3 ${
            msg.type === 'success'
              ? 'bg-green-50 border-green-200 text-green-800'
              : msg.type === 'error'
                ? 'bg-red-50 border-red-200 text-red-800'
                : 'bg-blue-50 border-blue-200 text-blue-800'
          }`}
        >
          {msg.text}
        </div>
      )}

      <div className="bg-blue-50 border border-blue-200 rounded-xl p-4 text-sm text-blue-950">
        <p className="font-semibold mb-1">SMTP setup (any provider)</p>
        <ul className="list-disc list-inside space-y-1 text-blue-900/90">
          <li>
            Use <strong>587 + TLS</strong> (STARTTLS) or <strong>465 + SSL</strong> — not both TLS and SSL.
          </li>
          <li>Authentication is required: set <strong>username</strong>, <strong>password</strong>, and <strong>from email</strong>.</li>
          <li>
            <strong>Gmail</strong> — host <code className="bg-blue-100 px-1 rounded">smtp.gmail.com</code>; use an{' '}
            <a
              className="text-blue-700 underline"
              href="https://support.google.com/accounts/answer/185833"
              target="_blank"
              rel="noopener noreferrer"
            >
              app password
            </a>{' '}
            if 2FA is enabled.
          </li>
          <li>
            <strong>Zoho</strong> — org domain mail: <code className="bg-blue-100 px-1 rounded">smtppro.zoho.in</code>{' '}
            (India) or <code className="bg-blue-100 px-1 rounded">smtppro.zoho.com</code>. Username and from email must
            be the same mailbox (e.g. <code className="bg-blue-100 px-1 rounded">noreply@yourdomain.com</code>).
          </li>
          <li>
            <strong>Zoho error 554 / Access Restricted</strong> — in Zoho Mail open Settings → Mail Accounts → your
            address → turn on <strong>IMAP Access</strong>; then Security → <strong>App Passwords</strong> → generate one
            and use it as SMTP password here (not your normal login password).
          </li>
          <li>
            <strong>Outlook / Microsoft 365</strong> — host <code className="bg-blue-100 px-1 rounded">smtp.office365.com</code>;
            username is usually the full mailbox address.
          </li>
          <li>
            <strong>Custom</strong> — enter any SMTP host/port (e.g. SendGrid, Amazon SES, your own server).
          </li>
          <li>
            When active, Admin SMTP config is used for password-reset email OTP (overrides env{' '}
            <code className="bg-blue-100 px-1 rounded">EMAIL_*</code>).
          </li>
        </ul>
      </div>

      <form onSubmit={saveConfig} className="bg-white rounded-xl border border-gray-200 p-6 shadow-sm space-y-6">
        <div>
          <h1 className="text-xl font-semibold text-gray-900 mb-1">SMTP Settings</h1>
          <p className="text-sm text-gray-500">
            Transactional email for password-reset OTP.{' '}
            {configId ? <span className="text-gray-700">Config ID: {configId}</span> : 'No config saved yet.'}
          </p>
        </div>

        <div>
          <label className="block text-xs font-medium text-gray-600 mb-1">Apply provider preset</label>
          <select
            className="w-full max-w-md border border-gray-300 rounded-lg px-3 py-2 text-sm bg-white"
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
          <p className="text-xs text-gray-500 mt-1">
            Presets fill host, port, and TLS/SSL only. Username, from email, and password are unchanged.
          </p>
        </div>

        <div className="grid md:grid-cols-2 gap-4">
          <div>
            <label className="block text-xs font-medium text-gray-600 mb-1">Config name</label>
            <input
              className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm"
              value={form.name || ''}
              onChange={(e) => setForm((p) => ({ ...p, name: e.target.value }))}
            />
          </div>
          <div>
            <label className="block text-xs font-medium text-gray-600 mb-1">SMTP host</label>
            <input
              className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm"
              placeholder="e.g. smtp.gmail.com"
              value={form.host || ''}
              onChange={(e) => {
                setPresetKey('');
                setForm((p) => ({ ...p, host: e.target.value }));
              }}
            />
          </div>
          <div>
            <label className="block text-xs font-medium text-gray-600 mb-1">Port</label>
            <input
              type="number"
              className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm"
              value={form.port}
              onChange={(e) => {
                setPresetKey('');
                setForm((p) => ({ ...p, port: Number(e.target.value) || 587 }));
              }}
            />
          </div>
          <div>
            <label className="block text-xs font-medium text-gray-600 mb-1">Username</label>
            <input
              className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm"
              autoComplete="off"
              placeholder="Usually your mailbox email"
              value={form.username || ''}
              onChange={(e) => setForm((p) => ({ ...p, username: e.target.value }))}
            />
          </div>
          <div>
            <label className="block text-xs font-medium text-gray-600 mb-1">From email</label>
            <input
              type="email"
              className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm"
              placeholder="sender@yourdomain.com"
              value={form.from_email || ''}
              onChange={(e) => setForm((p) => ({ ...p, from_email: e.target.value }))}
            />
          </div>
          <div className="flex items-end gap-6 pb-1">
            <label className="flex items-center gap-2 text-sm">
              <input
                type="checkbox"
                checked={!!form.use_tls}
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
              Use TLS (587)
            </label>
            <label className="flex items-center gap-2 text-sm">
              <input
                type="checkbox"
                checked={!!form.use_ssl}
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
              Use SSL (465)
            </label>
          </div>
          <div className="flex items-end gap-6 pb-1 md:col-span-2">
            <label className="flex items-center gap-2 text-sm">
              <input
                type="checkbox"
                checked={!!form.enabled}
                onChange={(e) => setForm((p) => ({ ...p, enabled: e.target.checked }))}
              />
              Enabled
            </label>
            <label className="flex items-center gap-2 text-sm">
              <input
                type="checkbox"
                checked={!!form.is_active}
                onChange={(e) => setForm((p) => ({ ...p, is_active: e.target.checked }))}
              />
              Active (only one active config)
            </label>
          </div>
        </div>

        <button
          type="submit"
          disabled={saving}
          className="px-4 py-2 rounded-lg bg-blue-600 text-white text-sm font-medium hover:bg-blue-700 disabled:opacity-50"
        >
          {saving ? 'Saving...' : 'Save SMTP config'}
        </button>
      </form>

      <div className="bg-white rounded-xl border border-gray-200 p-6 shadow-sm space-y-4">
        <h2 className="text-lg font-semibold text-gray-900">SMTP password</h2>
        <p className="text-sm text-gray-500">
          {hasPassword ? 'A password is stored (encrypted). Enter a new value to replace it.' : 'No password stored yet.'}
        </p>
        <div className="flex flex-col sm:flex-row gap-3 max-w-xl">
          <input
            type="password"
            className="flex-1 border border-gray-300 rounded-lg px-3 py-2 text-sm"
            placeholder="SMTP password or app password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            autoComplete="new-password"
          />
          <button
            type="button"
            disabled={saving}
            onClick={savePassword}
            className="px-4 py-2 rounded-lg border border-gray-300 text-sm font-medium hover:bg-gray-50 disabled:opacity-50"
          >
            Update password
          </button>
        </div>
      </div>

      <div className="bg-white rounded-xl border border-gray-200 p-6 shadow-sm space-y-4">
        <h2 className="text-lg font-semibold text-gray-900">Test connection</h2>
        <p className="text-sm text-gray-500">
          Sends a test message using the saved active config. Leave blank to use your admin account email.
        </p>
        <div className="flex flex-col sm:flex-row gap-3 max-w-xl">
          <input
            type="email"
            className="w-full flex-1 border border-gray-300 rounded-lg px-3 py-2 text-sm"
            placeholder="recipient@example.com (optional)"
            value={testEmail}
            onChange={(e) => setTestEmail(e.target.value)}
          />
          <button
            type="button"
            disabled={saving}
            onClick={sendTest}
            className="px-4 py-2 rounded-lg bg-indigo-600 text-white text-sm font-medium hover:bg-indigo-700 disabled:opacity-50"
          >
            Send test email
          </button>
        </div>
      </div>
    </div>
  );
};

export default SmtpSettings;
