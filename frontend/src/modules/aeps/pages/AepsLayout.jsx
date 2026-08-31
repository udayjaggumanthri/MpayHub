import React, { useEffect, useMemo, useState } from 'react';
import { Link, NavLink, useLocation, useNavigate } from 'react-router-dom';
import { useAuth } from '../../../context/AuthContext';
import { isModuleEnabled } from '../../../utils/maintenanceMode';
import Card from '../../../components/common/Card';
import Button from '../../../components/common/Button';
import aepsAPI from '../services/aepsApi';
import { setCaptureProfile } from '../services/mantraRd';

const JOURNEY = [
  { key: 'onboarding', label: 'Onboard', to: '/aeps/setup' },
  { key: 'device', label: 'Device', to: '/aeps/device' },
  { key: 'ekyc', label: 'eKYC', to: '/aeps/ekyc' },
  { key: 'twofa', label: '2FA', to: '/aeps/2fa' },
  { key: 'ready', label: 'Trade', to: '/aeps/withdraw' },
];

const NAV = [
  { to: '/aeps', end: true, label: 'Overview', group: 'home' },
  { to: '/aeps/setup', label: 'Setup', group: 'setup' },
  { to: '/aeps/device', label: 'Device', group: 'setup' },
  { to: '/aeps/ekyc', label: 'eKYC', group: 'setup' },
  { to: '/aeps/2fa', label: 'Daily 2FA', group: 'setup' },
  { to: '/aeps/withdraw', label: 'Withdraw', group: 'trade' },
  { to: '/aeps/balance', label: 'Balance', group: 'trade' },
  { to: '/aeps/mini-statement', label: 'Mini stmt', group: 'trade' },
  { to: '/aeps/aadhaar-pay', label: 'Aadhaar Pay', group: 'trade' },
  { to: '/aeps/deposit', label: 'Deposit', group: 'trade' },
  { to: '/aeps/history', label: 'History', group: 'ops' },
  { to: '/aeps/reports', label: 'Reports', group: 'ops' },
];

const journeyIndex = (nextAction) => {
  const map = {
    request_access: -1,
    await_approval: -1,
    onboarding: 0,
    device: 1,
    ekyc: 2,
    twofa: 3,
    ready: 4,
    admin_ops: 4,
  };
  return map[nextAction] ?? -1;
};

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
    if (res.success) {
      setStatus(res.data);
      setCaptureProfile(res.data?.capture_profile);
    }
    setLoading(false);
  };

  useEffect(() => {
    refresh();
  }, [location.pathname]);

  const nextHint = useMemo(() => {
    const n = status?.next_action;
    if (n === 'admin_ops') return 'Configure Fingpay and enable AEPS for operators.';
    if (n === 'request_access') return 'Request AEPS access from Admin to begin.';
    if (n === 'await_approval') return 'Your access request is pending Admin approval.';
    if (n === 'onboarding') return 'Complete merchant onboarding next.';
    if (n === 'device') return 'Register your Mantra fingerprint device.';
    if (n === 'ekyc') return 'Complete eKYC (OTP + biometric).';
    if (n === 'twofa') return "Complete today's 2FA to unlock cash products.";
    if (n === 'ready') return 'You are ready to transact.';
    return '';
  }, [status]);

  const activeJourney = journeyIndex(status?.next_action);

  if (!moduleOn) {
    return (
      <div className="flex min-h-[60vh] items-center justify-center p-6">
        <Card className="max-w-lg w-full text-center" shadow="md">
          <p className="text-xs font-semibold uppercase tracking-widest text-blue-600 dark:text-blue-400">AEPS</p>
          <h1 className="mt-2 text-2xl font-bold text-slate-900 dark:text-slate-100">Service paused</h1>
          <p className="mt-3 text-slate-600 dark:text-slate-400">
            {maintenance?.aeps?.message ||
              'AEPS is temporarily unavailable due to maintenance. Please try again later.'}
          </p>
          <Button className="mt-6" onClick={() => navigate('/dashboard')}>
            Back to dashboard
          </Button>
        </Card>
      </div>
    );
  }

  const child = React.isValidElement(children)
    ? React.cloneElement(children, { aepsStatus: status, refreshStatus: refresh, loadingStatus: loading })
    : children;

  return (
    <div className="-m-3 min-h-screen bg-slate-50 dark:bg-slate-800/50 p-3 sm:-m-4 sm:p-4 md:-m-6 md:p-6 lg:-m-8 lg:p-8">
      <div className="mx-auto max-w-7xl space-y-5">
        <header className="flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
          <div>
            <p className="text-xs font-semibold uppercase tracking-[0.18em] text-blue-700 dark:text-blue-300">AEPS</p>
            <h1 className="mt-1 text-2xl font-bold tracking-tight text-slate-900 dark:text-slate-100 sm:text-3xl">
              Banking services
            </h1>
            <p className="mt-1 text-sm text-slate-600 dark:text-slate-400">{loading ? 'Loading status…' : nextHint}</p>
          </div>
          <div className="flex flex-wrap gap-2">
            {loading ? (
              <span className="rounded-full bg-slate-100 dark:bg-slate-800 px-3 py-1 text-xs font-semibold text-slate-600 dark:text-slate-400 ring-1 ring-slate-200 dark:ring-slate-700">
                Checking access…
              </span>
            ) : status?.entitled ? (
              <span className="rounded-full bg-emerald-50 dark:bg-emerald-950/40 px-3 py-1 text-xs font-semibold text-emerald-800 dark:text-emerald-300 ring-1 ring-emerald-200 dark:ring-emerald-800">
                Entitled
              </span>
            ) : (
              <span className="rounded-full bg-amber-50 dark:bg-amber-950/40 px-3 py-1 text-xs font-semibold text-amber-900 dark:text-amber-300 ring-1 ring-amber-200 dark:ring-amber-800">
                Not entitled
              </span>
            )}
            {status?.merchant?.stage ? (
              <span className="rounded-full bg-blue-50 dark:bg-blue-950/40 px-3 py-1 text-xs font-semibold text-blue-900 dark:text-blue-300 ring-1 ring-blue-200 dark:ring-blue-800">
                {status.merchant.stage}
              </span>
            ) : null}
            {status?.merchant?.device_ready ? (
              <span className="rounded-full bg-slate-100 dark:bg-slate-800 px-3 py-1 text-xs font-semibold text-slate-800 dark:text-slate-200 ring-1 ring-slate-200 dark:ring-slate-700">
                Device ready
              </span>
            ) : null}
            {status?.merchant?.twofa_ok_today ? (
              <span className="rounded-full bg-emerald-50 dark:bg-emerald-950/40 px-3 py-1 text-xs font-semibold text-emerald-800 dark:text-emerald-300 ring-1 ring-emerald-200 dark:ring-emerald-800">
                2FA today
              </span>
            ) : null}
          </div>
        </header>

        {!status?.is_admin && activeJourney >= 0 ? (
          <div className="overflow-x-auto rounded-xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900 px-3 py-3 shadow-sm">
            <ol className="flex min-w-max items-center gap-2">
              {JOURNEY.map((step, idx) => {
                const done = idx < activeJourney;
                const current = idx === activeJourney;
                return (
                  <li key={step.key} className="flex items-center gap-2">
                    <Link
                      to={step.to}
                      className={`rounded-lg px-3 py-1.5 text-xs font-semibold transition ${
                        current
                          ? 'bg-blue-600 text-white'
                          : done
                            ? 'bg-emerald-50 dark:bg-emerald-950/40 text-emerald-800 dark:text-emerald-300'
                            : 'bg-slate-100 dark:bg-slate-800 text-slate-500 dark:text-slate-400'
                      }`}
                    >
                      {idx + 1}. {step.label}
                    </Link>
                    {idx < JOURNEY.length - 1 ? <span className="text-slate-300">→</span> : null}
                  </li>
                );
              })}
            </ol>
          </div>
        ) : null}

        {/* Mobile trade strip */}
        <nav className="flex gap-2 overflow-x-auto pb-1 lg:hidden">
          {NAV.filter((n) => n.group === 'trade' || n.group === 'setup' || n.end).map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.end}
              className={({ isActive }) =>
                `whitespace-nowrap rounded-full px-3 py-1.5 text-xs font-semibold ring-1 ${
                  isActive
                    ? 'bg-blue-600 text-white ring-blue-600'
                    : 'bg-white dark:bg-slate-900 text-slate-700 dark:text-slate-300 ring-slate-200 dark:ring-slate-700'
                }`
              }
            >
              {item.label}
            </NavLink>
          ))}
        </nav>

        <div className="grid gap-6 lg:grid-cols-[210px_1fr]">
          <aside className="hidden h-fit lg:block">
            <Card padding="sm" shadow="sm" className="sticky top-4">
              <nav className="flex flex-col gap-0.5">
                {NAV.map((item) => (
                  <NavLink
                    key={item.to}
                    to={item.to}
                    end={item.end}
                    className={({ isActive }) =>
                      `rounded-lg px-3 py-2 text-sm font-medium transition ${
                        isActive
                          ? 'bg-blue-600 text-white'
                          : 'text-slate-600 dark:text-slate-400 hover:bg-slate-50 dark:hover:bg-slate-800 hover:text-slate-900 dark:hover:text-slate-100'
                      }`
                    }
                  >
                    {item.label}
                  </NavLink>
                ))}
              </nav>
              <div className="mt-3 border-t border-slate-100 dark:border-slate-800 px-2 pt-3">
                <Link to="/dashboard" className="text-xs font-semibold text-slate-500 dark:text-slate-400 hover:text-blue-700 dark:hover:text-blue-200">
                  ← Main dashboard
                </Link>
              </div>
            </Card>
          </aside>
          <main className="min-w-0">{child}</main>
        </div>
      </div>
    </div>
  );
};

export default AepsLayout;
