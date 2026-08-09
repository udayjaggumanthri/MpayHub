import React, { useEffect, useState } from 'react';
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
  recon_base_url: '',
  bank_list_url: 'https://fpuat.tapits.in/fpaepsservice/api/bankdata/bank/details',
  aadhaar_pay_bank_list_url: 'https://fpuat.tapits.in/fpaepsservice/api/bankdata/bank/aadharpay',
};

const emptySecrets = { password: '', secret_key: '', rsa_public_key_pem: '' };

export const AepsAdminProvider = () => {
  const [env, setEnv] = useState('prod');
  const [form, setForm] = useState({
    environment: 'prod',
    is_active: true,
    onboarding_api_style: 'java',
    super_merchant_id: '1501',
    super_merchant_login_id: 'Mpayhubd',
    ...PROD_URLS,
    ...emptySecrets,
    gstin_number: '',
    company_or_shop_pan: '',
    notes: '',
  });
  const [meta, setMeta] = useState(null);
  const [envs, setEnvs] = useState([]);
  const [onboardingEndpoints, setOnboardingEndpoints] = useState([]);
  const [msg, setMsg] = useState('');
  const [probeJson, setProbeJson] = useState(null);
  const [saving, setSaving] = useState(false);

  const refreshMeta = (data) => {
    if (!data) return;
    setMeta(data);
    setEnvs(data.environments || []);
    setOnboardingEndpoints(data.onboarding_endpoints || []);
    const presets = data.presets?.[data.environment] || (data.environment === 'uat' ? UAT_URLS : PROD_URLS);
    setForm((f) => ({
      ...f,
      environment: data.environment || env,
      is_active: !!data.is_active,
      onboarding_api_style: data.onboarding_api_style || 'java',
      super_merchant_id: data.super_merchant_id || (data.environment === 'uat' ? '' : '1501'),
      super_merchant_login_id: data.super_merchant_login_id || (data.environment === 'uat' ? '' : 'Mpayhubd'),
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
      make_active: extra.make_active ?? form.is_active,
    };
    if (!body.password) delete body.password;
    if (!body.secret_key) delete body.secret_key;
    if (!body.rsa_public_key_pem && !extra.use_bundled_certificate) delete body.rsa_public_key_pem;
    const res = await aepsAPI.adminProviderSave(body);
    setMsg(res.success ? `Saved (${env.toUpperCase()})${body.make_active ? ' · set active' : ''}.` : res.message || 'Save failed');
    if (res.success) await loadEnv(env);
    setSaving(false);
  };

  const applyPresetUrls = () => {
    const preset = env === 'uat' ? UAT_URLS : PROD_URLS;
    setForm((f) => ({
      ...f,
      ...preset,
      environment: env,
      ...(env === 'prod'
        ? { super_merchant_id: f.super_merchant_id || '1501', super_merchant_login_id: f.super_merchant_login_id || 'Mpayhubd' }
        : {}),
    }));
    setMsg(`${env.toUpperCase()} URLs applied — click Save.`);
  };

  const activateEnv = async () => {
    await save(null, { make_active: true, is_active: true });
  };

  const activateOnboardingApi = async (api) => {
    setSaving(true);
    setProbeJson(null);
    const body = {
      environment: api.environment,
      onboarding_api_style: api.style,
      activate_onboarding_style: api.style,
      make_active: true,
      is_active: true,
    };
    const res = await aepsAPI.adminProviderSave(body);
    if (res.success) {
      setMsg(`Active onboarding API: ${api.label}`);
      await loadEnv(api.environment);
    } else {
      setMsg(res.message || 'Could not activate onboarding API');
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
      server_ip: probeJson.server_ip || meta?.server_egress_ip || '57.131.39.21',
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
  const uatUsingProdLogin =
    env === 'uat' &&
    String(form.super_merchant_login_id || '').toLowerCase() === 'mpayhubd' &&
    String(form.super_merchant_id || '') === '1501';

  return (
    <div className="mx-auto max-w-3xl space-y-4 p-4">
      <h1 className="text-2xl font-bold text-slate-900">AEPS provider (Fingpay)</h1>
      <p className="text-sm text-slate-500">
        Store <strong>UAT</strong> and <strong>Production</strong> credentials separately. Choose one of the four
        onboarding APIs (UAT/Prod × Java/PHP) — only one can be live-active for Submit. Leave password blank to keep
        the encrypted value.
      </p>

      {uatUsingProdLogin ? (
        <div className="rounded-xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-900">
          <p className="font-semibold">UAT cannot use Production login</p>
          <p className="mt-1">
            <code>Mpayhubd</code> / ID <code>1501</code> is Production-only. Fingpay returns{' '}
            <strong>10005 Invalid super merchant</strong> on <code>fpuat</code>. Ask Tapits for separate UAT
            SuperMerchant login/ID/password, save them here, then test. Or switch to <strong>PROD</strong> and make it
            active for go-live (after Production IP whitelist).
          </p>
        </div>
      ) : null}

      <div className="flex flex-wrap items-center gap-2 rounded-xl border border-slate-200 bg-white p-3 shadow-sm">
        <span className="text-xs font-semibold uppercase text-slate-500">Environment</span>
        {['uat', 'prod'].map((e) => {
          const info = envs.find((x) => x.environment === e);
          const selected = env === e;
          return (
            <button
              key={e}
              type="button"
              onClick={() => loadEnv(e)}
              className={`rounded-lg px-3 py-1.5 text-sm font-semibold ring-1 ${
                selected
                  ? e === 'prod'
                    ? 'bg-emerald-600 text-white ring-emerald-600'
                    : 'bg-amber-500 text-white ring-amber-500'
                  : 'bg-white text-slate-700 ring-slate-200'
              }`}
            >
              {e.toUpperCase()}
              {info?.is_active ? ' · active' : ''}
              {info?.configured ? '' : ' · empty'}
            </button>
          );
        })}
        <span className="ml-auto text-xs text-slate-500">
          Live calls use: <strong className="uppercase">{activeLabel}</strong>
          {activeOnboarding ? (
            <>
              {' '}
              · <strong>{String(activeOnboarding.style || '').toUpperCase()}</strong>
            </>
          ) : null}
        </span>
      </div>

      <div className="rounded-xl border border-indigo-200 bg-indigo-50 px-4 py-3 text-sm text-indigo-950 shadow-sm">
        <p className="font-semibold">Onboarding create API (pick one)</p>
        <p className="mt-1 text-xs text-indigo-900/80">
          Doc lists Java/.NET <code>…/merchant/creation/v2</code> and PHP <code>…/merchant/php/creation/v2</code> for
          both UAT and Production. Activating one deactivates the other three.
        </p>
        <div className="mt-3 grid gap-2 sm:grid-cols-2">
          {(onboardingEndpoints.length ? onboardingEndpoints : []).map((api) => (
            <div
              key={api.id}
              className={`rounded-lg border bg-white p-3 ${
                api.is_active ? 'border-indigo-500 ring-2 ring-indigo-200' : 'border-slate-200'
              }`}
            >
              <div className="flex items-start justify-between gap-2">
                <div>
                  <p className="text-sm font-semibold text-slate-900">{api.label}</p>
                  <p className="mt-1 break-all font-mono text-[11px] text-slate-600">{api.endpoint}</p>
                  <p className="mt-1 text-[11px] text-slate-500">
                    AES {String(api.aes_mode || '').toUpperCase()}
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
                      : 'border border-indigo-300 bg-indigo-50 text-indigo-900 hover:bg-indigo-100 disabled:opacity-50'
                  }`}
                >
                  {api.is_active ? 'Active' : 'Activate'}
                </button>
              </div>
            </div>
          ))}
        </div>
        {activeOnboarding ? (
          <p className="mt-3 text-xs">
            Submit currently posts to <code className="break-all">{activeOnboarding.endpoint}</code>
          </p>
        ) : null}
      </div>

      <div className="rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-950">
        <p className="font-semibold">Server IP to share with Tapits (whitelist)</p>
        <p className="mt-1 font-mono text-base font-bold">{meta?.server_egress_ip || '57.131.39.21'}</p>
        <p className="mt-2 text-xs text-amber-900/90">
          {meta?.whitelist_note ||
            'Do not send old AWS IPs (52.66.x / 13.234.x / 3.108.x) from other portals — those are not this VPS.'}
        </p>
      </div>

      <div
        className={`rounded-xl border px-4 py-3 text-sm ${
          env === 'prod' ? 'border-emerald-200 bg-emerald-50 text-emerald-950' : 'border-amber-200 bg-amber-50 text-amber-950'
        }`}
      >
        <p className="font-semibold">Editing {env.toUpperCase()} endpoints</p>
        <ul className="mt-2 list-disc space-y-1 pl-5">
          <li>
            Onboarding base: <code>{form.onboarding_base_url}</code>
          </li>
          <li>
            Create API style:{' '}
            <strong>{String(form.onboarding_api_style || 'java').toUpperCase()}</strong> →{' '}
            <code className="break-all">
              {meta?.onboarding_create_url ||
                `${form.onboarding_base_url}/api/onboarding/merchant/${
                  form.onboarding_api_style === 'php' ? 'php/' : ''
                }creation/v2`}
            </code>
          </li>
          <li>
            eKYC: <code>{form.ekyc_base_url}</code>
          </li>
          <li>
            AEPS: <code>{form.aeps_base_url}</code>
          </li>
        </ul>
        <div className="mt-3 flex flex-wrap gap-2">
          {[
            { id: 'java', label: 'Java / .NET create' },
            { id: 'php', label: 'PHP create' },
          ].map((opt) => (
            <button
              key={opt.id}
              type="button"
              onClick={() => setForm((f) => ({ ...f, onboarding_api_style: opt.id }))}
              className={`rounded-lg px-3 py-1.5 text-xs font-semibold ring-1 ${
                form.onboarding_api_style === opt.id
                  ? 'bg-slate-900 text-white ring-slate-900'
                  : 'bg-white text-slate-700 ring-slate-300'
              }`}
            >
              {opt.label}
            </button>
          ))}
          <span className="self-center text-[11px] opacity-80">Saved with the form below (or use Activate cards above).</span>
        </div>
      </div>

      <div className="rounded-xl border border-slate-200 bg-white px-4 py-3 shadow-sm">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <p className="text-sm font-semibold text-slate-900">Bank IIN cache</p>
            <p className="text-xs text-slate-500">Uses the currently active environment URLs.</p>
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
        <p className="text-xs text-slate-500">
          Secrets on file ({env}): password {meta.has_password ? 'yes' : 'no'}, secret{' '}
          {meta.has_secret_key ? 'yes' : 'no'}, public cert {meta.has_public_key ? 'yes' : 'no'}
        </p>
      ) : null}
      <form onSubmit={(e) => save(e)} className="space-y-3 rounded-2xl border bg-white p-6 shadow-sm">
        <div className="flex flex-wrap gap-2">
          <button
            type="button"
            onClick={applyPresetUrls}
            className="rounded-lg border border-slate-300 bg-slate-50 px-3 py-2 text-sm font-medium text-slate-900"
          >
            Apply {env.toUpperCase()} URLs
          </button>
          <button
            type="button"
            onClick={activateEnv}
            disabled={saving}
            className="rounded-lg border border-blue-300 bg-blue-50 px-3 py-2 text-sm font-medium text-blue-900 disabled:opacity-50"
          >
            Save & make {env.toUpperCase()} active
          </button>
        </div>
        {[
          'super_merchant_id',
          'super_merchant_login_id',
          'onboarding_base_url',
          'ekyc_base_url',
          'aeps_base_url',
          'recon_base_url',
          'password',
          'secret_key',
          'gstin_number',
          'company_or_shop_pan',
        ].map((k) => (
          <label key={k} className="block text-xs font-semibold uppercase text-slate-500">
            {k === 'gstin_number'
              ? 'Super merchant GSTIN (onboarding KYC — mandatory)'
              : k === 'company_or_shop_pan'
                ? 'Company / shop PAN (onboarding KYC — mandatory)'
                : k === 'secret_key'
                  ? 'secret_key (recon — from Fingpay email)'
                  : k === 'password'
                    ? 'API password (leave blank to keep encrypted value)'
                    : k}
            <input
              className="mt-1 w-full rounded-lg border px-3 py-2 text-sm"
              type={k.includes('password') || k.includes('secret') ? 'password' : 'text'}
              autoComplete="off"
              value={form[k]}
              onChange={(e) => setForm({ ...form, [k]: e.target.value })}
              placeholder={
                k === 'password' && meta?.has_password
                  ? '•••• leave blank to keep'
                  : k === 'secret_key' && meta?.has_secret_key
                    ? '•••• leave blank to keep'
                    : ''
              }
            />
          </label>
        ))}
        <label className="block text-xs font-semibold uppercase text-slate-500">
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
            className="rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm font-medium text-slate-700"
          >
            Load bundled certificate into form
          </button>
          <button
            type="button"
            onClick={saveBundledCert}
            disabled={saving || !meta?.has_bundled_certificate}
            className="rounded-lg border border-emerald-300 bg-emerald-50 px-3 py-2 text-sm font-medium text-emerald-900 disabled:opacity-50"
          >
            Save bundled certificate now
          </button>
        </div>
        <label className="flex items-center gap-2 text-sm">
          <input
            type="checkbox"
            checked={form.is_active}
            onChange={(e) => setForm({ ...form, is_active: e.target.checked })}
          />
          Make this environment active when saving
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
          className="ml-2 rounded-lg border border-slate-300 bg-white px-4 py-2 text-sm font-semibold text-slate-800 disabled:opacity-50"
        >
          Test active environment
        </button>
        {probeJson ? (
          <button
            type="button"
            onClick={copyProbeForEmail}
            className="ml-2 rounded-lg border border-indigo-300 bg-indigo-50 px-4 py-2 text-sm font-semibold text-indigo-900"
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

export const AepsAdminRequests = () => {
  const [rows, setRows] = useState([]);
  const load = () => aepsAPI.adminAccessRequests('pending').then((r) => r.success && setRows(r.data?.results || []));
  useEffect(() => {
    load();
  }, []);
  return (
    <div className="space-y-4 p-4">
      <h1 className="text-2xl font-bold">AEPS access requests</h1>
      <div className="rounded-2xl border bg-white shadow-sm">
        {rows.map((r) => (
          <div key={r.id} className="flex flex-wrap items-center justify-between gap-3 border-b px-4 py-3">
            <div>
              <p className="font-medium">
                {r.user?.name} · {r.user?.phone} · {r.user?.role}
              </p>
              <p className="text-sm text-slate-500">{r.reason || 'No reason'}</p>
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
                className="rounded-lg bg-slate-200 px-3 py-1.5 text-sm"
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
        {!rows.length ? <p className="p-6 text-slate-500">No pending requests.</p> : null}
      </div>
    </div>
  );
};

export const AepsAdminMerchants = () => {
  const [rows, setRows] = useState([]);
  const [q, setQ] = useState('');
  const load = () =>
    aepsAPI.adminMerchants({ search: q || undefined }).then((r) => r.success && setRows(r.data?.results || []));
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
      <div className="overflow-x-auto rounded-2xl border bg-white shadow-sm">
        <table className="min-w-full text-sm">
          <thead className="bg-slate-50 text-xs uppercase text-slate-500">
            <tr>
              <th className="px-4 py-3 text-left">User</th>
              <th className="px-4 py-3 text-left">Login id</th>
              <th className="px-4 py-3 text-left">Stage</th>
              <th className="px-4 py-3 text-left">Device</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((m) => (
              <tr key={m.id} className="border-t">
                <td className="px-4 py-3">
                  {m.user?.name} ({m.user?.role})
                </td>
                <td className="px-4 py-3 font-mono text-xs">{m.merchant_login_id}</td>
                <td className="px-4 py-3">{m.stage}</td>
                <td className="px-4 py-3">{m.device_ready ? m.device_imei : '—'}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
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
      <ul className="rounded-2xl border bg-white p-4 text-sm shadow-sm">
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
              <span className="text-xs font-semibold text-blue-700">{openId === b.id ? 'Hide' : 'Items'}</span>
            </button>
            {openId === b.id ? (
              <pre className="mt-2 max-h-48 overflow-auto rounded-lg bg-slate-50 p-2 text-xs">
                {JSON.stringify(b.items || b.sample_items || b, null, 2)}
              </pre>
            ) : null}
          </li>
        ))}
        {!rows.length ? <li className="text-slate-500">No recon batches yet.</li> : null}
      </ul>
    </div>
  );
};
