import React, { useCallback, useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { billAvenueAdminAPI } from '../../services/api';

const PRESETS = {
  uat: { name: 'billavenue-uat', mode: 'uat', base_url: 'https://stgapi.billavenue.com' },
  prod: { name: 'billavenue-prod', mode: 'prod', base_url: 'https://api.billavenue.com' },
};

/** BillAvenue / CCAvenue PHP sample: pack("C*", 0x00..0x0f) as hex */
const BILLAVENUE_STANDARD_IV_HEX = '000102030405060708090a0b0c0d0e0f';

const defaultForm = {
  name: 'billavenue-uat',
  mode: 'uat',
  api_format: 'json',
  crypto_key_derivation: 'md5',
  enc_request_encoding: 'hex',
  allow_variant_fallback: true,
  allow_txn_status_path_fallback: true,
  base_url: 'https://stgapi.billavenue.com',
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
  const [env, setEnv] = useState('uat');
  const [liveMode, setLiveMode] = useState('uat');
  const [environments, setEnvironments] = useState([]);
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

  const applyConfigPayload = useCallback((data, nextEnv) => {
    const c = data?.config;
    const preset = PRESETS[nextEnv] || PRESETS.uat;
    setLiveMode(data?.live_mode || nextEnv);
    setEnvironments(data?.environments || []);
    if (c) {
      setConfigId(c.id);
      setForm((prev) => ({
        ...prev,
        ...c,
        mode: nextEnv,
        name: preset.name,
        base_url: c.base_url || preset.base_url,
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
      setForm({ ...defaultForm, ...preset });
      setHasSecrets({ has_working_key: false, has_iv: false, has_callback_secret: false });
    }
  }, []);

  const loadEnv = useCallback(async (nextEnv) => {
    const mode = nextEnv === 'prod' ? 'prod' : 'uat';
    setEnv(mode);
    const res = await billAvenueAdminAPI.getConfig(mode);
    if (res.success) {
      applyConfigPayload(res.data, mode);
    } else {
      setBanner('error', res.message || 'Failed to load BillAvenue config');
      setForm({ ...defaultForm, ...(PRESETS[mode] || PRESETS.uat) });
      setConfigId(null);
    }
  }, [applyConfigPayload]);

  const loadAgentProfiles = useCallback(async () => {
    if (!configId) {
      setAgentProfiles([]);
      return;
    }
    const res = await billAvenueAdminAPI.listAgentProfiles(configId);
    if (res.success && res.data?.profiles) setAgentProfiles(res.data.profiles);
  }, [configId]);

  useEffect(() => {
    (async () => {
      const res = await billAvenueAdminAPI.getConfig();
      const live = String(res.success ? res.data?.live_mode || '' : '').toLowerCase();
      await loadEnv(live === 'prod' ? 'prod' : 'uat');
    })();
  }, [loadEnv]);

  useEffect(() => {
    loadAgentProfiles();
  }, [loadAgentProfiles]);

  const setPartnerLive = async (mode) => {
    if (mode === liveMode) {
      await loadEnv(mode);
      return;
    }
    const envMeta = environments.find((row) => row.mode === mode);
    if (envMeta && !envMeta.credentials_ready) {
      const ivBad = envMeta.has_iv && envMeta.iv_length > 0 && envMeta.iv_length < 8;
      setBanner(
        'error',
        ivBad
          ? `Cannot switch to ${mode.toUpperCase()}: IV looks invalid (only ${envMeta.iv_length} characters saved). Paste the full IV value from BillAvenue — not the word "IV".`
          : `Cannot switch to ${mode.toUpperCase()}: Working Key and IV are not saved correctly. Paste them under Encrypted secrets, click Save secrets, then switch live again.`,
      );
      await loadEnv(mode);
      return;
    }
    if (mode === 'prod') {
      const typed = window.prompt(
        'Type PRODUCTION to confirm switching live partners to Production credentials and catalog.',
      );
      if (typed !== 'PRODUCTION') {
        setBanner('error', 'Live environment switch cancelled — confirmation text did not match.');
        return;
      }
      const ok = window.confirm('Switch partners to Production credentials and catalog?');
      if (!ok) return;
    }
    setSaving(true);
    setBanner('info', '');
    const res = await billAvenueAdminAPI.activateLiveEnvironment(mode);
    if (!res.success) {
      setBanner('error', res.message || 'Failed to switch live environment');
      setSaving(false);
      return;
    }
    setLiveMode(mode);
    setBanner('success', `${mode.toUpperCase()} is now live for partners.`);
    setSaving(false);
    await loadEnv(mode);
  };

  const saveConfig = async ({ makeActive = false } = {}) => {
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
    const preset = PRESETS[env] || PRESETS.uat;
    if (makeActive && env === 'prod') {
      const ok = window.confirm(
        'Make Production live for partners?',
      );
      if (!ok) {
        setSaving(false);
        return;
      }
    }
    const res = await billAvenueAdminAPI.saveConfig({
      ...configPayload,
      mode: env,
      name: preset.name,
      base_url: configPayload.base_url || preset.base_url,
      make_active: makeActive,
      is_active: makeActive ? true : !!configPayload.is_active && liveMode === env,
      enabled: makeActive ? true : configPayload.enabled,
    });
    if (res.success) {
      if (makeActive) {
        const act = await billAvenueAdminAPI.activateLiveEnvironment(env);
        if (!act.success) {
          setBanner('error', act.message || 'Saved, but failed to set live environment');
          setSaving(false);
          return;
        }
      }
      setBanner(
        'success',
        `Saved ${env.toUpperCase()}${makeActive ? ' and set as live for partners' : ''}.`,
      );
      await loadEnv(env);
    } else {
      setBanner('error', res.message || res.errors || 'Failed to save config');
    }
    setSaving(false);
  };

  const saveSecrets = async () => {
    setSaving(true);
    setBanner('info', '');
    const res = await billAvenueAdminAPI.updateSecrets({ ...secrets, mode: env, config_id: configId });
    if (res.success) {
      setBanner('success', `${env.toUpperCase()} secrets saved (stored encrypted).`);
      if (res.data?.config) {
        setHasSecrets({
          has_working_key: !!res.data.config.has_working_key,
          has_iv: !!res.data.config.has_iv,
          has_callback_secret: !!res.data.config.has_callback_secret,
        });
        setConfigId(res.data.config.id);
      } else {
        await loadEnv(env);
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
    if (env === 'prod' && agentForm.agent_id.trim() === 'CC01CC01513515340681') {
      const ok = window.confirm(
        'This Agent ID is the BillAvenue UAT sample ID. Production usually rejects it (VE003). Save anyway?',
      );
      if (!ok) return;
    }
    setSaving(true);
    const existing = agentProfiles.find(
      (p) => String(p.name || '').trim().toLowerCase() === String(agentForm.name || '').trim().toLowerCase(),
    );
    const res = await billAvenueAdminAPI.createAgentProfile({
      ...(existing?.id ? { id: existing.id } : {}),
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
      setBanner('success', `${env.toUpperCase()} agent profile saved.`);
      setAgentForm((p) => ({ ...p, id: res.data?.profile?.id || p.id, agent_id: '' }));
      await loadAgentProfiles();
    } else {
      const detail = res.errors && typeof res.errors === 'object' ? JSON.stringify(res.errors) : '';
      setBanner('error', `${res.message || 'Failed to save agent profile'}${detail ? `: ${detail}` : ''}`);
    }
    setSaving(false);
  };

  const removeAgentProfile = async (id) => {
    const ok = window.confirm('Remove this agent profile?');
    if (!ok) return;
    setSaving(true);
    const res = await billAvenueAdminAPI.deleteAgentProfile(id);
    if (res.success) {
      setBanner('success', 'Agent profile removed.');
      await loadAgentProfiles();
    } else {
      setBanner('error', res.message || 'Failed to remove agent profile');
    }
    setSaving(false);
  };

  const applyPresetUrl = () => {
    const preset = PRESETS[env] || PRESETS.uat;
    setForm((p) => ({ ...p, base_url: preset.base_url, name: preset.name, mode: env }));
    setBanner('info', `${env.toUpperCase()} base URL applied — click Save.`);
  };

  return (
    <div className="space-y-8 max-w-4xl mx-auto">
      {msg.text && (
        <div
          className={`text-sm border rounded px-4 py-3 ${
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

      <div className="bg-white dark:bg-slate-900 rounded-xl border border-gray-200 dark:border-slate-700 p-6 shadow-sm space-y-4">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <h1 className="text-xl font-semibold text-gray-900 dark:text-slate-100">BillAvenue Settings</h1>
            <p className="text-sm text-gray-500 dark:text-slate-400 mt-0.5">Edit UAT or Production credentials. Each environment is stored separately.</p>
          </div>
          <Link className="text-sm text-blue-700 dark:text-blue-300 underline" to="/admin/bbps-governance">
            Provider Governance
          </Link>
        </div>

        <div className="rounded-lg border border-slate-200 dark:border-slate-700 bg-slate-50 dark:bg-slate-800/50 p-3 flex flex-wrap items-center gap-3">
          <span className="text-sm font-medium text-slate-800 dark:text-slate-200">Partners use</span>
          <div className="inline-flex rounded-lg border border-slate-300 dark:border-slate-600 overflow-hidden bg-white dark:bg-slate-900">
            {['uat', 'prod'].map((mode) => (
              <button
                key={mode}
                type="button"
                disabled={saving}
                onClick={() => setPartnerLive(mode)}
                className={`px-4 py-2 text-sm font-medium disabled:opacity-50 ${
                  liveMode === mode ? 'bg-emerald-700 text-white' : 'text-slate-700 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-slate-700'
                }`}
              >
                {mode === 'uat' ? 'UAT' : 'Production'}
                {liveMode === mode ? ' · live' : ''}
              </button>
            ))}
          </div>
        </div>

        {(() => {
          const liveMeta = environments.find((row) => row.mode === liveMode);
          if (!liveMeta || liveMeta.credentials_ready) return null;
          const ivBad = liveMeta.has_iv && liveMeta.iv_length > 0 && liveMeta.iv_length < 8;
          return (
            <div className="rounded-lg border border-amber-300 dark:border-amber-800 bg-amber-50 dark:bg-amber-950/40 px-4 py-3 text-sm text-amber-900 dark:text-amber-300">
              <strong>{liveMode.toUpperCase()} is live for partners</strong> but credentials are incomplete or invalid.
              {ivBad ? (
                <>
                  The saved IV is only <strong>{liveMeta.iv_length}</strong> characters — paste the full IV from your
                  BillAvenue PI39 pack (usually 16 chars or 32 hex digits), not the label &quot;IV&quot;.
                </>
              ) : (
                <> Save Working Key and IV under Encrypted secrets below.</>
              )}
              Bill payments will fail with <code className="font-mono text-xs">DE001 Invalid ENC</code> until fixed.
            </div>
          );
        })()}

        <div className="flex flex-wrap gap-2">
          {['uat', 'prod'].map((m) => {
            const meta = environments.find((e) => e.mode === m);
            const active = env === m;
            return (
              <button
                key={m}
                type="button"
                onClick={() => loadEnv(m)}
                className={`px-4 py-2 text-sm rounded-lg border ${
                  active ? 'bg-blue-600 text-white border-blue-600' : 'bg-white dark:bg-slate-900 text-gray-700 dark:text-slate-300 border-gray-300 dark:border-slate-600 hover:bg-gray-50 dark:hover:bg-slate-800'
                }`}
              >
                Edit {m === 'uat' ? 'UAT' : 'Production'}
                {meta?.is_active ? ' · live' : ''}
              </button>
            );
          })}
          <button
            type="button"
            onClick={applyPresetUrl}
            className="ml-auto px-3 py-2 text-xs rounded-lg border border-gray-300 dark:border-slate-600 text-gray-700 dark:text-slate-300 hover:bg-gray-50 dark:hover:bg-slate-800"
          >
            Apply {env.toUpperCase()} URL preset
          </button>
        </div>

        <p className="text-sm text-gray-500 dark:text-slate-400">
          Editing <strong>{env.toUpperCase()}</strong>
          {configId ? <span> · Config ID {configId}</span> : null}
        </p>

        <div className="grid md:grid-cols-2 gap-4">
          <div>
            <label className="block text-xs font-medium text-gray-600 dark:text-slate-400 mb-1">Config name</label>
            <input
              className="w-full border border-gray-300 dark:border-slate-600 rounded-lg px-3 py-2 text-sm bg-gray-50 dark:bg-slate-800/50"
              value={(PRESETS[env] || PRESETS.uat).name}
              readOnly
            />
          </div>
          <div>
            <label className="block text-xs font-medium text-gray-600 dark:text-slate-400 mb-1">Base URL (host only, no /billpay path)</label>
            <input
              className="w-full border border-gray-300 dark:border-slate-600 rounded-lg px-3 py-2 text-sm"
              placeholder={(PRESETS[env] || PRESETS.uat).base_url}
              value={form.base_url || ''}
              onChange={(e) => setForm((p) => ({ ...p, base_url: e.target.value }))}
            />
          </div>
          <div>
            <label className="block text-xs font-medium text-gray-600 dark:text-slate-400 mb-1">Access code</label>
            <input
              className="w-full border border-gray-300 dark:border-slate-600 rounded-lg px-3 py-2 text-sm"
              value={form.access_code || ''}
              onChange={(e) => setForm((p) => ({ ...p, access_code: e.target.value }))}
            />
          </div>
          <div>
            <label className="block text-xs font-medium text-gray-600 dark:text-slate-400 mb-1">Institute ID (Agent Institution ID)</label>
            <input
              className="w-full border border-gray-300 dark:border-slate-600 rounded-lg px-3 py-2 text-sm"
              placeholder="e.g. PI39"
              value={form.institute_id || ''}
              onChange={(e) => setForm((p) => ({ ...p, institute_id: e.target.value }))}
            />
          </div>
          <div>
            <label className="block text-xs font-medium text-gray-600 dark:text-slate-400 mb-1">API version (ver)</label>
            <select
              className="w-full border border-gray-300 dark:border-slate-600 rounded-lg px-3 py-2 text-sm"
              value={form.request_version || '1.0'}
              onChange={(e) => setForm((p) => ({ ...p, request_version: e.target.value }))}
            >
              <option value="1.0">1.0 — Biller, fetch, pay, status (default)</option>
              <option value="2.0">2.0 — Complaint register / track (per BillAvenue spec)</option>
            </select>
          </div>
          <div>
            <label className="block text-xs font-medium text-gray-600 dark:text-slate-400 mb-1">Environment</label>
            <input
              className="w-full border border-gray-300 dark:border-slate-600 rounded-lg px-3 py-2 text-sm bg-gray-50 dark:bg-slate-800/50"
              value={env === 'prod' ? 'Production' : 'UAT'}
              readOnly
            />
          </div>
          <div>
            <label className="block text-xs font-medium text-gray-600 dark:text-slate-400 mb-1">Payload format</label>
            <select
              className="w-full border border-gray-300 dark:border-slate-600 rounded-lg px-3 py-2 text-sm"
              value={form.api_format || 'json'}
              onChange={(e) => setForm((p) => ({ ...p, api_format: e.target.value }))}
            >
              <option value="json">JSON</option>
              <option value="xml">XML</option>
            </select>
          </div>
          <div>
            <label className="block text-xs font-medium text-gray-600 dark:text-slate-400 mb-1">Key derivation</label>
            <select
              className="w-full border border-gray-300 dark:border-slate-600 rounded-lg px-3 py-2 text-sm"
              value={form.crypto_key_derivation || 'md5'}
              onChange={(e) => setForm((p) => ({ ...p, crypto_key_derivation: e.target.value }))}
            >
              <option value="rawhex">Raw hex (decode 32-hex working key)</option>
              <option value="md5">MD5 (PHP sample style)</option>
            </select>
          </div>
          <div>
            <label className="block text-xs font-medium text-gray-600 dark:text-slate-400 mb-1">encRequest encoding</label>
            <select
              className="w-full border border-gray-300 dark:border-slate-600 rounded-lg px-3 py-2 text-sm"
              value={form.enc_request_encoding || 'hex'}
              onChange={(e) => setForm((p) => ({ ...p, enc_request_encoding: e.target.value }))}
            >
              <option value="base64">Base64</option>
              <option value="hex">Hex</option>
            </select>
          </div>
        </div>

        <div className="mt-6 pt-4 border-t border-gray-200 dark:border-slate-700">
          <h2 className="text-lg font-semibold text-gray-900 dark:text-slate-100 mb-1">BBPS wallet service charge</h2>
          <p className="text-sm text-gray-500 dark:text-slate-400 mb-4">
            Shown on the pay screen (quote) before Proceed to Pay. Separate from BillAvenue CCF fields.
          </p>
          <div className="grid md:grid-cols-2 gap-4">
            <div>
              <label className="block text-xs font-medium text-gray-600 dark:text-slate-400 mb-1">Charge type</label>
              <select
                className="w-full border border-gray-300 dark:border-slate-600 rounded-lg px-3 py-2 text-sm"
                value={form.bbps_wallet_service_charge_mode || 'FLAT'}
                onChange={(e) => setForm((p) => ({ ...p, bbps_wallet_service_charge_mode: e.target.value }))}
              >
                <option value="FLAT">Flat (fixed INR)</option>
                <option value="PERCENT">Percent of bill amount</option>
              </select>
            </div>
            <div>
              <label className="block text-xs font-medium text-gray-600 dark:text-slate-400 mb-1">Flat amount (INR)</label>
              <input
                type="number"
                min={0}
                step="0.01"
                className="w-full border border-gray-300 dark:border-slate-600 rounded-lg px-3 py-2 text-sm"
                value={form.bbps_wallet_service_charge_flat ?? 0}
                onChange={(e) =>
                  setForm((p) => ({ ...p, bbps_wallet_service_charge_flat: parseFloat(e.target.value) || 0 }))
                }
                disabled={(form.bbps_wallet_service_charge_mode || 'FLAT') !== 'FLAT'}
              />
            </div>
            <div className="md:col-span-2">
              <label className="block text-xs font-medium text-gray-600 dark:text-slate-400 mb-1">Percent of bill (%)</label>
              <input
                type="number"
                min={0}
                max={100}
                step="0.0001"
                className="w-full border border-gray-300 dark:border-slate-600 rounded-lg px-3 py-2 text-sm"
                value={form.bbps_wallet_service_charge_percent ?? 0}
                onChange={(e) =>
                  setForm((p) => ({ ...p, bbps_wallet_service_charge_percent: parseFloat(e.target.value) || 0 }))
                }
                disabled={(form.bbps_wallet_service_charge_mode || 'FLAT') !== 'PERCENT'}
              />
            </div>
          </div>
        </div>

        <div className="grid md:grid-cols-2 gap-4 mt-4">
          <div>
            <label className="block text-xs font-medium text-gray-600 dark:text-slate-400 mb-1">Connect timeout (seconds)</label>
            <input
              type="number"
              min={5}
              className="w-full border border-gray-300 dark:border-slate-600 rounded-lg px-3 py-2 text-sm"
              value={form.connect_timeout_seconds}
              onChange={(e) => setForm((p) => ({ ...p, connect_timeout_seconds: parseInt(e.target.value, 10) || 30 }))}
            />
          </div>
          <div>
            <label className="block text-xs font-medium text-gray-600 dark:text-slate-400 mb-1">Read timeout (seconds)</label>
            <input
              type="number"
              min={5}
              className="w-full border border-gray-300 dark:border-slate-600 rounded-lg px-3 py-2 text-sm"
              value={form.read_timeout_seconds}
              onChange={(e) => setForm((p) => ({ ...p, read_timeout_seconds: parseInt(e.target.value, 10) || 60 }))}
            />
          </div>
        </div>

        <div className="mt-4">
          <label className="block text-xs font-medium text-gray-600 dark:text-slate-400 mb-1">Push / callback URL (optional)</label>
          <input
            className="w-full border border-gray-300 dark:border-slate-600 rounded-lg px-3 py-2 text-sm"
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
            <span>Enabled (integration on for this env)</span>
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
        {form.updated_at && <p className="text-xs text-gray-500 dark:text-slate-400 mt-2">Last saved: {form.updated_at}</p>}
        <div className="flex flex-wrap gap-3 mt-4">
          <button
            type="button"
            disabled={saving}
            onClick={() => saveConfig({ makeActive: false })}
            className="px-5 py-2.5 bg-blue-600 text-white text-sm font-medium rounded-lg hover:bg-blue-700 disabled:opacity-50"
          >
            {saving ? 'Saving…' : `Save ${env.toUpperCase()}`}
          </button>
          <button
            type="button"
            disabled={saving}
            onClick={() => saveConfig({ makeActive: true })}
            className="px-5 py-2.5 bg-emerald-700 text-white text-sm font-medium rounded-lg hover:bg-emerald-800 disabled:opacity-50"
          >
            {saving ? 'Saving…' : `Save & make ${env.toUpperCase()} live`}
          </button>
        </div>
      </div>

      <div className="bg-white dark:bg-slate-900 rounded-xl border border-gray-200 dark:border-slate-700 p-6 shadow-sm">
        <h2 className="text-lg font-semibold text-gray-900 dark:text-slate-100 mb-1">Encrypted secrets ({env.toUpperCase()})</h2>
        <p className="text-sm text-gray-500 dark:text-slate-400 mb-4">
          Working key and IV are required. Blank keeps existing encrypted values for this environment only.
        </p>
        <div className="flex flex-wrap gap-2 mb-4">
          <span
            className={`text-xs px-2 py-1 rounded border ${hasSecrets.has_working_key ? 'bg-green-50 dark:bg-green-950/40 border-green-200 dark:border-green-800 text-green-800 dark:text-green-300' : 'bg-gray-50 dark:bg-slate-800/50 border-gray-200 dark:border-slate-700 text-gray-600 dark:text-slate-400'}`}
          >
            Working key: {hasSecrets.has_working_key ? 'stored' : 'not set'}
          </span>
          <span
            className={`text-xs px-2 py-1 rounded border ${hasSecrets.has_iv ? 'bg-green-50 dark:bg-green-950/40 border-green-200 dark:border-green-800 text-green-800 dark:text-green-300' : 'bg-amber-50 dark:bg-amber-950/40 border-amber-200 dark:border-amber-800 text-amber-900 dark:text-amber-300'}`}
          >
            IV: {hasSecrets.has_iv ? 'stored' : 'not set (required)'}
          </span>
          {environments.find((e) => e.mode === env)?.iv_length > 0 && environments.find((e) => e.mode === env)?.iv_length < 8 && (
            <span className="text-xs px-2 py-1 rounded border bg-red-50 dark:bg-red-950/40 border-red-200 dark:border-red-800 text-red-800 dark:text-red-300">
              IV invalid ({environments.find((e) => e.mode === env)?.iv_length} chars) — re-enter full value
            </span>
          )}
          <span
            className={`text-xs px-2 py-1 rounded border ${hasSecrets.has_callback_secret ? 'bg-green-50 dark:bg-green-950/40 border-green-200 dark:border-green-800 text-green-800 dark:text-green-300' : 'bg-gray-50 dark:bg-slate-800/50 border-gray-200 dark:border-slate-700 text-gray-600 dark:text-slate-400'}`}
          >
            Callback secret: {hasSecrets.has_callback_secret ? 'stored' : 'optional'}
          </span>
        </div>
        <div className="grid md:grid-cols-3 gap-4">
          <div>
            <label className="block text-xs font-medium text-gray-600 dark:text-slate-400 mb-1">Working key</label>
            <input
              className="w-full border border-gray-300 dark:border-slate-600 rounded-lg px-3 py-2 text-sm font-mono"
              type="password"
              autoComplete="off"
              placeholder={hasSecrets.has_working_key ? '•••• leave blank to keep' : 'Paste working key'}
              value={secrets.working_key}
              onChange={(e) => setSecrets((p) => ({ ...p, working_key: e.target.value }))}
            />
          </div>
          <div>
            <label className="block text-xs font-medium text-gray-600 dark:text-slate-400 mb-1">IV</label>
            <input
              className="w-full border border-gray-300 dark:border-slate-600 rounded-lg px-3 py-2 text-sm font-mono"
              type="password"
              autoComplete="off"
              placeholder={hasSecrets.has_iv ? '•••• leave blank to keep' : '16-char or 32-hex from BillAvenue pack'}
              value={secrets.iv}
              onChange={(e) => setSecrets((p) => ({ ...p, iv: e.target.value }))}
            />
            <p className="mt-1 text-xs text-gray-500 dark:text-slate-400">
              BillAvenue PHP sample uses fixed IV{' '}
              <code className="font-mono text-[11px]">{BILLAVENUE_STANDARD_IV_HEX}</code> (not the word &quot;IV&quot;).
            </p>
            <button
              type="button"
              className="mt-2 text-xs font-medium text-blue-700 dark:text-blue-300 hover:text-blue-900 dark:hover:text-blue-200 underline"
              onClick={() => setSecrets((p) => ({ ...p, iv: BILLAVENUE_STANDARD_IV_HEX }))}
            >
              Apply standard BillAvenue IV (PHP sample)
            </button>
          </div>
          <div>
            <label className="block text-xs font-medium text-gray-600 dark:text-slate-400 mb-1">Callback secret</label>
            <input
              className="w-full border border-gray-300 dark:border-slate-600 rounded-lg px-3 py-2 text-sm font-mono"
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
          {saving ? 'Saving…' : `Save ${env.toUpperCase()} secrets`}
        </button>
      </div>

      <div className="bg-white dark:bg-slate-900 rounded-xl border border-gray-200 dark:border-slate-700 p-6 shadow-sm">
        <h2 className="text-lg font-semibold text-gray-900 dark:text-slate-100 mb-1">Agent ID ({env.toUpperCase()})</h2>
        <p className="text-sm text-gray-500 dark:text-slate-400 mb-4">
          Use the Agent ID from your BillAvenue {env === 'prod' ? 'Production' : 'UAT'} pack. UAT and Production IDs are usually different.
        </p>
        {env === 'prod' && agentProfiles.some((p) => String(p.agent_id || '').trim() === 'CC01CC01513515340681') ? (
          <div className="mb-4 text-sm border border-amber-200 dark:border-amber-800 bg-amber-50 dark:bg-amber-950/40 text-amber-950 dark:text-amber-200 rounded-lg px-3 py-2">
            This looks like the BillAvenue <strong>UAT sample</strong> Agent ID. Production rejects it with VE003
            (&quot;Agent ID invalid&quot;). Replace it with your Production Agent ID from BillAvenue.
          </div>
        ) : null}
        {agentProfiles.length > 0 && (
          <ul className="mb-4 text-sm border border-gray-100 dark:border-slate-800 rounded-lg divide-y">
            {agentProfiles.map((p) => (
              <li key={p.id} className="px-3 py-2 flex flex-wrap justify-between gap-2 items-center">
                <span>
                  <span className="font-medium text-gray-800 dark:text-slate-200">{p.name}</span>
                  <span className="text-gray-500 dark:text-slate-400"> — {p.init_channel}</span>
                </span>
                <code className="text-xs bg-gray-50 dark:bg-slate-800/50 px-2 py-0.5 rounded">{p.agent_id}</code>
                <span className={p.enabled ? 'text-green-600 dark:text-green-400' : 'text-gray-400 dark:text-slate-500'}>{p.enabled ? 'enabled' : 'disabled'}</span>
                <button
                  type="button"
                  className="text-xs text-red-700 dark:text-red-300 underline"
                  onClick={() => removeAgentProfile(p.id)}
                >
                  Remove
                </button>
              </li>
            ))}
          </ul>
        )}
        <form onSubmit={saveAgentProfile} className="grid md:grid-cols-2 gap-4">
          <div>
            <label className="block text-xs font-medium text-gray-600 dark:text-slate-400 mb-1">Profile name</label>
            <input
              className="w-full border border-gray-300 dark:border-slate-600 rounded-lg px-3 py-2 text-sm"
              value={agentForm.name}
              onChange={(e) => setAgentForm((p) => ({ ...p, name: e.target.value }))}
            />
          </div>
          <div>
            <label className="block text-xs font-medium text-gray-600 dark:text-slate-400 mb-1">Init channel</label>
            <select
              className="w-full border border-gray-300 dark:border-slate-600 rounded-lg px-3 py-2 text-sm"
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
            <label className="block text-xs font-medium text-gray-600 dark:text-slate-400 mb-1">Agent ID</label>
            <input
              className="w-full border border-gray-300 dark:border-slate-600 rounded-lg px-3 py-2 text-sm font-mono"
              placeholder={env === 'prod' ? 'Production Agent ID from BillAvenue pack' : 'UAT Agent ID from BillAvenue pack'}
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

      <div className="bg-slate-50 dark:bg-slate-800/50 border border-slate-200 dark:border-slate-700 rounded-xl p-4 text-sm text-slate-700 dark:text-slate-300">
        To sync billers for UAT or Production, open{' '}
        <Link className="text-blue-700 dark:text-blue-300 underline" to="/admin/bbps-governance">
          Provider Governance
        </Link>
        , pick that catalog, and click Sync.
      </div>
    </div>
  );
};

export default BillAvenueSettings;
