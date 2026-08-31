import React, { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import aepsAPI from '../services/aepsApi';

const PROD_URLS = {
  environment: 'prod',
  onboarding_base_url: 'https://fingpayap.tapits.in/fpaepsweb',
  ekyc_base_url: 'https://fpekyc.tapits.in',
  aeps_base_url: 'https://fingpayap.tapits.in',
  recon_base_url: '',
  bank_list_url: 'https://fingpayap.tapits.in/fpaepsservice/api/bankdata/bank/details',
  aadhaar_pay_bank_list_url: 'https://fingpayap.tapits.in/fpaepsservice/api/bankdata/bank/aadharpay',
};

const UAT_URLS = {
  environment: 'uat',
  onboarding_base_url: 'https://fpuat.tapits.in/fpaepsweb',
  ekyc_base_url: 'https://fpekyc.tapits.in',
  aeps_base_url: 'https://fpuat.tapits.in',
  recon_base_url: 'https://fpuat.tapits.in',
  bank_list_url: 'https://fpuat.tapits.in/fpaepsservice/api/bankdata/bank/details',
  aadhaar_pay_bank_list_url: 'https://fpuat.tapits.in/fpaepsservice/api/bankdata/bank/aadharpay',
};

const SIMPLE_URLS = {
  environment: 'simple',
  onboarding_base_url: 'https://fingpayap.tapits.in/fpaepsweb',
  ekyc_base_url: 'https://fpekyc.tapits.in',
  aeps_base_url: 'https://fingpayap.tapits.in',
  recon_base_url: 'https://fingpayap.tapits.in',
  bank_list_url: 'https://fingpayap.tapits.in/fpaepsservice/api/bankdata/bank/details',
  aadhaar_pay_bank_list_url: 'https://fingpayap.tapits.in/fpaepsservice/api/bankdata/bank/aadharpay',
};

const PRESETS = { uat: UAT_URLS, prod: PROD_URLS, simple: SIMPLE_URLS };
const emptySecrets = { password: '', secret_key: '', rsa_public_key_pem: '' };
const ENV_TABS = [
  { id: 'uat', label: 'UAT' },
  { id: 'prod', label: 'Production' },
  { id: 'simple', label: 'Simple API' },
];

export const AepsAdminProvider = () => {
  const [env, setEnv] = useState('prod');
  const [form, setForm] = useState({
    environment: 'prod',
    is_active: true,
    api_mode: 'encrypted',
    debug_mode: false,
    onboarding_api_style: 'java',
    password_mode: 'plain',
    egress_ip: '',
    capture_ftype_aeps: '2',
    capture_ftype_ekyc: '2',
    endpoints_json: {},
    full_endpoints: {},
    super_merchant_id: '',
    super_merchant_login_id: '',
    ...PROD_URLS,
    ...emptySecrets,
    gstin_number: '',
    company_or_shop_pan: '',
    notes: '',
  });
  const [meta, setMeta] = useState(null);
  const [envs, setEnvs] = useState([]);
  const [onboardingEndpoints, setOnboardingEndpoints] = useState([]);
  const [endpointFields, setEndpointFields] = useState([]);
  const [showEndpoints, setShowEndpoints] = useState(true);
  const [showAdvanced, setShowAdvanced] = useState(false);
  const [msg, setMsg] = useState('');
  const [probeJson, setProbeJson] = useState(null);
  const [saving, setSaving] = useState(false);

  const refreshMeta = (data) => {
    if (!data) return;
    setMeta(data);
    setEnvs(data.environments || []);
    setOnboardingEndpoints(data.onboarding_endpoints || []);
    setEndpointFields(data.endpoint_fields || []);
    const presets = data.presets?.[data.environment] || PRESETS[data.environment] || PROD_URLS;
    const endpoints = data.endpoints_json || {};
    const fullEndpoints = data.full_endpoints || {};
    setForm((f) => ({
      ...f,
      environment: data.environment || env,
      is_active: !!data.is_active,
      api_mode: data.api_mode || (data.environment === 'simple' ? 'simple' : 'encrypted'),
      debug_mode: !!data.debug_mode,
      password_mode: data.password_mode === 'md5' ? 'md5' : 'plain',
      onboarding_api_style: data.onboarding_api_style || 'java',
      // Blank means "auto-detect"; only a real NAT override belongs in this box.
      egress_ip: data.egress_ip_override ?? '',
      capture_ftype_aeps: data.capture_ftype_aeps || '2',
      capture_ftype_ekyc: data.capture_ftype_ekyc || '2',
      endpoints_json: endpoints,
      full_endpoints: fullEndpoints,
      super_merchant_id: data.super_merchant_id || '',
      super_merchant_login_id: data.super_merchant_login_id || '',
      onboarding_base_url: data.onboarding_base_url || presets.onboarding_base_url,
      ekyc_base_url: data.ekyc_base_url || presets.ekyc_base_url,
      aeps_base_url: data.aeps_base_url || presets.aeps_base_url,
      recon_base_url: data.recon_base_url || '',
      bank_list_url: data.bank_list_url || presets.bank_list_url || '',
      aadhaar_pay_bank_list_url: data.aadhaar_pay_bank_list_url || presets.aadhaar_pay_bank_list_url || '',
      gstin_number: data.gstin_number || '',
      company_or_shop_pan: data.company_or_shop_pan || '',
      notes: data.notes || '',
      ...emptySecrets,
    }));
  };

  const loadEnv = async (nextEnv) => {
    setEnv(nextEnv);
    setProbeJson(null);
    const res = await aepsAPI.adminProviderGet(nextEnv);
    if (res.success) refreshMeta(res.data);
    else setMsg(res.message || 'Failed to load provider config');
  };

  useEffect(() => {
    loadEnv('prod');
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const save = async (e, extra = {}) => {
    e?.preventDefault?.();
    setSaving(true);
    const body = {
      ...form,
      ...extra,
      environment: env,
      password_mode: form.password_mode === 'md5' ? 'md5' : 'plain',
      full_endpoints: form.full_endpoints || {},
      make_active: extra.make_active ?? form.is_active,
    };
    // Prefer labeled full endpoint map over raw JSON
    if (body.full_endpoints && Object.keys(body.full_endpoints).length) {
      delete body.endpoints_json;
    }
    if (!body.password) delete body.password;
    if (!body.secret_key) delete body.secret_key;
    if (!body.rsa_public_key_pem && !extra.use_bundled_certificate) delete body.rsa_public_key_pem;
    const res = await aepsAPI.adminProviderSave(body);
    setMsg(
      res.success
        ? `Saved (${env.toUpperCase()})${body.make_active ? ' · set active' : ''}${body.debug_mode ? ' · debug on' : ''}.`
        : res.message || 'Save failed'
    );
    if (res.success) await loadEnv(env);
    setSaving(false);
  };

  const applyPresetUrls = () => {
    const preset = PRESETS[env] || PROD_URLS;
    setForm((f) => ({ ...f, ...preset, environment: env }));
    setMsg(`${env.toUpperCase()} URLs applied — click Save.`);
  };

  const resetEndpoints = async () => {
    await save(null, { reset_endpoints: true, make_active: form.is_active });
  };

  const activateEnv = async () => {
    await save(null, { make_active: true, is_active: true });
  };

  const activateOnboardingApi = async (api) => {
    setSaving(true);
    setProbeJson(null);
    const body = {
      environment: api.environment,
      make_active: true,
      is_active: true,
    };
    if (api.environment === 'simple') {
      body.api_mode = 'simple';
    } else {
      body.onboarding_api_style = api.style;
      body.activate_onboarding_style = api.style;
      body.api_mode = 'encrypted';
    }
    const res = await aepsAPI.adminProviderSave(body);
    if (res.success) {
      setMsg(`Active profile: ${api.label}`);
      await loadEnv(api.environment);
    } else {
      setMsg(res.message || 'Could not activate profile');
    }
    setSaving(false);
  };

  const loadBundledCert = () => {
    if (meta?.bundled_public_certificate) {
      setForm((f) => ({ ...f, rsa_public_key_pem: meta.bundled_public_certificate }));
      setMsg('Bundled Fingpay certificate loaded — click Save.');
    } else {
      setMsg('Bundled certificate not available from API.');
    }
  };

  const saveBundledCert = async (e) => {
    e.preventDefault();
    await save(e, { use_bundled_certificate: true });
  };

  const testCreds = async () => {
    setSaving(true);
    setProbeJson(null);
    const res = await aepsAPI.adminProviderTest();
    if (res.success) {
      const d = res.data || {};
      setProbeJson(d);
      setMsg(
        d.auth_accepted
          ? `Credential probe OK (${d.mode}): ${d.message || d.statusCode}`
          : `Credential probe FAILED (${d.statusCode || 'n/a'}): ${d.message}. ${d.hint || ''}`
      );
    } else {
      setMsg(res.message || 'Credential test failed');
    }
    setSaving(false);
  };

  const copyProbeForEmail = async () => {
    if (!probeJson) return;
    const payload = probeJson.fingpay_exchange?.share_with_tapits || {
      endpoint: probeJson.endpoint,
      server_ip: probeJson.server_ip || form.egress_ip || meta?.server_egress_ip,
      login: probeJson.login,
      super_merchant_id: probeJson.super_merchant_id,
      request_plain_json: probeJson.request_plain_json,
      response_plain_json: probeJson.response_plain_json,
      fingpay_exchange: probeJson.fingpay_exchange,
    };
    try {
      await navigator.clipboard.writeText(JSON.stringify(payload, null, 2));
      setMsg('Copied plain request/response JSON for email to Tapits.');
    } catch {
      setMsg('Could not copy — select the JSON box below and copy manually.');
    }
  };

  const syncBanks = async () => {
    setSaving(true);
    const res = await aepsAPI.syncBanks();
    setMsg(res.success ? `Bank IIN sync OK — ${res.data?.synced ?? 0} rows.` : res.message || 'Bank sync failed');
    setSaving(false);
  };

  const activeLabel = envs.find((e) => e.is_active)?.environment || meta?.environment || 'prod';
  const activeOnboarding = (onboardingEndpoints.length ? onboardingEndpoints : meta?.onboarding_endpoints || []).find(
    (x) => x.is_active
  );
  const isSimple = env === 'simple';
  const tabColor = (e, selected) => {
    if (!selected) return 'bg-white dark:bg-slate-900 text-slate-700 dark:text-slate-300 ring-slate-200 dark:ring-slate-700';
    if (e === 'prod') return 'bg-emerald-600 text-white ring-emerald-600';
    if (e === 'simple') return 'bg-sky-600 text-white ring-sky-600';
    return 'bg-amber-500 text-white ring-amber-500';
  };

  return (
    <div className="mx-auto max-w-3xl space-y-4 p-4">
      <h1 className="text-2xl font-bold text-slate-900 dark:text-slate-100">AEPS provider (Fingpay)</h1>
      <p className="text-sm text-slate-500 dark:text-slate-400">
        Three profiles — <strong>UAT</strong>, <strong>Production</strong>, and <strong>Simple API</strong> — each with
        its own credentials. Activate exactly one for all users. Turn on <strong>Debug mode</strong> to store every
        request/response for Tapits sharing.
      </p>

      <div className="flex flex-wrap items-center gap-2 rounded-xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900 p-3 shadow-sm">
        <span className="text-xs font-semibold uppercase text-slate-500 dark:text-slate-400">Profile</span>
        {ENV_TABS.map((tab) => {
          const info = envs.find((x) => x.environment === tab.id);
          const selected = env === tab.id;
          return (
            <button
              key={tab.id}
              type="button"
              onClick={() => loadEnv(tab.id)}
              className={`rounded-lg px-3 py-1.5 text-sm font-semibold ring-1 ${tabColor(tab.id, selected)}`}
            >
              {tab.label}
              {info?.is_active ? ' · active' : ''}
              {info?.configured ? '' : ' · empty'}
            </button>
          );
        })}
        <span className="ml-auto text-xs text-slate-500 dark:text-slate-400">
          Live: <strong className="uppercase">{activeLabel}</strong>
          {activeOnboarding ? (
            <>
              {' '}
              · <strong>{String(activeOnboarding.style || activeOnboarding.api_mode || '').toUpperCase()}</strong>
            </>
          ) : null}
        </span>
      </div>

      <div className="rounded-xl border border-indigo-200 dark:border-indigo-800 bg-indigo-50 dark:bg-indigo-950/40 px-4 py-3 text-sm text-indigo-950 dark:text-indigo-200 shadow-sm">
        <p className="font-semibold">Activate one profile for all users</p>
        <p className="mt-1 text-xs text-indigo-900/80 dark:text-indigo-300/80">
          Encrypted UAT/Prod use Java or PHP paths. Simple API uses plain JSON + secret-key hashes (no RSA).
        </p>
        <div className="mt-3 grid gap-2 sm:grid-cols-2">
          {(onboardingEndpoints.length ? onboardingEndpoints : []).map((api) => (
            <div
              key={api.id}
              className={`rounded-lg border bg-white dark:bg-slate-900 p-3 ${
                api.is_active ? 'border-indigo-500 ring-2 ring-indigo-200 dark:ring-indigo-800' : 'border-slate-200 dark:border-slate-700'
              }`}
            >
              <div className="flex items-start justify-between gap-2">
                <div>
                  <p className="text-sm font-semibold text-slate-900 dark:text-slate-100">{api.label}</p>
                  <p className="mt-1 break-all font-mono text-[11px] text-slate-600 dark:text-slate-400">{api.endpoint}</p>
                  <p className="mt-1 text-[11px] text-slate-500 dark:text-slate-400">
                    {api.api_mode === 'simple' ? 'Plain JSON' : `AES ${String(api.aes_mode || '').toUpperCase()}`}
                    {api.configured ? '' : ' · credentials not saved yet'}
                    {api.is_active ? ' · LIVE' : ''}
                  </p>
                </div>
                <button
                  type="button"
                  disabled={saving || api.is_active}
                  onClick={() => activateOnboardingApi(api)}
                  className={`shrink-0 rounded-lg px-2.5 py-1.5 text-xs font-semibold ${
                    api.is_active
                      ? 'bg-indigo-600 text-white'
                      : 'border border-indigo-300 dark:border-indigo-800 bg-indigo-50 dark:bg-indigo-950/40 text-indigo-900 dark:text-indigo-300 hover:bg-indigo-100 dark:hover:bg-indigo-900/60 disabled:opacity-50'
                  }`}
                >
                  {api.is_active ? 'Active' : 'Activate'}
                </button>
              </div>
            </div>
          ))}
        </div>
      </div>

      <div className="rounded-xl border border-amber-200 dark:border-amber-800 bg-amber-50 dark:bg-amber-950/40 px-4 py-3 text-sm text-amber-950 dark:text-amber-200">
        <p className="font-semibold">Server egress IP (whitelist with Tapits)</p>
        <p className="mt-1 font-mono text-base font-bold">{meta?.server_egress_ip || '—'}</p>
        <p className="mt-1 text-xs text-amber-900/90 dark:text-amber-300/90">
          {form.egress_ip
            ? `Manual override in use. Auto-detected address: ${meta?.egress_ip_detected || 'unavailable'}.`
            : 'Auto-detected from this server. Re-check after any host or network move.'}
        </p>
        <p className="mt-2 text-xs text-amber-900/90 dark:text-amber-300/90">{meta?.whitelist_note}</p>
      </div>

      {isSimple ? (
        <div className="rounded-xl border border-sky-200 dark:border-sky-800 bg-sky-50 dark:bg-sky-950/40 px-4 py-3 text-sm text-sky-950 dark:text-sky-200">
          <p className="font-semibold">Simple API hash formulas</p>
          <ul className="mt-2 list-disc space-y-1 pl-5 text-xs">
            <li>
              Onboarding: <code>{meta?.hash_help?.simple_onboarding}</code>
            </li>
            <li>
              Txn / eKYC / 2FA: <code>{meta?.hash_help?.simple_txn}</code>
            </li>
            <li>RSA certificate is not required. Secret key is required for product APIs.</li>
          </ul>
        </div>
      ) : null}

      <div className="rounded-xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900 px-4 py-3 shadow-sm">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <p className="text-sm font-semibold text-slate-900 dark:text-slate-100">Bank IIN cache</p>
            <p className="text-xs text-slate-500 dark:text-slate-400">Uses the currently active environment URLs.</p>
          </div>
          <button
            type="button"
            disabled={saving}
            onClick={syncBanks}
            className="rounded-lg bg-slate-900 px-4 py-2 text-sm font-semibold text-white disabled:opacity-50"
          >
            Sync banks
          </button>
        </div>
      </div>

      {meta ? (
        <p className="text-xs text-slate-500 dark:text-slate-400">
          Secrets on file ({env}): password {meta.has_password ? 'yes' : 'no'}, secret{' '}
          {meta.has_secret_key ? 'yes' : 'no'}, public cert {meta.has_public_key ? 'yes' : 'no'} · debug{' '}
          {meta.debug_mode ? 'ON' : 'off'}
        </p>
      ) : null}

      <form onSubmit={(e) => save(e)} className="space-y-3 rounded-2xl border bg-white dark:bg-slate-900 p-6 shadow-sm">
        <div className="flex flex-wrap gap-2">
          <button
            type="button"
            onClick={applyPresetUrls}
            className="rounded-lg border border-slate-300 dark:border-slate-600 bg-slate-50 dark:bg-slate-800/50 px-3 py-2 text-sm font-medium text-slate-900 dark:text-slate-100"
          >
            Apply {env.toUpperCase()} URLs
          </button>
          <button
            type="button"
            onClick={activateEnv}
            disabled={saving}
            className="rounded-lg border border-blue-300 dark:border-blue-800 bg-blue-50 dark:bg-blue-950/40 px-3 py-2 text-sm font-medium text-blue-900 dark:text-blue-300 disabled:opacity-50"
          >
            Save & make {env.toUpperCase()} active
          </button>
        </div>

        <label className="flex items-center gap-2 rounded-lg border border-rose-200 dark:border-rose-800 bg-rose-50 dark:bg-rose-950/40 px-3 py-2 text-sm text-rose-950 dark:text-rose-200">
          <input
            type="checkbox"
            checked={!!form.debug_mode}
            onChange={(e) => setForm({ ...form, debug_mode: e.target.checked })}
          />
          <span>
            <strong>Debug mode</strong> — store every Fingpay request/response for this profile (share from Debug logs)
          </span>
        </label>

        {!isSimple ? (
          <div className="flex flex-wrap gap-2">
            {[
              { id: 'java', label: 'Java / .NET create' },
              { id: 'php', label: 'PHP create' },
            ].map((opt) => (
              <button
                key={opt.id}
                type="button"
                onClick={() => setForm((f) => ({ ...f, onboarding_api_style: opt.id, api_mode: 'encrypted' }))}
                className={`rounded-lg px-3 py-1.5 text-xs font-semibold ring-1 ${
                  form.onboarding_api_style === opt.id
                    ? 'bg-slate-900 text-white ring-slate-900'
                    : 'bg-white dark:bg-slate-900 text-slate-700 dark:text-slate-300 ring-slate-300 dark:ring-slate-600'
                }`}
              >
                {opt.label}
              </button>
            ))}
          </div>
        ) : null}

        <div className="rounded-xl border border-slate-200 dark:border-slate-700 bg-slate-50 dark:bg-slate-800/50 p-3 space-y-3">
          <p className="text-sm font-semibold text-slate-900 dark:text-slate-100">Super merchant credentials</p>
          <label className="block text-xs font-semibold uppercase text-slate-500 dark:text-slate-400">
            Super merchant ID
            <input
              className="mt-1 w-full rounded-lg border px-3 py-2 text-sm"
              value={form.super_merchant_id || ''}
              onChange={(e) => setForm({ ...form, super_merchant_id: e.target.value })}
            />
          </label>
          <label className="block text-xs font-semibold uppercase text-slate-500 dark:text-slate-400">
            Super merchant username (login ID)
            <input
              className="mt-1 w-full rounded-lg border px-3 py-2 text-sm"
              autoComplete="off"
              value={form.super_merchant_login_id || ''}
              onChange={(e) => setForm({ ...form, super_merchant_login_id: e.target.value })}
            />
          </label>
          <div>
            <p className="text-xs font-semibold uppercase text-slate-500 dark:text-slate-400">Password storage mode</p>
            <div className="mt-2 flex flex-wrap gap-2">
              {[
                { id: 'plain', label: 'Plain text → auto MD5' },
                { id: 'md5', label: 'Already MD5 hashed' },
              ].map((opt) => (
                <button
                  key={opt.id}
                  type="button"
                  onClick={() => setForm((f) => ({ ...f, password_mode: opt.id }))}
                  className={`rounded-lg px-3 py-1.5 text-xs font-semibold ring-1 ${
                    form.password_mode === opt.id
                      ? 'bg-slate-900 text-white ring-slate-900'
                      : 'bg-white dark:bg-slate-900 text-slate-700 dark:text-slate-300 ring-slate-300 dark:ring-slate-600'
                  }`}
                >
                  {opt.label}
                </button>
              ))}
            </div>
            <p className="mt-1 text-[11px] text-slate-500 dark:text-slate-400">
              {form.password_mode === 'md5'
                ? 'Paste the 32-char MD5 hex from Tapits — used as-is in API body / Simple onboard hash.'
                : 'Paste the plain API password — app MD5-hashes it before calling Fingpay (per docs).'}
            </p>
          </div>
          <label className="block text-xs font-semibold uppercase text-slate-500 dark:text-slate-400">
            Super merchant password
            <input
              className="mt-1 w-full rounded-lg border px-3 py-2 text-sm font-mono"
              type="password"
              autoComplete="new-password"
              value={form.password || ''}
              onChange={(e) => setForm({ ...form, password: e.target.value })}
              placeholder={meta?.has_password ? '•••• leave blank to keep saved value' : ''}
            />
          </label>
          <label className="block text-xs font-semibold uppercase text-slate-500 dark:text-slate-400">
            Secret key {isSimple ? '(required for txn / eKYC / 2FA hash)' : '(recon + Simple hashes)'}
            <input
              className="mt-1 w-full rounded-lg border px-3 py-2 text-sm"
              type="password"
              autoComplete="off"
              value={form.secret_key || ''}
              onChange={(e) => setForm({ ...form, secret_key: e.target.value })}
              placeholder={meta?.has_secret_key ? '•••• leave blank to keep' : ''}
            />
          </label>
          <label className="block text-xs font-semibold uppercase text-slate-500 dark:text-slate-400">
            Egress IP override (leave blank to auto-detect)
            <input
              className="mt-1 w-full rounded-lg border px-3 py-2 text-sm font-mono"
              value={form.egress_ip || ''}
              placeholder={meta?.egress_ip_detected || 'auto-detected'}
              onChange={(e) => setForm({ ...form, egress_ip: e.target.value })}
            />
            <span className="mt-1 block text-[11px] font-normal normal-case text-slate-500 dark:text-slate-400">
              Only needed behind NAT, where this server cannot see its own public address.
            </span>
          </label>
          <label className="block text-xs font-semibold uppercase text-slate-500 dark:text-slate-400">
            Capture fType — AEPS &amp; 2FA
            <select
              className="mt-1 w-full rounded-lg border px-3 py-2 text-sm"
              value={form.capture_ftype_aeps || '2'}
              onChange={(e) => setForm({ ...form, capture_ftype_aeps: e.target.value })}
            >
              <option value="0">0 — FMR</option>
              <option value="1">1 — FIR</option>
              <option value="2">2 — Full image</option>
            </select>
            <span className="mt-1 block text-[11px] font-normal normal-case text-slate-500 dark:text-slate-400">
              Finger format asked of the reader. If UIDAI replies “Missing biometric data as
              specified in Uses”, this device cannot produce the selected format — try another.
            </span>
          </label>
          <label className="block text-xs font-semibold uppercase text-slate-500 dark:text-slate-400">
            Capture fType — eKYC
            <select
              className="mt-1 w-full rounded-lg border px-3 py-2 text-sm"
              value={form.capture_ftype_ekyc || '2'}
              onChange={(e) => setForm({ ...form, capture_ftype_ekyc: e.target.value })}
            >
              <option value="0">0 — FMR</option>
              <option value="1">1 — FIR</option>
              <option value="2">2 — Full image</option>
            </select>
          </label>
        </div>

        <div className="rounded-lg border border-slate-200 dark:border-slate-700 p-3">
          <button
            type="button"
            className="text-sm font-semibold text-slate-800 dark:text-slate-200"
            onClick={() => setShowEndpoints((v) => !v)}
          >
            {showEndpoints ? 'Hide' : 'Show'} full module endpoints
          </button>
          <p className="mt-1 text-[11px] text-slate-500 dark:text-slate-400">
            Edit full URLs for each Fingpay module (or keep relative paths). Changes apply without a code deploy.
          </p>
          {showEndpoints ? (
            <div className="mt-3 max-h-96 space-y-2 overflow-y-auto pr-1">
              {(endpointFields.length
                ? endpointFields
                : Object.keys(form.full_endpoints || {}).map((k) => ({ key: k, label: k }))
              )
                .filter((f) => {
                  if (!isSimple) return true;
                  // Simple profile: hide java/php create paths from primary list
                  return !['onboarding_create_java', 'onboarding_create_php'].includes(f.key);
                })
                .map((f) => (
                  <label key={f.key} className="block text-[11px] font-semibold uppercase text-slate-500 dark:text-slate-400">
                    {f.label || f.key}
                    <input
                      className="mt-1 w-full rounded-lg border px-2 py-1.5 font-mono text-xs normal-case"
                      value={(form.full_endpoints || {})[f.key] || ''}
                      onChange={(e) =>
                        setForm((prev) => ({
                          ...prev,
                          full_endpoints: { ...(prev.full_endpoints || {}), [f.key]: e.target.value },
                        }))
                      }
                    />
                  </label>
                ))}
              <button
                type="button"
                onClick={resetEndpoints}
                disabled={saving}
                className="rounded-lg border border-slate-300 dark:border-slate-600 bg-slate-50 dark:bg-slate-800/50 px-3 py-1.5 text-xs font-semibold"
              >
                Reset paths to doc defaults
              </button>
            </div>
          ) : null}
        </div>

        <div className="rounded-lg border border-slate-200 dark:border-slate-700 p-3">
          <button
            type="button"
            className="text-sm font-semibold text-slate-800 dark:text-slate-200"
            onClick={() => setShowAdvanced((v) => !v)}
          >
            {showAdvanced ? 'Hide' : 'Show'} advanced (base URLs
            {!isSimple ? ', RSA cert, GSTIN/PAN' : ''})
          </button>
          {showAdvanced ? (
            <div className="mt-3 space-y-3">
              {['onboarding_base_url', 'ekyc_base_url', 'aeps_base_url', 'recon_base_url'].map((k) => (
                <label key={k} className="block text-xs font-semibold uppercase text-slate-500 dark:text-slate-400">
                  {k}
                  <input
                    className="mt-1 w-full rounded-lg border px-3 py-2 text-sm"
                    value={form[k] || ''}
                    onChange={(e) => setForm({ ...form, [k]: e.target.value })}
                  />
                </label>
              ))}
              {!isSimple ? (
                <>
                  {['gstin_number', 'company_or_shop_pan'].map((k) => (
                    <label key={k} className="block text-xs font-semibold uppercase text-slate-500 dark:text-slate-400">
                      {k === 'gstin_number' ? 'Super merchant GSTIN' : 'Company / shop PAN'}
                      <input
                        className="mt-1 w-full rounded-lg border px-3 py-2 text-sm"
                        value={form[k] || ''}
                        onChange={(e) => setForm({ ...form, [k]: e.target.value })}
                      />
                    </label>
                  ))}
                  <label className="block text-xs font-semibold uppercase text-slate-500 dark:text-slate-400">
                    Fingpay public certificate (PEM — BEGIN CERTIFICATE)
                    <textarea
                      className="mt-1 w-full rounded-lg border px-3 py-2 font-mono text-xs"
                      rows={6}
                      value={form.rsa_public_key_pem}
                      onChange={(e) => setForm({ ...form, rsa_public_key_pem: e.target.value })}
                      placeholder={
                        meta?.has_public_key
                          ? 'Already saved — paste a new cert only to replace'
                          : 'Paste certificate PEM or load bundled'
                      }
                    />
                  </label>
                  <div className="flex flex-wrap gap-2">
                    <button
                      type="button"
                      onClick={loadBundledCert}
                      className="rounded-lg border border-slate-300 dark:border-slate-600 bg-white dark:bg-slate-900 px-3 py-2 text-sm font-medium text-slate-700 dark:text-slate-300"
                    >
                      Load bundled certificate into form
                    </button>
                    <button
                      type="button"
                      onClick={saveBundledCert}
                      disabled={saving || !meta?.has_bundled_certificate}
                      className="rounded-lg border border-emerald-300 dark:border-emerald-800 bg-emerald-50 dark:bg-emerald-950/40 px-3 py-2 text-sm font-medium text-emerald-900 dark:text-emerald-300 disabled:opacity-50"
                    >
                      Save bundled certificate now
                    </button>
                  </div>
                </>
              ) : null}
            </div>
          ) : null}
        </div>

        <label className="flex items-center gap-2 text-sm">
          <input
            type="checkbox"
            checked={form.is_active}
            onChange={(e) => setForm({ ...form, is_active: e.target.checked })}
          />
          Make this profile active when saving
        </label>
        <button
          type="submit"
          disabled={saving}
          className="rounded-lg bg-blue-600 px-4 py-2 text-sm font-semibold text-white disabled:opacity-50"
        >
          {saving ? 'Saving…' : `Save ${env.toUpperCase()}`}
        </button>
        <button
          type="button"
          onClick={testCreds}
          disabled={saving}
          className="ml-2 rounded-lg border border-slate-300 dark:border-slate-600 bg-white dark:bg-slate-900 px-4 py-2 text-sm font-semibold text-slate-800 dark:text-slate-200 disabled:opacity-50"
        >
          Test active profile
        </button>
        {probeJson ? (
          <button
            type="button"
            onClick={copyProbeForEmail}
            className="ml-2 rounded-lg border border-indigo-300 dark:border-indigo-800 bg-indigo-50 dark:bg-indigo-950/40 px-4 py-2 text-sm font-semibold text-indigo-900 dark:text-indigo-300"
          >
            Copy JSON for Tapits email
          </button>
        ) : null}
        {msg ? <p className="text-sm">{msg}</p> : null}
        {probeJson ? (
          <pre className="max-h-80 overflow-auto rounded-lg bg-slate-900 p-3 text-xs text-slate-100">
            {JSON.stringify(
              {
                endpoint: probeJson.endpoint,
                api_mode: probeJson.api_mode,
                server_ip: probeJson.server_ip,
                login: probeJson.login,
                super_merchant_id: probeJson.super_merchant_id,
                request_plain_json: probeJson.request_plain_json,
                response_plain_json: probeJson.response_plain_json,
              },
              null,
              2
            )}
          </pre>
        ) : null}
      </form>
    </div>
  );
};

export const AepsAdminDebugLogs = () => {
  const [rows, setRows] = useState([]);
  const [endpoint, setEndpoint] = useState('');
  const [merchantTranId, setMerchantTranId] = useState('');
  const [debugOnly, setDebugOnly] = useState(true);
  const [selected, setSelected] = useState(null);
  const [msg, setMsg] = useState('');

  const load = async () => {
    const res = await aepsAPI.adminDebugLogs({
      endpoint: endpoint || undefined,
      merchant_tran_id: merchantTranId || undefined,
      debug_only: debugOnly ? '1' : undefined,
      limit: 50,
    });
    if (res.success) {
      setRows(res.data?.results || []);
      setMsg('');
    } else {
      setMsg(res.message || 'Failed to load logs');
    }
  };

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const openDetail = async (id) => {
    const res = await aepsAPI.adminDebugLogDetail(id);
    if (res.success) setSelected(res.data);
    else setMsg(res.message || 'Failed to load detail');
  };

  const copyPack = async () => {
    if (!selected?.exchange_pack && !selected?.request_body) return;
    const pack = selected.exchange_pack?.share_with_tapits || selected.exchange_pack || selected;
    try {
      await navigator.clipboard.writeText(JSON.stringify(pack, null, 2));
      setMsg('Copied exchange pack for Tapits.');
    } catch {
      setMsg('Copy failed — select JSON manually.');
    }
  };

  return (
    <div className="mx-auto max-w-4xl space-y-4 p-4">
      <h1 className="text-2xl font-bold text-slate-900 dark:text-slate-100">AEPS debug logs</h1>
      <p className="text-sm text-slate-500 dark:text-slate-400">
        When Debug mode is on for the active provider, full request/response packs are stored here for Tapits
        troubleshooting.
      </p>
      <div className="flex flex-wrap gap-2">
        <input
          className="rounded-lg border px-3 py-2 text-sm"
          placeholder="Filter endpoint"
          value={endpoint}
          onChange={(e) => setEndpoint(e.target.value)}
        />
        <input
          className="rounded-lg border px-3 py-2 text-sm"
          placeholder="merchantTranId"
          value={merchantTranId}
          onChange={(e) => setMerchantTranId(e.target.value)}
        />
        <label className="flex items-center gap-2 text-sm">
          <input type="checkbox" checked={debugOnly} onChange={(e) => setDebugOnly(e.target.checked)} />
          Debug packs only
        </label>
        <button type="button" onClick={load} className="rounded-lg bg-blue-600 px-3 py-2 text-sm font-semibold text-white">
          Refresh
        </button>
      </div>
      {msg ? <p className="text-sm text-slate-700 dark:text-slate-300">{msg}</p> : null}
      <div className="overflow-x-auto rounded-2xl border bg-white dark:bg-slate-900 shadow-sm">
        <table className="min-w-full text-sm">
          <thead className="bg-slate-50 dark:bg-slate-800/50 text-xs uppercase text-slate-500 dark:text-slate-400">
            <tr>
              <th className="px-3 py-2 text-left">When</th>
              <th className="px-3 py-2 text-left">Endpoint</th>
              <th className="px-3 py-2 text-left">Txn</th>
              <th className="px-3 py-2 text-left">HTTP</th>
              <th className="px-3 py-2 text-left">OK</th>
              <th className="px-3 py-2 text-left" />
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => (
              <tr key={r.id} className="border-t">
                <td className="px-3 py-2 text-xs">{r.created_at ? new Date(r.created_at).toLocaleString() : ''}</td>
                <td className="px-3 py-2 font-mono text-xs">{r.endpoint}</td>
                <td className="px-3 py-2 font-mono text-xs">{r.merchant_tran_id || '—'}</td>
                <td className="px-3 py-2">{r.http_status || r.provider_status_code || '—'}</td>
                <td className="px-3 py-2">{r.success ? 'yes' : 'no'}</td>
                <td className="px-3 py-2">
                  <button
                    type="button"
                    className="text-xs font-semibold text-blue-700 dark:text-blue-300"
                    onClick={() => openDetail(r.id)}
                  >
                    Open
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        {!rows.length ? <p className="p-6 text-slate-500 dark:text-slate-400">No audit rows yet.</p> : null}
      </div>
      {selected ? (
        <div className="space-y-2 rounded-2xl border bg-white dark:bg-slate-900 p-4 shadow-sm">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <p className="font-semibold">
              #{selected.id} · {selected.endpoint}
              {selected.debug_enabled ? ' · full pack' : ' · summary only'}
            </p>
            {selected.debug_enabled ? (
              <button
                type="button"
                onClick={copyPack}
                className="rounded-lg border border-indigo-300 dark:border-indigo-800 bg-indigo-50 dark:bg-indigo-950/40 px-3 py-1.5 text-xs font-semibold text-indigo-900 dark:text-indigo-300"
              >
                Copy Tapits pack
              </button>
            ) : null}
          </div>
          <pre className="max-h-96 overflow-auto rounded-lg bg-slate-900 p-3 text-xs text-slate-100">
            {JSON.stringify(
              selected.debug_enabled
                ? {
                    request_headers: selected.request_headers,
                    request_body: selected.request_body,
                    response_body: selected.response_body,
                    exchange_pack: selected.exchange_pack,
                  }
                : {
                    request_summary: selected.request_summary,
                    response_summary: selected.response_summary,
                  },
              null,
              2
            )}
          </pre>
        </div>
      ) : null}
    </div>
  );
};

export const AepsAdminRequests = () => {
  const [rows, setRows] = useState([]);
  const load = () => aepsAPI.adminAccessRequests('pending').then((r) => r.success && setRows(r.data?.results || []));
  useEffect(() => {
    load();
  }, []);
  return (
    <div className="space-y-4 p-4">
      <h1 className="text-2xl font-bold">AEPS access requests</h1>
      <div className="rounded-2xl border bg-white dark:bg-slate-900 shadow-sm">
        {rows.map((r) => (
          <div key={r.id} className="flex flex-wrap items-center justify-between gap-3 border-b px-4 py-3">
            <div>
              <p className="font-medium">
                {r.user?.name} · {r.user?.phone} · {r.user?.role}
              </p>
              <p className="text-sm text-slate-500 dark:text-slate-400">{r.reason || 'No reason'}</p>
            </div>
            <div className="flex gap-2">
              <button
                type="button"
                className="rounded-lg bg-emerald-600 px-3 py-1.5 text-sm text-white"
                onClick={async () => {
                  await aepsAPI.adminDecideRequest(r.id, 'approved');
                  load();
                }}
              >
                Approve
              </button>
              <button
                type="button"
                className="rounded-lg bg-slate-200 dark:bg-slate-700 px-3 py-1.5 text-sm"
                onClick={async () => {
                  await aepsAPI.adminDecideRequest(r.id, 'rejected');
                  load();
                }}
              >
                Reject
              </button>
            </div>
          </div>
        ))}
        {!rows.length ? <p className="p-6 text-slate-500 dark:text-slate-400">No pending requests.</p> : null}
      </div>
    </div>
  );
};

export const AepsAdminMerchants = () => {
  const [rows, setRows] = useState([]);
  const [q, setQ] = useState('');
  const [selectedId, setSelectedId] = useState(null);
  const [detail, setDetail] = useState(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [newPin, setNewPin] = useState('');
  const [resetLoading, setResetLoading] = useState(false);
  const [resetMsg, setResetMsg] = useState('');
  const [resetErr, setResetErr] = useState('');

  const load = () =>
    aepsAPI.adminMerchants({ search: q || undefined }).then((r) => r.success && setRows(r.data?.results || []));

  const loadDetail = async (id) => {
    setSelectedId(id);
    setDetailLoading(true);
    setDetail(null);
    setResetMsg('');
    setResetErr('');
    setNewPin('');
    const res = await aepsAPI.adminMerchantDetail(id);
    if (res.success) setDetail(res.data);
    setDetailLoading(false);
  };

  const handleResetPin = async () => {
    if (!selectedId || resetLoading) return;
    const pin = newPin.trim();
    if (pin && !/^\d{4,8}$/.test(pin)) {
      setResetErr('New PIN must be 4 to 8 digits, or leave blank to re-submit the current PIN.');
      return;
    }
    setResetLoading(true);
    setResetMsg('');
    setResetErr('');
    const res = await aepsAPI.adminMerchantResetPin(selectedId, pin ? { new_pin: pin } : {});
    setResetLoading(false);
    if (res.success) {
      setResetMsg(res.message || 'PIN re-sync submitted to Fingpay (Simple onboarding).');
      setNewPin('');
      if (res.data?.merchant) setDetail(res.data.merchant);
      load();
    } else {
      setResetErr(res.message || 'PIN re-sync failed.');
      loadDetail(selectedId);
    }
  };

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <div className="space-y-4 p-4">
      <h1 className="text-2xl font-bold">AEPS merchants</h1>
      <div className="flex flex-wrap gap-2">
        <input
          className="rounded-lg border px-3 py-2 text-sm"
          placeholder="Filter name / login / phone"
          value={q}
          onChange={(e) => setQ(e.target.value)}
        />
        <button type="button" onClick={load} className="rounded-lg bg-blue-600 px-3 py-2 text-sm font-semibold text-white">
          Apply
        </button>
      </div>
      <div className="overflow-x-auto rounded-2xl border bg-white dark:bg-slate-900 shadow-sm">
        <table className="min-w-full text-sm">
          <thead className="bg-slate-50 dark:bg-slate-800/50 text-xs uppercase text-slate-500 dark:text-slate-400">
            <tr>
              <th className="px-4 py-3 text-left">User</th>
              <th className="px-4 py-3 text-left">Login id</th>
              <th className="px-4 py-3 text-left">Stage</th>
              <th className="px-4 py-3 text-left">Device IMEI</th>
              <th className="px-4 py-3 text-left">Masked Aadhaar</th>
              <th className="px-4 py-3 text-left">Last error</th>
              <th className="px-4 py-3 text-left">Updated</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((m) => (
              <tr
                key={m.id}
                className={`cursor-pointer border-t hover:bg-slate-50 dark:hover:bg-slate-800 ${selectedId === m.id ? 'bg-blue-50 dark:bg-blue-950/40' : ''}`}
                onClick={() => loadDetail(m.id)}
              >
                <td className="px-4 py-3">
                  {m.user?.name} ({m.user?.role})
                </td>
                <td className="px-4 py-3 font-mono text-xs">{m.merchant_login_id}</td>
                <td className="px-4 py-3">{m.stage}</td>
                <td className="px-4 py-3 font-mono text-xs">{m.device_ready ? m.device_imei : '—'}</td>
                <td className="px-4 py-3 font-mono text-xs">{m.masked_aadhaar || '—'}</td>
                <td className="max-w-[200px] truncate px-4 py-3 text-rose-700 dark:text-rose-300" title={m.last_error || ''}>
                  {m.last_error || '—'}
                </td>
                <td className="px-4 py-3 text-xs text-slate-500 dark:text-slate-400">
                  {m.updated_at ? new Date(m.updated_at).toLocaleString() : '—'}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {selectedId ? (
        <div className="rounded-2xl border bg-white dark:bg-slate-900 p-5 shadow-sm">
          <div className="mb-4 flex flex-wrap items-center justify-between gap-2">
            <h2 className="text-lg font-semibold">Merchant detail #{selectedId}</h2>
            <button type="button" className="text-sm text-slate-500 dark:text-slate-400 hover:text-slate-800 dark:hover:text-slate-200" onClick={() => setSelectedId(null)}>
              Close
            </button>
          </div>
          {detailLoading ? (
            <p className="text-sm text-slate-500 dark:text-slate-400">Loading…</p>
          ) : detail ? (
            <div className="grid gap-6 lg:grid-cols-2">
              <section>
                <h3 className="text-xs font-semibold uppercase tracking-wide text-slate-500 dark:text-slate-400">User</h3>
                <dl className="mt-2 space-y-1 text-sm">
                  <div>
                    <dt className="inline font-medium">Name:</dt> {detail.user?.name}
                  </div>
                  <div>
                    <dt className="inline font-medium">Phone:</dt> {detail.user?.phone}
                  </div>
                  <div>
                    <dt className="inline font-medium">Email:</dt> {detail.user?.email || '—'}
                  </div>
                  <div>
                    <dt className="inline font-medium">Role:</dt> {detail.user?.role}
                  </div>
                </dl>
              </section>
              <section>
                <h3 className="text-xs font-semibold uppercase tracking-wide text-slate-500 dark:text-slate-400">Merchant</h3>
                <dl className="mt-2 space-y-1 text-sm">
                  <div>
                    <dt className="inline font-medium">Login:</dt>{' '}
                    <span className="font-mono text-xs">{detail.merchant?.merchant_login_id}</span>
                  </div>
                  <div>
                    <dt className="inline font-medium">Stage:</dt> {detail.merchant?.stage}
                  </div>
                  <div>
                    <dt className="inline font-medium">Device:</dt>{' '}
                    {detail.merchant?.device_ready ? detail.merchant?.device_imei : 'Not registered'}
                  </div>
                  <div>
                    <dt className="inline font-medium">Masked Aadhaar:</dt> {detail.merchant?.masked_aadhaar || '—'}
                  </div>
                  {detail.merchant?.last_error ? (
                    <div className="text-rose-700 dark:text-rose-300">
                      <dt className="inline font-medium">Last error:</dt> {detail.merchant.last_error}
                    </div>
                  ) : null}
                </dl>
                <div className="mt-4 rounded-xl border border-amber-200 dark:border-amber-800 bg-amber-50/70 dark:bg-amber-950/40 p-3 space-y-2">
                  <p className="text-xs font-semibold uppercase tracking-wide text-amber-800 dark:text-amber-300">
                    Reset PIN / Re-sync onboarding
                  </p>
                  <p className="text-xs text-amber-900 dark:text-amber-300">
                    Re-submits Simple onboarding create on <span className="font-mono">fingpayap</span> so
                    Fingpay merchantLoginId + PIN match our DB (fixes 10006). Leave blank to keep the
                    current PIN. Does not clear Bank eKYC. If you still see <span className="font-mono">10027</span>,
                    Tapits must enable AEPS on fpaepsservice — this button cannot clear that.
                  </p>
                  <div className="flex flex-wrap items-end gap-2">
                    <label className="text-sm">
                      <span className="mb-1 block text-xs text-slate-600 dark:text-slate-400">New PIN (optional)</span>
                      <input
                        className="w-32 rounded-lg border px-3 py-2 font-mono text-sm"
                        inputMode="numeric"
                        maxLength={8}
                        placeholder={detail.merchant?.has_merchant_pin ? 'Keep current' : '4–8 digits'}
                        value={newPin}
                        onChange={(e) => setNewPin(e.target.value.replace(/\D/g, '').slice(0, 8))}
                      />
                    </label>
                    <button
                      type="button"
                      disabled={resetLoading}
                      onClick={handleResetPin}
                      className="rounded-lg bg-amber-700 px-3 py-2 text-sm font-semibold text-white disabled:opacity-60"
                    >
                      {resetLoading ? 'Submitting…' : 'Reset PIN / Re-sync'}
                    </button>
                  </div>
                  {resetMsg ? <p className="text-sm text-emerald-800 dark:text-emerald-300">{resetMsg}</p> : null}
                  {resetErr ? <p className="text-sm text-rose-700 dark:text-rose-300">{resetErr}</p> : null}
                </div>
              </section>
              {detail.kyc ? (
                <section>
                  <h3 className="text-xs font-semibold uppercase tracking-wide text-slate-500 dark:text-slate-400">User KYC</h3>
                  <dl className="mt-2 space-y-1 text-sm">
                    <div>
                      PAN: {detail.kyc.masked_pan || '—'} ({detail.kyc.pan_verified ? 'verified' : 'not verified'})
                    </div>
                    <div>
                      Aadhaar: {detail.kyc.masked_aadhaar || '—'} (
                      {detail.kyc.aadhaar_verified ? 'verified' : 'not verified'})
                    </div>
                    <div>Status: {detail.kyc.verification_status}</div>
                  </dl>
                </section>
              ) : null}
              <section>
                <h3 className="text-xs font-semibold uppercase tracking-wide text-slate-500 dark:text-slate-400">Onboarding fields</h3>
                <pre className="mt-2 max-h-48 overflow-auto rounded-lg bg-slate-50 dark:bg-slate-800/50 p-3 text-xs">
                  {JSON.stringify(detail.onboarding?.fields || {}, null, 2)}
                </pre>
                {detail.onboarding?.saved_images ? (
                  <p className="mt-2 text-xs text-slate-500 dark:text-slate-400">
                    Images saved:{' '}
                    {Object.entries(detail.onboarding.saved_images)
                      .filter(([, v]) => v)
                      .map(([k]) => k)
                      .join(', ') || 'none'}
                  </p>
                ) : null}
              </section>
              <section className="lg:col-span-2">
                <h3 className="text-xs font-semibold uppercase tracking-wide text-slate-500 dark:text-slate-400">Recent transactions</h3>
                <ul className="mt-2 space-y-1 text-sm">
                  {(detail.recent_transactions || []).map((t) => (
                    <li key={t.id} className="rounded-lg bg-slate-50 dark:bg-slate-800/50 px-3 py-2">
                      <span className="font-mono text-xs">{t.merchant_tran_id}</span> · {t.product} · {t.status}
                      {t.response_message ? ` — ${t.response_message}` : ''}
                    </li>
                  ))}
                  {!detail.recent_transactions?.length ? <li className="text-slate-500 dark:text-slate-400">No transactions yet.</li> : null}
                </ul>
              </section>
              <section className="lg:col-span-2">
                <h3 className="text-xs font-semibold uppercase tracking-wide text-slate-500 dark:text-slate-400">Debug audit logs</h3>
                <p className="mt-1 text-sm text-slate-600 dark:text-slate-400">
                  {detail.audit_logs?.count || 0} log(s) for this user.{' '}
                  <Link to="/admin/aeps/debug-logs" className="font-semibold text-blue-700 dark:text-blue-300 underline">
                    Open debug logs
                  </Link>
                </p>
                <ul className="mt-2 space-y-1 text-sm">
                  {(detail.audit_logs?.recent || []).map((log) => (
                    <li key={log.id} className="rounded-lg bg-slate-50 dark:bg-slate-800/50 px-3 py-2">
                      #{log.id} · {log.endpoint} · {log.success ? 'ok' : 'fail'}
                      {log.error_message ? ` — ${log.error_message}` : ''}
                    </li>
                  ))}
                </ul>
              </section>
            </div>
          ) : (
            <p className="text-sm text-rose-600 dark:text-rose-400">Could not load merchant detail.</p>
          )}
        </div>
      ) : null}
    </div>
  );
};

export const AepsAdminRecon = () => {
  const [rows, setRows] = useState([]);
  const [openId, setOpenId] = useState(null);
  useEffect(() => {
    aepsAPI.adminRecon().then((r) => r.success && setRows(r.data?.results || []));
  }, []);
  return (
    <div className="space-y-4 p-4">
      <h1 className="text-2xl font-bold">AEPS recon batches</h1>
      <ul className="rounded-2xl border bg-white dark:bg-slate-900 p-4 text-sm shadow-sm">
        {rows.map((b) => (
          <li key={b.id} className="border-b py-3 last:border-0">
            <button
              type="button"
              className="flex w-full flex-wrap items-center justify-between gap-2 text-left"
              onClick={() => setOpenId(openId === b.id ? null : b.id)}
            >
              <span>
                #{b.id} · {b.txn_date || '—'} · {b.item_count} items ·{' '}
                {b.created_at ? new Date(b.created_at).toLocaleString() : ''}
              </span>
              <span className="text-xs font-semibold text-blue-700 dark:text-blue-300">{openId === b.id ? 'Hide' : 'Items'}</span>
            </button>
            {openId === b.id ? (
              <pre className="mt-2 max-h-48 overflow-auto rounded-lg bg-slate-50 dark:bg-slate-800/50 p-2 text-xs">
                {JSON.stringify(b.items || b.sample_items || b, null, 2)}
              </pre>
            ) : null}
          </li>
        ))}
        {!rows.length ? <li className="text-slate-500 dark:text-slate-400">No recon batches yet.</li> : null}
      </ul>
    </div>
  );
};
