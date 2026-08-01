import React, { useEffect, useState } from 'react';
import aepsAPI from '../services/aepsApi';

export const AepsAdminProvider = () => {
  const [form, setForm] = useState({
    environment: 'uat',
    is_active: false,
    super_merchant_id: '',
    super_merchant_login_id: '',
    onboarding_base_url: 'https://fpuat.tapits.in/fpaepsweb',
    ekyc_base_url: 'https://fpuat.tapits.in',
    aeps_base_url: 'https://fpuat.tapits.in',
    recon_base_url: 'https://fpuat.tapits.in/fpcollectservice_uat',
    password: '',
    secret_key: '',
    rsa_public_key_pem: '',
    notes: '',
  });
  const [meta, setMeta] = useState(null);
  const [msg, setMsg] = useState('');

  useEffect(() => {
    aepsAPI.adminProviderGet().then((res) => {
      if (res.success && res.data?.configured) {
        setMeta(res.data);
        setForm((f) => ({
          ...f,
          environment: res.data.environment || 'uat',
          is_active: !!res.data.is_active,
          super_merchant_id: res.data.super_merchant_id || '',
          super_merchant_login_id: res.data.super_merchant_login_id || '',
          onboarding_base_url: res.data.onboarding_base_url || f.onboarding_base_url,
          ekyc_base_url: res.data.ekyc_base_url || f.ekyc_base_url,
          aeps_base_url: res.data.aeps_base_url || f.aeps_base_url,
          recon_base_url: res.data.recon_base_url || f.recon_base_url,
          notes: res.data.notes || '',
        }));
      }
    });
  }, []);

  const save = async (e) => {
    e.preventDefault();
    const res = await aepsAPI.adminProviderSave(form);
    setMsg(res.success ? 'Saved.' : res.message);
  };

  return (
    <div className="mx-auto max-w-3xl space-y-4 p-4">
      <h1 className="text-2xl font-bold text-slate-900">AEPS provider (Fingpay)</h1>
      <p className="text-sm text-slate-500">
        Credentials stay inside the AEPS module. Module is OFF by default in maintenance until you
        enable it.
      </p>
      <div className="rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-950">
        <p className="font-semibold">Where to get Secret key and RSA public key</p>
        <ul className="mt-2 list-disc space-y-1 pl-5 text-amber-900/90">
          <li>
            Ask your <strong>Fingpay / Tapits integration manager</strong> (email/WhatsApp from
            onboarding).
          </li>
          <li>
            They provide the UAT pack: super merchant id/login, password, <strong>secret key</strong>{' '}
            (hash / 3-way recon), and <strong>RSA public key</strong> (request encryption / eskey).
          </li>
          <li>
            Paste the full public key PEM when they send it (include BEGIN/END PUBLIC KEY lines if
            present).
          </li>
          <li>Production keys are shared only after UAT sign-off — do not reuse UAT secrets in prod.</li>
        </ul>
      </div>
      {meta ? (
        <p className="text-xs text-slate-500">
          Secrets on file: password {meta.has_password ? 'yes' : 'no'}, secret{' '}
          {meta.has_secret_key ? 'yes' : 'no'}, public key {meta.has_public_key ? 'yes' : 'no'}
        </p>
      ) : null}
      <form onSubmit={save} className="space-y-3 rounded-2xl border bg-white p-6 shadow-sm">
        {[
          'super_merchant_id',
          'super_merchant_login_id',
          'onboarding_base_url',
          'ekyc_base_url',
          'aeps_base_url',
          'recon_base_url',
          'password',
          'secret_key',
        ].map((k) => (
          <label key={k} className="block text-xs font-semibold uppercase text-slate-500">
            {k}
            <input
              className="mt-1 w-full rounded-lg border px-3 py-2 text-sm"
              type={k.includes('password') || k.includes('secret') ? 'password' : 'text'}
              value={form[k]}
              onChange={(e) => setForm({ ...form, [k]: e.target.value })}
            />
          </label>
        ))}
        <label className="block text-xs font-semibold uppercase text-slate-500">
          RSA public key (PEM)
          <textarea
            className="mt-1 w-full rounded-lg border px-3 py-2 font-mono text-xs"
            rows={6}
            value={form.rsa_public_key_pem}
            onChange={(e) => setForm({ ...form, rsa_public_key_pem: e.target.value })}
          />
        </label>
        <label className="flex items-center gap-2 text-sm">
          <input
            type="checkbox"
            checked={form.is_active}
            onChange={(e) => setForm({ ...form, is_active: e.target.checked })}
          />
          Active provider
        </label>
        <select
          className="rounded-lg border px-3 py-2 text-sm"
          value={form.environment}
          onChange={(e) => setForm({ ...form, environment: e.target.value })}
        >
          <option value="uat">UAT</option>
          <option value="prod">Production</option>
        </select>
        <button type="submit" className="rounded-lg bg-blue-600 px-4 py-2 text-sm font-semibold text-white">
          Save
        </button>
        {msg ? <p className="text-sm">{msg}</p> : null}
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
  useEffect(() => {
    aepsAPI.adminMerchants().then((r) => r.success && setRows(r.data?.results || []));
  }, []);
  return (
    <div className="space-y-4 p-4">
      <h1 className="text-2xl font-bold">AEPS merchants</h1>
      <div className="overflow-hidden rounded-2xl border bg-white shadow-sm">
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
  useEffect(() => {
    aepsAPI.adminRecon().then((r) => r.success && setRows(r.data?.results || []));
  }, []);
  return (
    <div className="space-y-4 p-4">
      <h1 className="text-2xl font-bold">AEPS recon batches</h1>
      <ul className="rounded-2xl border bg-white p-4 text-sm shadow-sm">
        {rows.map((b) => (
          <li key={b.id} className="border-b py-2 last:border-0">
            #{b.id} · {b.txn_date || '—'} · {b.item_count} items ·{' '}
            {b.created_at ? new Date(b.created_at).toLocaleString() : ''}
          </li>
        ))}
        {!rows.length ? <li className="text-slate-500">No recon batches yet.</li> : null}
      </ul>
    </div>
  );
};
