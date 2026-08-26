import React, { useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import { useAuth } from '../../../context/AuthContext';
import { isAdminUser } from '../../../utils/rolePermissions';
import Card from '../../../components/common/Card';
import Button from '../../../components/common/Button';
import aepsAPI from '../services/aepsApi';

const NEXT_CTA = {
  request_access: { to: null, label: 'Request access', action: 'request' },
  await_approval: { to: null, label: 'Awaiting approval', action: null },
  onboarding: { to: '/aeps/setup', label: 'Continue onboarding' },
  device: { to: '/aeps/device', label: 'Register device' },
  ekyc: { to: '/aeps/ekyc', label: 'Complete eKYC' },
  twofa: { to: '/aeps/2fa', label: 'Complete daily 2FA' },
  ready: { to: '/aeps/withdraw', label: 'Start cash withdrawal' },
  admin_ops: { to: '/admin/aeps/provider', label: 'Open provider settings' },
};

const PRODUCTS = [
  { to: '/aeps/withdraw', title: 'Cash withdrawal', desc: 'CW — cash out' },
  { to: '/aeps/balance', title: 'Balance enquiry', desc: 'BE — check balance' },
  { to: '/aeps/mini-statement', title: 'Mini statement', desc: 'MS — recent txns' },
  { to: '/aeps/aadhaar-pay', title: 'Aadhaar Pay', desc: 'AP — collect payment' },
  { to: '/aeps/deposit', title: 'Cash deposit', desc: 'CD — bio or OTP' },
  { to: '/aeps/history', title: 'History', desc: 'AEPS-only ledger' },
];

const AepsOverview = ({ aepsStatus: status, refreshStatus }) => {
  const { user } = useAuth();
  const isAdmin = isAdminUser(user) || status?.is_admin || status?.next_action === 'admin_ops';
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState('');

  const cta = useMemo(() => NEXT_CTA[status?.next_action] || null, [status?.next_action]);

  const requestAccess = async () => {
    setBusy(true);
    setMsg('');
    const res = await aepsAPI.requestAccess('Please enable AEPS for my account');
    setMsg(res.success ? 'Request submitted to Admin.' : res.message || 'Request failed');
    if (refreshStatus) await refreshStatus();
    setBusy(false);
  };

  return (
    <div className="space-y-6">
      <Card shadow="sm" className="overflow-hidden !p-0">
        <div className="bg-slate-900 px-6 py-7 text-white">
          <h2 className="text-2xl font-bold">{isAdmin ? 'AEPS admin workspace' : 'Your AEPS workspace'}</h2>
          <p className="mt-2 max-w-xl text-sm text-slate-300">
            {isAdmin
              ? 'Configure Fingpay, sync banks, enable operators. Admins do not run trades here.'
              : 'One next step at a time — then trade CW, BE, MS, AP, and CD.'}
          </p>
          {!isAdmin && cta ? (
            <div className="mt-5">
              {cta.action === 'request' ? (
                <Button loading={busy} onClick={requestAccess} variant="primary">
                  {cta.label}
                </Button>
              ) : cta.to ? (
                <Link
                  to={cta.to}
                  className="inline-flex rounded-lg bg-blue-600 px-4 py-2.5 text-sm font-semibold text-white hover:bg-blue-700"
                >
                  {cta.label}
                </Link>
              ) : (
                <p className="text-sm font-medium text-amber-200">{cta.label}</p>
              )}
            </div>
          ) : null}
          {msg ? <p className="mt-3 text-sm text-slate-200">{msg}</p> : null}
        </div>
        <div className="grid gap-4 p-6 sm:grid-cols-3">
          <Stat label="Access" value={isAdmin ? 'Admin (ops)' : status?.entitled ? 'Enabled' : 'Not enabled'} />
          <Stat label="Merchant" value={isAdmin ? '—' : status?.merchant?.stage || '—'} />
          <Stat label="Next" value={isAdmin ? 'Provider & banks' : status?.next_action || '—'} />
        </div>
      </Card>

      {isAdmin ? (
        <section className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          <Quick to="/admin/aeps/provider" title="Provider + bank sync" desc="Credentials, Production URLs, Sync banks" />
          <Quick to="/admin/aeps/requests" title="Access requests" desc="Approve operators" />
          <Quick to="/admin/aeps/merchants" title="Merchants" desc="Stages & devices" />
          <Quick to="/admin/aeps/recon" title="Recon" desc="Three-way batches" />
          <Quick to="/admin/maintenance" title="Maintenance" desc="Module ON/OFF" />
          <Quick to="/user-management/users" title="Enable users" desc="Entitlement on profiles" />
        </section>
      ) : status?.entitled ? (
        <section className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          <Quick to="/aeps/setup" title="Setup" desc="Merchant onboarding" />
          <Quick to="/aeps/ekyc" title="eKYC" desc="OTP + fingerprint" />
          <Quick to="/aeps/device" title="Device" desc="Mantra readiness" />
          <Quick to="/aeps/2fa" title="Daily 2FA" desc="Unlock cash products" />
          {PRODUCTS.map((p) => (
            <Quick key={p.to} {...p} />
          ))}
        </section>
      ) : null}
    </div>
  );
};

const Stat = ({ label, value }) => (
  <div className="rounded-xl bg-slate-50 px-4 py-3 ring-1 ring-slate-100">
    <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">{label}</p>
    <p className="mt-1 truncate text-lg font-semibold text-slate-900">{value}</p>
  </div>
);

const Quick = ({ to, title, desc }) => (
  <Link
    to={to}
    className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm transition hover:border-blue-200 hover:shadow-md"
  >
    <p className="font-semibold text-slate-900">{title}</p>
    <p className="mt-1 text-sm text-slate-500">{desc}</p>
  </Link>
);

export default AepsOverview;
