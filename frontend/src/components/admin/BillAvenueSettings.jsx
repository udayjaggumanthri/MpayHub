import React, { useCallback, useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { billAvenueAdminAPI } from '../../services/api';

const defaultForm = {
  name: 'default',
  mode: 'uat',
  api_format: 'json',
  crypto_key_derivation: 'md5',
  enc_request_encoding: 'hex',
  allow_variant_fallback: true,
  allow_txn_status_path_fallback: true,
  base_url: '',
  access_code: '',
  institute_id: '',
  request_version: '1.0',
  connect_timeout_seconds: 30,
  read_timeout_seconds: 60,
  max_retries: 2,
  mdm_refresh_hours: 24,
  mdm_max_calls_per_day: 15,
  push_callback_url: '',
  enabled: false,
  is_active: false,
  bbps_wallet_service_charge_mode: 'FLAT',
  bbps_wallet_service_charge_flat: 5,
  bbps_wallet_service_charge_percent: 0,
};

const BillAvenueSettings = () => {
  const [form, setForm] = useState(defaultForm);
  const [configId, setConfigId] = useState(null);
  const [hasSecrets, setHasSecrets] = useState({
    has_working_key: false,
    has_iv: false,
    has_callback_secret: false,
  });
  const [secrets, setSecrets] = useState({ working_key: '', iv: '', callback_secret: '' });
  const [msg, setMsg] = useState({ type: 'info', text: '' });
  const [saving, setSaving] = useState(false);
  const [agentProfiles, setAgentProfiles] = useState([]);
  const [agentForm, setAgentForm] = useState({
    name: 'AGT default',
    agent_id: '',
    init_channel: 'AGT',
    require_ip: true,
    require_mac: false,
    require_imei: false,
    require_os: false,
    require_app: false,
    enabled: true,
  });

  const setBanner = (type, text) => setMsg({ type, text });

  const load = useCallback(async () => {
    const res = await billAvenueAdminAPI.getConfig();
    if (res.success && res.data?.config) {
      const c = { ...res.data.config };
      setConfigId(c.id);
      setForm((prev) => ({
        ...prev,
        ...c,
        request_version: c.request_version || '1.0',
        crypto_key_derivation: c.crypto_key_derivation || 'md5',
        enc_request_encoding: c.enc_request_encoding || 'hex',
        allow_variant_fallback: c.allow_variant_fallback ?? true,
        allow_txn_status_path_fallback: c.allow_txn_status_path_fallback ?? true,
        connect_timeout_seconds: c.connect_timeout_seconds ?? 30,
        read_timeout_seconds: c.read_timeout_seconds ?? 60,
        max_retries: c.max_retries ?? 2,
        mdm_refresh_hours: c.mdm_refresh_hours ?? 24,
        mdm_max_calls_per_day: c.mdm_max_calls_per_day ?? 15,
        bbps_wallet_service_charge_mode: c.bbps_wallet_service_charge_mode || 'FLAT',
        bbps_wallet_service_charge_flat: Number(c.bbps_wallet_service_charge_flat ?? 5),
        bbps_wallet_service_charge_percent: Number(c.bbps_wallet_service_charge_percent ?? 0),
      }));
      setHasSecrets({
        has_working_key: !!c.has_working_key,
        has_iv: !!c.has_iv,
        has_callback_secret: !!c.has_callback_secret,
      });
    } else {
      setConfigId(null);
      setForm((prev) => ({ ...defaultForm, name: prev.name || 'default' }));
    }
  }, []);

  const loadAgentProfiles = useCallback(async () => {
    const res = await billAvenueAdminAPI.listAgentProfiles();
    if (res.success && res.data?.profiles) setAgentProfiles(res.data.profiles);
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  useEffect(() => {
    if (configId) loadAgentProfiles();
  }, [configId, loadAgentProfiles]);

  const saveConfig = async () => {
    setSaving(true);
    setBanner('info', '');
    const {
      has_working_key: _hwk,
      has_iv: _hiv,
      has_callback_secret: _hcs,
      id: _id,
      activated_at: _aa,
      created_at: _ca,
      updated_at: _ua,
      ...configPayload
    } = form;
    const res = await billAvenueAdminAPI.saveConfig(configPayload);
    if (res.success) {
      setBanner('success', `Config saved. Updated: ${res.data?.config?.updated_at || 'OK'}.`);
      await load();
    } else {
      setBanner('error', res.message || res.errors || 'Failed to save config');
    }
    setSaving(false);
  };

  const saveSecrets = async () => {
    setSaving(true);
    setBanner('info', '');
    const res = await billAvenueAdminAPI.updateSecrets(secrets);
    if (res.success) {
      setBanner('success', 'Secrets saved (stored encrypted).');
      if (res.data?.config) {
        setHasSecrets({
          has_working_key: !!res.data.config.has_working_key,
          has_iv: !!res.data.config.has_iv,
          has_callback_secret: !!res.data.config.has_callback_secret,
        });
        setConfigId(res.data.config.id);
      } else {
        await load();
      }
      setSecrets({ working_key: '', iv: '', callback_secret: '' });
    } else {
      setBanner('error', res.message || 'Failed to save secrets');
    }
    setSaving(false);
  };

  const saveAgentProfile = async (e) => {
    e.preventDefault();
    if (!configId) {
      setBanner('error', 'Save BillAvenue config first, then add Agent ID.');
      return;
    }
    if (!agentForm.agent_id.trim()) {
      setBanner('error', 'Enter Agent ID from BillAvenue (e.g. for AGT channel).');
      return;
    }
    setSaving(true);
    const res = await billAvenueAdminAPI.createAgentProfile({
      config: configId,
      name: agentForm.name,
      agent_id: agentForm.agent_id.trim(),
      init_channel: agentForm.init_channel,
      require_ip: agentForm.require_ip,
      require_mac: agentForm.require_mac,
      require_imei: agentForm.require_imei,
      require_os: agentForm.require_os,
      require_app: agentForm.require_app,
      enabled: agentForm.enabled,
    });
    if (res.success) {
      setBanner('success', 'Agent profile saved.');
      setAgentForm((p) => ({ ...p, id: res.data?.profile?.id || p.id, agent_id: '' }));
      await loadAgentProfiles();
    } else {
      const detail = res.errors && typeof res.errors === 'object' ? JSON.stringify(res.errors) : '';
      setBanner('error', `${res.message || 'Failed to save agent profile'}${detail ? `: ${detail}` : ''}`);
    }
    setSaving(false);
  };

  return (
    <div className="space-y-8 max-w-4xl mx-auto">
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

      <div className="bg-amber-50 border border-amber-200 rounded-xl p-4 text-sm text-amber-950">
        <p className="font-semibold mb-1">After credentials are saved</p>
        <ol className="list-decimal list-inside space-y-1 text-amber-900/90">
          <li>
            Set <strong>API version (ver)</strong> — use <code className="bg-amber-100 px-1 rounded">1.0</code> for most APIs; BillAvenue docs require{' '}
            <code className="bg-amber-100 px-1 rounded">2.0</code> for complaint register/track.
          </li>
          <li>
            Add your <strong>Agent ID</strong> (per channel) in the section below — this is <em>not</em> the same as Institute ID.
          </li>
          <li>
            Go to{' '}
            <Link className="text-blue-700 font-medium underline" to="/admin/bbps-governance">
              Provider Governance
            </Link>{' '}
            and use <strong>Run Biller Sync</strong> there to load biller master data (providers / biller catalogue).
          </li>
        </ol>
      </div>

      <div className="bg-white rounded-xl border border-gray-200 p-6 shadow-sm">
        <h1 className="text-xl font-semibold text-gray-900 mb-1">BillAvenue Settings</h1>
        <p className="text-sm text-gray-500 mb-6">
          Connection details for the active BillAvenue config. {configId ? <span className="text-gray-700">Config ID: {configId}</span> : null}
        </p>

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
            <label className="block text-xs font-medium text-gray-600 mb-1">Base URL (host only, no /billpay path)</label>
            <input
              className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm"
              placeholder="https://stgapi.billavenue.com"
              value={form.base_url || ''}
              onChange={(e) => setForm((p) => ({ ...p, base_url: e.target.value }))}
            />
          </div>
          <div>
            <label className="block text-xs font-medium text-gray-600 mb-1">Access code</label>
            <input
              className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm"
              value={form.access_code || ''}
              onChange={(e) => setForm((p) => ({ ...p, access_code: e.target.value }))}
            />
          </div>
          <div>
            <label className="block text-xs font-medium text-gray-600 mb-1">Institute ID (Agent Institution ID)</label>
            <input
              className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm"
              placeholder="e.g. PI39"
              value={form.institute_id || ''}
              onChange={(e) => setForm((p) => ({ ...p, institute_id: e.target.value }))}
            />
          </div>
          <div>
            <label className="block text-xs font-medium text-gray-600 mb-1">API version (ver)</label>
            <select
              className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm"
              value={form.request_version || '1.0'}
              onChange={(e) => setForm((p) => ({ ...p, request_version: e.target.value }))}
            >
              <option value="1.0">1.0 — Biller, fetch, pay, status (default)</option>
              <option value="2.0">2.0 — Complaint register / track (per BillAvenue spec)</option>
            </select>
            <p className="text-xs text-gray-500 mt-1">If you use complaints APIs, you may need a second deployment or code path for ver 2.0.</p>
          </div>
          <div>
            <label className="block text-xs font-medium text-gray-600 mb-1">Environment</label>
            <select
              className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm"
              value={form.mode || 'uat'}
              onChange={(e) => setForm((p) => ({ ...p, mode: e.target.value }))}
            >
              <option value="uat">UAT</option>
              <option value="prod">Production</option>
            </select>
          </div>
          <div>
            <label className="block text-xs font-medium text-gray-600 mb-1">Payload format</label>
            <select
              className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm"
              value={form.api_format || 'json'}
              onChange={(e) => setForm((p) => ({ ...p, api_format: e.target.value }))}
            >
              <option value="json">JSON</option>
              <option value="xml">XML</option>
            </select>
          </div>
          <div>
            <label className="block text-xs font-medium text-gray-600 mb-1">Key derivation</label>
            <select
              className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm"
              value={form.crypto_key_derivation || 'md5'}
              onChange={(e) => setForm((p) => ({ ...p, crypto_key_derivation: e.target.value }))}
            >
              <option value="rawhex">Raw hex (decode 32-hex working key)</option>
              <option value="md5">MD5 (PHP sample style)</option>
            </select>
            <p className="text-xs text-gray-500 mt-1">UAT CLI success used MD5. Use Raw hex only if BillAvenue confirms it for your institute.</p>
          </div>
          <div>
            <label className="block text-xs font-medium text-gray-600 mb-1">encRequest encoding</label>
            <select
              className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm"
              value={form.enc_request_encoding || 'hex'}
              onChange={(e) => setForm((p) => ({ ...p, enc_request_encoding: e.target.value }))}
            >
              <option value="base64">Base64</option>
              <option value="hex">Hex</option>
            </select>
            <p className="text-xs text-gray-500 mt-1">UAT CLI success used Hex for encRequest.</p>
          </div>
        </div>

        <div className="mt-6 pt-4 border-t border-gray-200">
          <h2 className="text-lg font-semibold text-gray-900 mb-1">BBPS wallet service charge</h2>
          <p className="text-sm text-gray-500 mb-4">
            Shown on the pay screen (quote) before Proceed to Pay, and deducted from the user BBPS wallet together with
            the bill amount. This is separate from BillAvenue biller CCF fields sent in pay payload.
          </p>
          <div className="grid md:grid-cols-2 gap-4">
            <div>
              <label className="block text-xs font-medium text-gray-600 mb-1">Charge type</label>
              <select
                className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm"
                value={form.bbps_wallet_service_charge_mode || 'FLAT'}
                onChange={(e) => setForm((p) => ({ ...p, bbps_wallet_service_charge_mode: e.target.value }))}
              >
                <option value="FLAT">Flat (fixed INR)</option>
                <option value="PERCENT">Percent of bill amount</option>
              </select>
            </div>
            <div>
              <label className="block text-xs font-medium text-gray-600 mb-1">Flat amount (INR)</label>
              <input
                type="number"
                min={0}
                step="0.01"
                className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm"
                value={form.bbps_wallet_service_charge_flat ?? 0}
                onChange={(e) =>
                  setForm((p) => ({ ...p, bbps_wallet_service_charge_flat: parseFloat(e.target.value) || 0 }))
                }
                disabled={(form.bbps_wallet_service_charge_mode || 'FLAT') !== 'FLAT'}
              />
            </div>
            <div className="md:col-span-2">
              <label className="block text-xs font-medium text-gray-600 mb-1">Percent of bill (%)</label>
              <input
                type="number"
                min={0}
                max={100}
                step="0.0001"
                className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm"
                value={form.bbps_wallet_service_charge_percent ?? 0}
                onChange={(e) =>
                  setForm((p) => ({ ...p, bbps_wallet_service_charge_percent: parseFloat(e.target.value) || 0 }))
                }
                disabled={(form.bbps_wallet_service_charge_mode || 'FLAT') !== 'PERCENT'}
              />
              <p className="text-xs text-gray-500 mt-1">Example: 1.25 means 1.25% of the bill amount.</p>
            </div>
          </div>
        </div>

        <div className="grid md:grid-cols-2 gap-4 mt-4">
          <div>
            <label className="block text-xs font-medium text-gray-600 mb-1">Connect timeout (seconds)</label>
            <input
              type="number"
              min={5}
              className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm"
              value={form.connect_timeout_seconds}
              onChange={(e) => setForm((p) => ({ ...p, connect_timeout_seconds: parseInt(e.target.value, 10) || 30 }))}
            />
          </div>
          <div>
            <label className="block text-xs font-medium text-gray-600 mb-1">Read timeout (seconds)</label>
            <input
              type="number"
              min={5}
              className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm"
              value={form.read_timeout_seconds}
              onChange={(e) => setForm((p) => ({ ...p, read_timeout_seconds: parseInt(e.target.value, 10) || 60 }))}
            />
          </div>
        </div>

        <div className="mt-4">
          <label className="block text-xs font-medium text-gray-600 mb-1">Push / callback URL (optional)</label>
          <input
            className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm"
            placeholder="https://your-domain/api/bbps/callback/billavenue/"
            value={form.push_callback_url || ''}
            onChange={(e) => setForm((p) => ({ ...p, push_callback_url: e.target.value }))}
          />
        </div>

        <div className="flex flex-wrap gap-6 mt-4 text-sm">
          <label className="inline-flex items-center gap-2">
            <input
              type="checkbox"
              checked={!!form.enabled}
              onChange={(e) => setForm((p) => ({ ...p, enabled: e.target.checked }))}
            />
            <span>Enabled (integration on)</span>
          </label>
          <label className="inline-flex items-center gap-2">
            <input
              type="checkbox"
              checked={!!form.is_active}
              onChange={(e) => setForm((p) => ({ ...p, is_active: e.target.checked }))}
            />
            <span>Active (this row is the one used at runtime)</span>
          </label>
          <label className="inline-flex items-center gap-2">
            <input
              type="checkbox"
              checked={!!form.allow_variant_fallback}
              onChange={(e) => setForm((p) => ({ ...p, allow_variant_fallback: e.target.checked }))}
            />
            <span>Allow safe provider fallbacks (recommended)</span>
          </label>
          <label className="inline-flex items-center gap-2">
            <input
              type="checkbox"
              checked={!!form.allow_txn_status_path_fallback}
              onChange={(e) => setForm((p) => ({ ...p, allow_txn_status_path_fallback: e.target.checked }))}
            />
            <span>Txn status 404 HTML path fallback</span>
          </label>
        </div>
        {form.updated_at && (
          <p className="text-xs text-gray-500 mt-2">Last saved: {form.updated_at}</p>
        )}
        <button
          type="button"
          disabled={saving}
          onClick={saveConfig}
          className="mt-4 px-5 py-2.5 bg-blue-600 text-white text-sm font-medium rounded-lg hover:bg-blue-700 disabled:opacity-50"
        >
          {saving ? 'Saving…' : 'Save config'}
        </button>
      </div>

      <div className="bg-white rounded-xl border border-gray-200 p-6 shadow-sm">
        <h2 className="text-lg font-semibold text-gray-900 mb-1">Encrypted secrets</h2>
        <p className="text-sm text-gray-500 mb-4">
          Working key and IV are required for encryption. Values are not shown after save — only status below.
        </p>
        <div className="flex flex-wrap gap-2 mb-4">
          <span
            className={`text-xs px-2 py-1 rounded border ${hasSecrets.has_working_key ? 'bg-green-50 border-green-200 text-green-800' : 'bg-gray-50 border-gray-200 text-gray-600'}`}
          >
            Working key: {hasSecrets.has_working_key ? 'stored' : 'not set'}
          </span>
          <span
            className={`text-xs px-2 py-1 rounded border ${hasSecrets.has_iv ? 'bg-green-50 border-green-200 text-green-800' : 'bg-amber-50 border-amber-200 text-amber-900'}`}
          >
            IV: {hasSecrets.has_iv ? 'stored' : 'not set (required)'}
          </span>
          <span
            className={`text-xs px-2 py-1 rounded border ${hasSecrets.has_callback_secret ? 'bg-green-50 border-green-200 text-green-800' : 'bg-gray-50 border-gray-200 text-gray-600'}`}
          >
            Callback secret: {hasSecrets.has_callback_secret ? 'stored' : 'optional'}
          </span>
        </div>
        <div className="grid md:grid-cols-3 gap-4">
          <div>
            <label className="block text-xs font-medium text-gray-600 mb-1">Working key</label>
            <input
              className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm font-mono"
              type="password"
              autoComplete="off"
              placeholder={hasSecrets.has_working_key ? '•••• leave blank to keep' : 'Paste working key'}
              value={secrets.working_key}
              onChange={(e) => setSecrets((p) => ({ ...p, working_key: e.target.value }))}
            />
          </div>
          <div>
            <label className="block text-xs font-medium text-gray-600 mb-1">IV</label>
            <input
              className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm font-mono"
              type="password"
              autoComplete="off"
              placeholder={hasSecrets.has_iv ? '•••• leave blank to keep' : 'From BillAvenue pack'}
              value={secrets.iv}
              onChange={(e) => setSecrets((p) => ({ ...p, iv: e.target.value }))}
            />
          </div>
          <div>
            <label className="block text-xs font-medium text-gray-600 mb-1">Callback secret</label>
            <input
              className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm font-mono"
              type="password"
              autoComplete="off"
              placeholder="If provided for webhooks"
              value={secrets.callback_secret}
              onChange={(e) => setSecrets((p) => ({ ...p, callback_secret: e.target.value }))}
            />
          </div>
        </div>
        <button
          type="button"
          disabled={saving}
          onClick={saveSecrets}
          className="mt-4 px-5 py-2.5 bg-gray-900 text-white text-sm font-medium rounded-lg hover:bg-gray-800 disabled:opacity-50"
        >
          {saving ? 'Saving…' : 'Save secrets'}
        </button>
      </div>

      <div className="bg-white rounded-xl border border-gray-200 p-6 shadow-sm">
        <h2 className="text-lg font-semibold text-gray-900 mb-1">Agent ID (per channel)</h2>
        <p className="text-sm text-gray-500 mb-4">
          BillAvenue provides an <strong>Agent ID</strong> per payment channel (e.g. AGT). This is separate from Institute ID and must be saved here for API
          requests.
        </p>
        {agentProfiles.length > 0 && (
          <ul className="mb-4 text-sm border border-gray-100 rounded-lg divide-y">
            {agentProfiles.map((p) => (
              <li key={p.id} className="px-3 py-2 flex flex-wrap justify-between gap-2">
                <span>
                  <span className="font-medium text-gray-800">{p.name}</span>
                  <span className="text-gray-500"> — {p.init_channel}</span>
                </span>
                <code className="text-xs bg-gray-50 px-2 py-0.5 rounded">{p.agent_id}</code>
                <span className={p.enabled ? 'text-green-600' : 'text-gray-400'}>{p.enabled ? 'enabled' : 'disabled'}</span>
              </li>
            ))}
          </ul>
        )}
        <form onSubmit={saveAgentProfile} className="grid md:grid-cols-2 gap-4">
          <div>
            <label className="block text-xs font-medium text-gray-600 mb-1">Profile name</label>
            <input
              className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm"
              value={agentForm.name}
              onChange={(e) => setAgentForm((p) => ({ ...p, name: e.target.value }))}
            />
          </div>
          <div>
            <label className="block text-xs font-medium text-gray-600 mb-1">Init channel</label>
            <select
              className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm"
              value={agentForm.init_channel}
              onChange={(e) => setAgentForm((p) => ({ ...p, init_channel: e.target.value }))}
            >
              {['AGT', 'INT', 'MOB', 'POS', 'INTB', 'MOBB', 'ATM', 'BNKBRNCH', 'BSC', 'KIOSK', 'MPOS'].map((c) => (
                <option key={c} value={c}>
                  {c}
                </option>
              ))}
            </select>
          </div>
          <div className="md:col-span-2">
            <label className="block text-xs font-medium text-gray-600 mb-1">Agent ID</label>
            <input
              className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm font-mono"
              placeholder="e.g. CC01CC01513515340681"
              value={agentForm.agent_id}
              onChange={(e) => setAgentForm((p) => ({ ...p, agent_id: e.target.value }))}
            />
          </div>
          <div className="md:col-span-2">
            <button
              type="submit"
              disabled={saving || !configId}
              className="px-5 py-2.5 bg-indigo-600 text-white text-sm font-medium rounded-lg hover:bg-indigo-700 disabled:opacity-50"
            >
              {configId ? 'Add agent profile' : 'Save config first'}
            </button>
          </div>
        </form>
      </div>

      <div className="bg-slate-50 border border-slate-200 rounded-xl p-4 text-sm text-slate-800">
        <p className="font-semibold mb-2">Load providers / biller catalogue</p>
        <p>
          BillAvenue does not list &quot;all APIs&quot; in this form — the app calls their endpoints using this config. To pull the{' '}
          <strong>biller master (MDM)</strong> into your database, open{' '}
          <Link className="text-blue-700 font-medium underline" to="/admin/bbps-governance">
            Provider Governance
          </Link>{' '}
          and click <strong>Run Biller Sync</strong> (leave biller IDs empty for a full sync, if your account allows it).
        </p>
      </div>
    </div>
  );
};

export default BillAvenueSettings;
