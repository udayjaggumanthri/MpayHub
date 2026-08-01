import React, { useState } from 'react';
import { Link } from 'react-router-dom';
import { useAuth } from '../../../context/AuthContext';
import { isAdminUser } from '../../../utils/rolePermissions';
import aepsAPI from '../services/aepsApi';

const AepsOverview = ({ aepsStatus: status, refreshStatus }) => {
  const { user } = useAuth();
  const isAdmin = isAdminUser(user) || status?.is_admin || status?.next_action === 'admin_ops';
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState('');

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
      <section className="overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm">
        <div className="bg-gradient-to-r from-blue-600 to-indigo-600 px-6 py-8 text-white">
          <h2 className="text-2xl font-bold">
            {isAdmin ? 'AEPS admin workspace' : 'Your AEPS workspace'}
          </h2>
          <p className="mt-2 max-w-xl text-sm text-blue-100">
            {isAdmin
              ? 'Configure Fingpay, enable AEPS for operators, and monitor the module. Admins do not run AEPS trades on this account.'
              : 'Guided setup, Mantra fingerprint capture, and Fingpay products — kept separate from other mPayHub reports.'}
          </p>
        </div>
        <div className="grid gap-4 p-6 sm:grid-cols-3">
          <Stat
            label="Access"
            value={isAdmin ? 'Admin (ops only)' : status?.entitled ? 'Enabled' : 'Not enabled'}
          />
          <Stat label="Merchant" value={isAdmin ? '—' : status?.merchant?.stage || '—'} />
          <Stat
            label="Next step"
            value={
              isAdmin
                ? 'Configure provider & enable users'
                : status?.next_action || '—'
            }
          />
        </div>
      </section>

      {isAdmin ? (
        <section className="space-y-4">
          <div className="rounded-2xl border border-blue-200 bg-blue-50/70 p-6">
            <h3 className="text-lg font-semibold text-blue-950">Admin cannot trade AEPS</h3>
            <p className="mt-1 text-sm text-blue-900/80">
              Your Admin account manages the module only. Enable AEPS for a Retailer / Distributor /
              MD / SD from User Management, then they complete onboarding and Mantra setup.
            </p>
          </div>
          <section className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            <Quick to="/admin/aeps/provider" title="Provider credentials" desc="Fingpay password, secret key, RSA public key" />
            <Quick to="/admin/maintenance" title="Maintenance" desc="Turn AEPS module ON/OFF for the platform" />
            <Quick to="/user-management/users" title="Enable users" desc="Enable AEPS on user create or user profile" />
            <Quick to="/admin/aeps/requests" title="Access requests" desc="Approve or reject operator requests" />
            <Quick to="/admin/aeps/merchants" title="Merchants" desc="Onboarding / eKYC status" />
            <Quick to="/aeps/reports" title="AEPS reports" desc="Module-local reports only" />
          </section>
        </section>
      ) : !status?.entitled ? (
        <section className="rounded-2xl border border-amber-200 bg-amber-50/60 p-6">
          <h3 className="text-lg font-semibold text-amber-950">Need AEPS?</h3>
          <p className="mt-1 text-sm text-amber-900/80">
            Only Admin can enable AEPS for your account. You can send a request now.
          </p>
          {status?.pending_access_request ? (
            <p className="mt-4 text-sm font-medium text-amber-800">Request pending approval.</p>
          ) : (
            <button
              type="button"
              disabled={busy}
              onClick={requestAccess}
              className="mt-4 rounded-lg bg-blue-600 px-4 py-2.5 text-sm font-semibold text-white hover:bg-blue-700 disabled:opacity-50"
            >
              Request access
            </button>
          )}
          {msg ? <p className="mt-3 text-sm text-slate-700">{msg}</p> : null}
        </section>
      ) : (
        <section className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          <Quick to="/aeps/setup" title="Setup" desc="Onboarding & eKYC" />
          <Quick to="/aeps/device" title="Device" desc="Mantra RD readiness" />
          <Quick to="/aeps/withdraw" title="Cash withdrawal" desc="Customer cash out" />
          <Quick to="/aeps/balance" title="Balance enquiry" desc="Check Aadhaar balance" />
          <Quick to="/aeps/history" title="History" desc="AEPS-only transactions" />
          <Quick to="/aeps/reports" title="Reports" desc="AEPS module reports" />
        </section>
      )}
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
    className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm transition hover:border-blue-200 hover:shadow-md"
  >
    <p className="font-semibold text-slate-900">{title}</p>
    <p className="mt-1 text-sm text-slate-500">{desc}</p>
  </Link>
);

export default AepsOverview;
