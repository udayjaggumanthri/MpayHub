import React, { useEffect, useState } from 'react';
import Card from '../../../components/common/Card';
import Button from '../../../components/common/Button';
import Input from '../../../components/common/Input';
import cmsAPI from '../services/cmsApi';
import { formatCmsAmount, formatCmsDateTime } from '../utils/cmsUserCopy';

export const CmsAdminProvider = () => {
  const [cfg, setCfg] = useState(null);
  const [form, setForm] = useState({
    name: 'default',
    environment: 'uat',
    is_active: false,
    login_type: '2',
    super_merchant_id: '',
    cms_base_url: 'https://fpuat.tapits.in',
    login_path: '/UberCMSBC/#/login',
    hash_template: '{payload}{secret_key}',
    allowed_inbound_ips: '',
    debug_mode: false,
    hold_ttl_hours: 24,
    super_merchant_skey: '',
    secret_key: '',
    notes: '',
  });
  const [msg, setMsg] = useState('');
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    cmsAPI.adminProviderGet().then((res) => {
      if (res.success && res.data?.config) {
        const c = res.data.config;
        setCfg(c);
        setForm((f) => ({
          ...f,
          name: c.name || 'default',
          environment: c.environment || 'uat',
          is_active: Boolean(c.is_active),
          login_type: c.login_type || '2',
          super_merchant_id: c.super_merchant_id || '',
          cms_base_url: c.cms_base_url || '',
          login_path: c.login_path || '/UberCMSBC/#/login',
          hash_template: c.hash_template || '{payload}{secret_key}',
          allowed_inbound_ips: (c.allowed_inbound_ips || []).join(', '),
          debug_mode: Boolean(c.debug_mode),
          hold_ttl_hours: c.hold_ttl_hours || 24,
          notes: c.notes || '',
        }));
      }
    });
  }, []);

  const save = async (e) => {
    e.preventDefault();
    setBusy(true);
    setMsg('');
    const body = {
      ...form,
      allowed_inbound_ips: form.allowed_inbound_ips
        .split(',')
        .map((x) => x.trim())
        .filter(Boolean),
    };
    if (!body.super_merchant_skey) delete body.super_merchant_skey;
    if (!body.secret_key) delete body.secret_key;
    const res = await cmsAPI.adminProviderSave(body);
    if (res.success) {
      setCfg(res.data?.config);
      setMsg('Provider saved.');
      setForm((f) => ({ ...f, super_merchant_skey: '', secret_key: '' }));
    } else {
      setMsg(res.message || 'Save failed');
    }
    setBusy(false);
  };

  return (
    <div className="mx-auto max-w-3xl space-y-5">
      <header>
        <h1 className="text-2xl font-bold text-slate-900 dark:text-slate-100">CMS provider (Uber CMS)</h1>
        <p className="text-sm text-slate-500">
          Web URL integration credentials. Secrets never leave the server after save.
        </p>
      </header>
      <Card shadow="sm">
        <form onSubmit={save} className="space-y-4">
          <div className="grid gap-3 sm:grid-cols-2">
            <Input
              label="Environment"
              value={form.environment}
              onChange={(e) => setForm({ ...form, environment: e.target.value })}
            />
            <Input
              label="Login type"
              value={form.login_type}
              onChange={(e) => setForm({ ...form, login_type: e.target.value })}
            />
            <Input
              label="Super merchant ID"
              value={form.super_merchant_id}
              onChange={(e) => setForm({ ...form, super_merchant_id: e.target.value })}
            />
            <Input
              label="CMS base URL"
              value={form.cms_base_url}
              onChange={(e) => setForm({ ...form, cms_base_url: e.target.value })}
            />
            <Input
              label="Login path"
              value={form.login_path}
              onChange={(e) => setForm({ ...form, login_path: e.target.value })}
            />
            <Input
              label="Hash template"
              value={form.hash_template}
              onChange={(e) => setForm({ ...form, hash_template: e.target.value })}
            />
            <Input
              label="Hold TTL (hours)"
              type="number"
              value={form.hold_ttl_hours}
              onChange={(e) => setForm({ ...form, hold_ttl_hours: Number(e.target.value) })}
            />
            <Input
              label="Allowed inbound IPs (comma-separated)"
              value={form.allowed_inbound_ips}
              onChange={(e) => setForm({ ...form, allowed_inbound_ips: e.target.value })}
            />
          </div>
          <Input
            label={`superMerchantSkey ${cfg?.has_super_merchant_skey ? '(saved — leave blank to keep)' : ''}`}
            type="password"
            value={form.super_merchant_skey}
            onChange={(e) => setForm({ ...form, super_merchant_skey: e.target.value })}
            autoComplete="off"
          />
          <Input
            label={`secretKey ${cfg?.has_secret_key ? '(saved — leave blank to keep)' : ''}`}
            type="password"
            value={form.secret_key}
            onChange={(e) => setForm({ ...form, secret_key: e.target.value })}
            autoComplete="off"
          />
          <label className="flex items-center gap-2 text-sm">
            <input
              type="checkbox"
              checked={form.is_active}
              onChange={(e) => setForm({ ...form, is_active: e.target.checked })}
            />
            Active provider
          </label>
          <label className="flex items-center gap-2 text-sm">
            <input
              type="checkbox"
              checked={form.debug_mode}
              onChange={(e) => setForm({ ...form, debug_mode: e.target.checked })}
            />
            Debug mode (store full inbound bodies)
          </label>
          <Button type="submit" loading={busy}>
            Save
          </Button>
          {msg ? <p className="text-sm text-slate-600 dark:text-slate-300">{msg}</p> : null}
        </form>
      </Card>
    </div>
  );
};

export const CmsAdminAgents = () => {
  const [rows, setRows] = useState([]);
  const [userId, setUserId] = useState('');
  const [msg, setMsg] = useState('');
  const [busy, setBusy] = useState(false);

  const load = async () => {
    const res = await cmsAPI.adminAgents();
    if (res.success) setRows(res.data?.results || []);
  };

  useEffect(() => {
    load();
  }, []);

  const enable = async () => {
    setBusy(true);
    setMsg('');
    const res = await cmsAPI.adminEnable(Number(userId));
    setMsg(res.success ? 'Enabled.' : res.message);
    setBusy(false);
    load();
  };

  const disable = async (uid) => {
    setBusy(true);
    const res = await cmsAPI.adminDisable(uid);
    setMsg(res.success ? 'Disabled.' : res.message);
    setBusy(false);
    load();
  };

  const resetPin = async (agentId) => {
    setBusy(true);
    const res = await cmsAPI.adminResetPin(agentId);
    if (res.success) {
      setMsg(`New PIN for ${res.data.bc_login_id}: ${res.data.new_pin}`);
    } else {
      setMsg(res.message);
    }
    setBusy(false);
  };

  return (
    <div className="space-y-5">
      <header>
        <h1 className="text-2xl font-bold">CMS agents</h1>
        <p className="text-sm text-slate-500">
          Users with CMS enabled from their profile. Disable here or from User Management → profile.
        </p>
      </header>
      <Card shadow="sm">
        <div className="flex flex-wrap items-end gap-2">
          <Input
            label="User ID"
            value={userId}
            onChange={(e) => setUserId(e.target.value.replace(/\D/g, ''))}
            className="max-w-[160px]"
          />
          <Button loading={busy} onClick={enable} disabled={!userId}>
            Enable CMS
          </Button>
        </div>
        {msg ? <p className="mt-3 text-sm">{msg}</p> : null}
      </Card>
      <Card shadow="sm" className="overflow-x-auto">
        <table className="min-w-full text-left text-sm">
          <thead className="bg-slate-50 text-xs uppercase text-slate-500 dark:bg-slate-800/50">
            <tr>
              <th className="px-3 py-2">User</th>
              <th className="px-3 py-2">BC login</th>
              <th className="px-3 py-2">Status</th>
              <th className="px-3 py-2">Available</th>
              <th className="px-3 py-2">Actions</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => (
              <tr key={r.id} className="border-t border-slate-100 dark:border-slate-800">
                <td className="px-3 py-2">
                  {r.user_name} <span className="text-xs text-slate-400">#{r.user_id}</span>
                </td>
                <td className="px-3 py-2 font-mono text-xs">{r.bc_login_id}</td>
                <td className="px-3 py-2 capitalize">
                  {r.status}
                  {r.entitled ? '' : ' · not entitled'}
                </td>
                <td className="px-3 py-2 tabular-nums">{formatCmsAmount(r.wallet?.available)}</td>
                <td className="px-3 py-2">
                  <div className="flex flex-wrap gap-1">
                    <Button size="sm" variant="secondary" loading={busy} onClick={() => resetPin(r.id)}>
                      Reset PIN
                    </Button>
                    <Button size="sm" variant="secondary" loading={busy} onClick={() => disable(r.user_id)}>
                      Disable
                    </Button>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </Card>
    </div>
  );
};

export const CmsAdminAuditLogs = () => {
  const [rows, setRows] = useState([]);

  useEffect(() => {
    cmsAPI.adminAuditLogs().then((res) => {
      if (res.success) setRows(res.data?.results || []);
    });
  }, []);

  return (
    <div className="space-y-5">
      <header>
        <h1 className="text-2xl font-bold">CMS audit logs</h1>
        <p className="text-sm text-slate-500">Inbound wallet-check / debit / txn-result calls.</p>
      </header>
      <Card shadow="sm" className="overflow-x-auto">
        <table className="min-w-full text-left text-sm">
          <thead className="bg-slate-50 text-xs uppercase text-slate-500 dark:bg-slate-800/50">
            <tr>
              <th className="px-3 py-2">When</th>
              <th className="px-3 py-2">Endpoint</th>
              <th className="px-3 py-2">OK</th>
              <th className="px-3 py-2">FP txn</th>
              <th className="px-3 py-2">Error</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => (
              <tr key={r.id} className="border-t border-slate-100 dark:border-slate-800">
                <td className="px-3 py-2 whitespace-nowrap">{formatCmsDateTime(r.created_at)}</td>
                <td className="px-3 py-2 font-mono text-xs">{r.endpoint}</td>
                <td className="px-3 py-2">{r.success ? 'yes' : 'no'}</td>
                <td className="px-3 py-2 font-mono text-xs">{r.fp_transaction_id || '—'}</td>
                <td className="px-3 py-2 text-xs text-slate-500">{r.error_message || '—'}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </Card>
    </div>
  );
};
