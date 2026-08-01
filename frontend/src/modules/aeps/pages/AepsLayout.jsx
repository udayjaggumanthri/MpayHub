import React, { useEffect, useMemo, useState } from 'react';
import { Link, NavLink, useLocation, useNavigate } from 'react-router-dom';
import { useAuth } from '../../../context/AuthContext';
import { isModuleEnabled } from '../../../utils/maintenanceMode';
import aepsAPI from '../services/aepsApi';

const NAV = [
  { to: '/aeps', end: true, label: 'Overview' },
  { to: '/aeps/setup', label: 'Setup' },
  { to: '/aeps/withdraw', label: 'Withdraw' },
  { to: '/aeps/balance', label: 'Balance' },
  { to: '/aeps/mini-statement', label: 'Mini statement' },
  { to: '/aeps/aadhaar-pay', label: 'Aadhaar Pay' },
  { to: '/aeps/deposit', label: 'Deposit' },
  { to: '/aeps/history', label: 'History' },
  { to: '/aeps/reports', label: 'Reports' },
  { to: '/aeps/device', label: 'Device' },
];

/** Shared AEPS chrome; pass page as children. */
const AepsLayout = ({ children }) => {
  const { maintenance } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [status, setStatus] = useState(null);
  const [loading, setLoading] = useState(true);
  const moduleOn = isModuleEnabled(maintenance, 'aeps');

  const refresh = async () => {
    setLoading(true);
    const res = await aepsAPI.meStatus();
    if (res.success) setStatus(res.data);
    setLoading(false);
  };

  useEffect(() => {
    refresh();
  }, [location.pathname]);

  const nextHint = useMemo(() => {
    const n = status?.next_action;
    if (n === 'admin_ops') return 'Configure Fingpay credentials and enable AEPS for operators.';
    if (n === 'request_access') return 'Request AEPS access from Admin to begin.';
    if (n === 'await_approval') return 'Your access request is pending Admin approval.';
    if (n === 'onboarding') return 'Complete merchant onboarding next.';
    if (n === 'ekyc') return 'Complete eKYC with your Mantra device.';
    if (n === 'device') return 'Register your Mantra fingerprint device.';
    if (n === 'twofa') return "Complete today's 2FA to unlock cash products.";
    if (n === 'ready') return 'You are ready to transact.';
    return '';
  }, [status]);

  if (!moduleOn) {
    return (
      <div className="min-h-[60vh] flex items-center justify-center p-6">
        <div className="max-w-lg w-full rounded-2xl border border-slate-200 bg-white p-8 text-center shadow-sm">
          <p className="text-xs font-semibold uppercase tracking-widest text-blue-600">AEPS</p>
          <h1 className="mt-2 text-2xl font-bold text-slate-900">Service paused</h1>
          <p className="mt-3 text-slate-600">
            {maintenance?.aeps?.message ||
              'AEPS is temporarily unavailable due to maintenance. Please try again later.'}
          </p>
          <button
            type="button"
            onClick={() => navigate('/dashboard')}
            className="mt-6 rounded-lg bg-blue-600 px-5 py-2.5 text-sm font-semibold text-white hover:bg-blue-700"
          >
            Back to dashboard
          </button>
        </div>
      </div>
    );
  }

  const child = React.isValidElement(children)
    ? React.cloneElement(children, { aepsStatus: status, refreshStatus: refresh, loadingStatus: loading })
    : children;

  return (
    <div className="min-h-screen bg-gradient-to-b from-slate-50 via-white to-blue-50/40 -m-3 sm:-m-4 md:-m-6 lg:-m-8 p-3 sm:p-4 md:p-6 lg:p-8">
      <div className="mx-auto max-w-7xl">
        <div className="mb-6 flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
          <div>
            <p className="text-xs font-semibold uppercase tracking-[0.2em] text-blue-600">AEPS</p>
            <h1 className="mt-1 text-3xl font-bold tracking-tight text-slate-900">Banking services</h1>
            <p className="mt-1 text-sm text-slate-600">{loading ? 'Loading status…' : nextHint}</p>
          </div>
          <div className="flex flex-wrap gap-2">
            {status?.is_admin || status?.next_action === 'admin_ops' ? (
              <span className="rounded-full bg-slate-100 px-3 py-1 text-xs font-semibold text-slate-700 ring-1 ring-slate-200">
                Admin ops
              </span>
            ) : status?.entitled ? (
              <span className="rounded-full bg-emerald-50 px-3 py-1 text-xs font-semibold text-emerald-700 ring-1 ring-emerald-200">
                Entitled
              </span>
            ) : (
              <span className="rounded-full bg-amber-50 px-3 py-1 text-xs font-semibold text-amber-800 ring-1 ring-amber-200">
                Not entitled
              </span>
            )}
            {status?.merchant?.stage ? (
              <span className="rounded-full bg-blue-50 px-3 py-1 text-xs font-semibold text-blue-800 ring-1 ring-blue-200">
                {status.merchant.stage}
              </span>
            ) : null}
            {status?.merchant?.device_ready ? (
              <span className="rounded-full bg-indigo-50 px-3 py-1 text-xs font-semibold text-indigo-800 ring-1 ring-indigo-200">
                Device ready
              </span>
            ) : null}
          </div>
        </div>

        <div className="grid gap-6 lg:grid-cols-[220px_1fr]">
          <aside className="h-fit rounded-2xl border border-slate-200/80 bg-white/90 p-2 shadow-sm backdrop-blur">
            <nav className="flex flex-col gap-0.5">
              {NAV.map((item) => (
                <NavLink
                  key={item.to}
                  to={item.to}
                  end={item.end}
                  className={({ isActive }) =>
                    `rounded-xl px-3 py-2.5 text-sm font-medium transition ${
                      isActive
                        ? 'bg-blue-600 text-white shadow-sm shadow-blue-600/20'
                        : 'text-slate-600 hover:bg-slate-50 hover:text-slate-900'
                    }`
                  }
                >
                  {item.label}
                </NavLink>
              ))}
            </nav>
            <div className="mt-3 border-t border-slate-100 px-3 pt-3">
              <Link to="/dashboard" className="text-xs font-semibold text-slate-500 hover:text-blue-700">
                ← Main dashboard
              </Link>
            </div>
          </aside>
          <main className="min-w-0">{child}</main>
        </div>
      </div>
    </div>
  );
};

export default AepsLayout;
