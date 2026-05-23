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
        provider: c.provider || 'msg91',
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
    setSaving(true);
    setBanner('info', 'Saving profile...');
    const payload = {
      ...form,
      name: form.name.trim(),
      country_code: String(form.country_code || '91').replace(/\D/g, '') || '91',
    };
    const res = isNew
      ? await adminAPI.createSmsConfig(payload)
      : await adminAPI.updateSmsConfig(id, payload);
    if (res.success) {
      const saved = res.data?.config;
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
      setBanner('error', 'Save the profile first, then set the auth key.');
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
      <div className="max-w-3xl mx-auto p-12 text-center text-gray-500">Loading profile...</div>
    );
  }

  return (
    <div className="space-y-6 max-w-3xl mx-auto">
      <Link
        to="/admin/sms-settings"
        className="inline-flex items-center gap-1.5 text-sm text-gray-600 hover:text-gray-900"
      >
        <FaArrowLeft className="w-3.5 h-3.5" /> Back to profiles
      </Link>

      {msg.text && (
        <div
          className={`text-sm border rounded-lg px-4 py-3 ${
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

      <form onSubmit={saveProfile} className="bg-white rounded-xl border border-gray-200 p-6 shadow-sm space-y-6">
        <div>
          <h1 className="text-xl font-semibold text-gray-900">
            {isNew ? 'New SMS profile' : `Edit: ${form.name}`}
          </h1>
          <p className="text-sm text-gray-500 mt-1">
            {isNew
              ? 'Create an MSG91 account profile. Activate from the list when ready.'
              : form.is_active
                ? 'This profile is active for all outbound SMS.'
                : 'Not active — activate from the profile list when ready.'}
          </p>
        </div>

        <div className="grid md:grid-cols-2 gap-4">
          <div>
            <label className="block text-xs font-medium text-gray-600 mb-1">Profile name (unique)</label>
            <input
              required
              className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm"
              placeholder="e.g. msg91-production"
              value={form.name}
              onChange={(e) => setForm((p) => ({ ...p, name: e.target.value }))}
            />
          </div>
          <div>
            <label className="block text-xs font-medium text-gray-600 mb-1">Provider</label>
            <select
              className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm bg-white"
              value={form.provider}
              onChange={(e) => setForm((p) => ({ ...p, provider: e.target.value }))}
            >
              <option value="msg91">MSG91</option>
              <option value="console">Console (dev log only)</option>
            </select>
          </div>
          <div>
            <label className="block text-xs font-medium text-gray-600 mb-1">DLT Sender ID</label>
            <input
              className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm"
              value={form.sender_id}
              onChange={(e) => setForm((p) => ({ ...p, sender_id: e.target.value }))}
            />
          </div>
          <div>
            <label className="block text-xs font-medium text-gray-600 mb-1">Country code</label>
            <input
              className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm"
              value={form.country_code}
              onChange={(e) => setForm((p) => ({ ...p, country_code: e.target.value }))}
            />
          </div>
          <div className="md:col-span-2">
            <label className="block text-xs font-medium text-gray-600 mb-1">API base URL</label>
            <input
              className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm"
              value={form.api_base_url}
              onChange={(e) => setForm((p) => ({ ...p, api_base_url: e.target.value }))}
            />
          </div>
          <div>
            <label className="block text-xs font-medium text-gray-600 mb-1">Route (optional)</label>
            <input
              className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm"
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
              <label className="flex items-center gap-2 text-sm text-gray-600">
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
            className="px-4 py-2 rounded-lg border border-gray-300 text-sm font-medium text-gray-700 hover:bg-gray-50"
          >
            Cancel
          </Link>
        </div>
      </form>

      {!isNew && form.provider === 'msg91' && (
        <div className="bg-white rounded-xl border border-gray-200 p-6 shadow-sm space-y-4">
          <h2 className="text-lg font-semibold text-gray-900">MSG91 auth key</h2>
          <p className="text-sm text-gray-500">
            {hasAuthKey
              ? 'Auth key stored (encrypted). Enter a new value to replace.'
              : 'Required before you can activate or test this profile.'}
          </p>
          <div className="flex flex-col sm:flex-row gap-3">
            <input
              type="password"
              className="flex-1 border border-gray-300 rounded-lg px-3 py-2 text-sm"
              placeholder="MSG91 authkey"
              value={authKey}
              onChange={(e) => setAuthKey(e.target.value)}
              autoComplete="new-password"
            />
            <button
              type="button"
              disabled={saving}
              onClick={saveAuthKey}
              className="px-4 py-2 rounded-lg border border-gray-300 text-sm font-medium hover:bg-gray-50 disabled:opacity-50"
            >
              Update auth key
            </button>
          </div>
        </div>
      )}

      {!isNew && (
        <div className="bg-white rounded-xl border border-gray-200 p-6 shadow-sm space-y-4">
          <h2 className="text-lg font-semibold text-gray-900">Test this profile</h2>
          <p className="text-sm text-gray-500">
            Sends using this profile&apos;s credentials (not only if active). Use an approved DLT template ID.
          </p>
          <div className="flex flex-col sm:flex-row gap-3">
            <input
              className="flex-1 border border-gray-300 rounded-lg px-3 py-2 text-sm"
              placeholder="10-digit mobile"
              value={testPhone}
              onChange={(e) => setTestPhone(e.target.value)}
            />
            <input
              className="flex-1 border border-gray-300 rounded-lg px-3 py-2 text-sm"
              placeholder="DLT template ID"
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

      <p className="text-sm text-gray-500">
        <a
          href="https://docs.msg91.com/overview"
          target="_blank"
          rel="noopener noreferrer"
          className="text-blue-600 underline"
        >
          MSG91 documentation
        </a>
        {' · '}
        <Link to="/admin/sms-settings/templates" className="text-blue-600 underline">
          Configure event templates
        </Link>
      </p>
    </div>
  );
};

export default SmsProfileForm;
