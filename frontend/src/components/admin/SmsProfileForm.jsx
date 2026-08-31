import React, { useCallback, useEffect, useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import { adminAPI } from '../../services/api';
import { defaultSmsForm, formatApiErrors } from './smsUtils';
import { FaArrowLeft, FaFloppyDisk, FaPaperPlane } from 'react-icons/fa6';

const SmsProfileForm = () => {
  const { id } = useParams();
  const isNew = !id || id === 'new';
  const navigate = useNavigate();
  const [form, setForm] = useState(defaultSmsForm);
  const [hasAuthKey, setHasAuthKey] = useState(false);
  const [authKey, setAuthKey] = useState('');
  const [testPhone, setTestPhone] = useState('');
  const [testTemplateId, setTestTemplateId] = useState('');
  const [loading, setLoading] = useState(!isNew);
  const [saving, setSaving] = useState(false);
  const [msg, setMsg] = useState({ type: '', text: '' });

  const setBanner = (type, text) => setMsg({ type, text });

  const loadProfile = useCallback(async () => {
    if (isNew) return;
    setLoading(true);
    const res = await adminAPI.getSmsConfigById(id);
    if (res.success && res.data?.config) {
      const c = res.data.config;
      setForm({
        name: c.name || '',
        provider: 'msg91',
        sender_id: c.sender_id || '',
        enabled: !!c.enabled,
        is_active: !!c.is_active,
        api_base_url: c.api_base_url || 'https://control.msg91.com',
        route: c.route || '',
        country_code: c.country_code || '91',
      });
      setHasAuthKey(!!c.has_auth_key);
    } else {
      setBanner('error', res.message || 'Profile not found');
      navigate('/admin/sms-settings', { replace: true });
    }
    setLoading(false);
  }, [id, isNew, navigate]);

  useEffect(() => {
    loadProfile();
  }, [loadProfile]);

  const saveProfile = async (e) => {
    e.preventDefault();
    if (!form.name?.trim()) {
      setBanner('error', 'Profile name is required.');
      return;
    }
    if (isNew && !authKey.trim()) {
      setBanner('error', 'MSG91 auth key is required to create a profile.');
      return;
    }
    if (!form.sender_id?.trim()) {
      setBanner('error', 'DLT Sender ID is required (e.g. MPAYHB).');
      return;
    }
    setSaving(true);
    setBanner('info', 'Saving profile...');
    const payload = {
      name: form.name.trim(),
      provider: 'msg91',
      sender_id: form.sender_id.trim(),
      enabled: !!form.enabled,
      is_active: !!form.is_active,
      api_base_url: (form.api_base_url || 'https://control.msg91.com').trim(),
      route: (form.route || '').trim(),
      country_code: String(form.country_code || '91').replace(/\D/g, '') || '91',
    };
    if (isNew) {
      payload.auth_key = authKey.trim();
    }
    const res = isNew
      ? await adminAPI.createSmsConfig(payload)
      : await adminAPI.updateSmsConfig(id, payload);
    if (res.success) {
      const saved = res.data?.config;
      if (!isNew && authKey.trim()) {
        const secretRes = await adminAPI.updateSmsSecrets(id, { auth_key: authKey.trim() });
        if (!secretRes.success) {
          setBanner('error', secretRes.message || 'Profile saved but auth key update failed');
          setSaving(false);
          return;
        }
        setAuthKey('');
        setHasAuthKey(true);
      }
      setBanner('success', res.message || 'Profile saved');
      if (isNew && saved?.id) {
        navigate(`/admin/sms-settings/${saved.id}/edit`, { replace: true });
      } else {
        await loadProfile();
      }
    } else {
      const detail = formatApiErrors(res.errors);
      setBanner('error', `${res.message || 'Save failed'}${detail ? ` — ${detail}` : ''}`);
    }
    setSaving(false);
  };

  const saveAuthKey = async () => {
    if (isNew) {
      setBanner('error', 'Enter the auth key above and click Create profile.');
      return;
    }
    if (!authKey.trim()) {
      setBanner('error', 'Enter an MSG91 auth key to save.');
      return;
    }
    setSaving(true);
    const res = await adminAPI.updateSmsSecrets(id, { auth_key: authKey.trim() });
    if (res.success) {
      setBanner('success', res.message || 'Auth key saved');
      setAuthKey('');
      setHasAuthKey(true);
    } else {
      setBanner('error', res.message || 'Failed to save auth key');
    }
    setSaving(false);
  };

  const sendTest = async () => {
    if (isNew) {
      setBanner('error', 'Save the profile before sending a test SMS.');
      return;
    }
    if (!hasAuthKey && !authKey.trim()) {
      setBanner('error', 'Set an MSG91 auth key before testing.');
      return;
    }
    if (!testPhone.trim() || !testTemplateId.trim()) {
      setBanner('error', 'Test phone and DLT template ID are required.');
      return;
    }
    setSaving(true);
    setBanner('info', 'Sending test SMS...');
    const res = await adminAPI.testSms(id, {
      phone: testPhone.trim(),
      template_id: testTemplateId.trim(),
    });
    if (res.success) {
      setBanner('success', res.message || 'Test SMS sent');
    } else {
      setBanner('error', res.message || 'Test SMS failed');
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
      <Link
        to="/admin/sms-settings"
        className="inline-flex items-center gap-1.5 text-sm text-gray-600 dark:text-slate-400 hover:text-gray-900 dark:hover:text-slate-100"
      >
        <FaArrowLeft className="w-3.5 h-3.5" /> Back to profiles
      </Link>

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
            {isNew ? 'New SMS profile' : `Edit: ${form.name}`}
          </h1>
          <p className="text-sm text-gray-500 dark:text-slate-400 mt-1">
            {isNew
              ? 'Add your MSG91 auth key and DLT sender. Then map Flow templates under Event templates.'
              : form.is_active
                ? 'This profile is active for all outbound SMS.'
                : 'Not active — activate from the profile list when ready.'}
          </p>
        </div>

        <div className="grid md:grid-cols-2 gap-4">
          <div>
            <label className="block text-xs font-medium text-gray-600 dark:text-slate-400 mb-1">Profile name (unique)</label>
            <input
              required
              className="w-full border border-gray-300 dark:border-slate-600 rounded-lg px-3 py-2 text-sm"
              placeholder="e.g. msg91-production"
              value={form.name}
              onChange={(e) => setForm((p) => ({ ...p, name: e.target.value }))}
            />
          </div>
          <div>
            <label className="block text-xs font-medium text-gray-600 dark:text-slate-400 mb-1">Provider</label>
            <input
              className="w-full border border-gray-200 dark:border-slate-700 rounded-lg px-3 py-2 text-sm bg-gray-50 dark:bg-slate-800/50 text-gray-700 dark:text-slate-300"
              value="MSG91"
              readOnly
            />
          </div>
          <div className="md:col-span-2">
            <label className="block text-xs font-medium text-gray-600 dark:text-slate-400 mb-1">
              MSG91 auth key {isNew ? <span className="text-red-600 dark:text-red-400">*</span> : null}
            </label>
            <input
              type="password"
              className="w-full border border-gray-300 dark:border-slate-600 rounded-lg px-3 py-2 text-sm font-mono"
              placeholder={
                isNew
                  ? 'Paste MSG91 authkey from control.msg91.com'
                  : hasAuthKey
                    ? '••••••••  (leave blank to keep current key)'
                    : 'Paste MSG91 authkey'
              }
              value={authKey}
              onChange={(e) => setAuthKey(e.target.value)}
              autoComplete="new-password"
              required={isNew}
            />
            <p className="text-xs text-gray-500 dark:text-slate-400 mt-1">
              Stored encrypted. Never shown again after save.
              {!isNew && hasAuthKey ? ' Key is already configured on this profile.' : ''}
            </p>
            {!isNew ? (
              <button
                type="button"
                disabled={saving || !authKey.trim()}
                onClick={saveAuthKey}
                className="mt-2 text-xs px-3 py-1.5 rounded border border-gray-300 dark:border-slate-600 hover:bg-gray-50 dark:hover:bg-slate-800 disabled:opacity-50"
              >
                Update auth key only
              </button>
            ) : null}
          </div>
          <div>
            <label className="block text-xs font-medium text-gray-600 dark:text-slate-400 mb-1">
              DLT Sender ID <span className="text-red-600 dark:text-red-400">*</span>
            </label>
            <input
              required
              className="w-full border border-gray-300 dark:border-slate-600 rounded-lg px-3 py-2 text-sm"
              placeholder="e.g. MPAYHB"
              value={form.sender_id}
              onChange={(e) => setForm((p) => ({ ...p, sender_id: e.target.value }))}
            />
          </div>
          <div>
            <label className="block text-xs font-medium text-gray-600 dark:text-slate-400 mb-1">Country code</label>
            <input
              className="w-full border border-gray-300 dark:border-slate-600 rounded-lg px-3 py-2 text-sm"
              value={form.country_code}
              onChange={(e) => setForm((p) => ({ ...p, country_code: e.target.value }))}
            />
          </div>
          <div className="md:col-span-2">
            <label className="block text-xs font-medium text-gray-600 dark:text-slate-400 mb-1">API base URL</label>
            <input
              className="w-full border border-gray-300 dark:border-slate-600 rounded-lg px-3 py-2 text-sm"
              value={form.api_base_url}
              onChange={(e) => setForm((p) => ({ ...p, api_base_url: e.target.value }))}
            />
          </div>
          <div>
            <label className="block text-xs font-medium text-gray-600 dark:text-slate-400 mb-1">Route (optional)</label>
            <input
              className="w-full border border-gray-300 dark:border-slate-600 rounded-lg px-3 py-2 text-sm"
              placeholder="Leave blank unless MSG91 assigned a route"
              value={form.route}
              onChange={(e) => setForm((p) => ({ ...p, route: e.target.value }))}
            />
          </div>
          <div className="flex flex-wrap items-center gap-6">
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
            to="/admin/sms-settings"
            className="px-4 py-2 rounded-lg border border-gray-300 dark:border-slate-600 text-sm font-medium text-gray-700 dark:text-slate-300 hover:bg-gray-50 dark:hover:bg-slate-800"
          >
            Cancel
          </Link>
        </div>
      </form>

      {!isNew && (
        <div className="bg-white dark:bg-slate-900 rounded-xl border border-gray-200 dark:border-slate-700 p-6 shadow-sm space-y-4">
          <h2 className="text-lg font-semibold text-gray-900 dark:text-slate-100">Test this profile</h2>
          <p className="text-sm text-gray-500 dark:text-slate-400">
            Sends a real MSG91 Flow SMS with this profile&apos;s auth key. Use an approved DLT template ID.
          </p>
          <div className="flex flex-col sm:flex-row gap-3">
            <input
              className="flex-1 border border-gray-300 dark:border-slate-600 rounded-lg px-3 py-2 text-sm"
              placeholder="10-digit mobile"
              value={testPhone}
              onChange={(e) => setTestPhone(e.target.value)}
            />
            <input
              className="flex-1 border border-gray-300 dark:border-slate-600 rounded-lg px-3 py-2 text-sm"
              placeholder="MSG91 template_id"
              value={testTemplateId}
              onChange={(e) => setTestTemplateId(e.target.value)}
            />
            <button
              type="button"
              disabled={saving}
              onClick={sendTest}
              className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-indigo-600 text-white text-sm font-medium hover:bg-indigo-700 disabled:opacity-50"
            >
              <FaPaperPlane /> Send test SMS
            </button>
          </div>
        </div>
      )}

      <p className="text-sm text-gray-500 dark:text-slate-400">
        <a
          href="https://docs.msg91.com/overview"
          target="_blank"
          rel="noopener noreferrer"
          className="text-blue-600 dark:text-blue-400 underline"
        >
          MSG91 documentation
        </a>
        {' · '}
        <Link to="/admin/sms-settings/templates" className="text-blue-600 dark:text-blue-400 underline">
          Configure event templates
        </Link>
      </p>
    </div>
  );
};

export default SmsProfileForm;
