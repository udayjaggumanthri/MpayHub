import React, { useEffect, useState } from 'react';
import { NavLink, useLocation, useNavigate } from 'react-router-dom';
import { useAuth } from '../../../context/AuthContext';
import { isModuleEnabled } from '../../../utils/maintenanceMode';
import { isAdminUser } from '../../../utils/rolePermissions';
import Card from '../../../components/common/Card';
import Button from '../../../components/common/Button';
import cmsAPI from '../services/cmsApi';

const NAV = [
  { to: '/cms', end: true, label: 'Overview' },
  { to: '/cms/wallet', label: 'Wallet' },
  { to: '/cms/launch', label: 'Launch' },
  { to: '/cms/reports', label: 'Reports' },
];

const CmsLayout = ({ children }) => {
  const { user, maintenance } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [status, setStatus] = useState(null);
  const moduleOn = isModuleEnabled(maintenance, 'cms');

  useEffect(() => {
    cmsAPI.meStatus().then((res) => {
      if (res.success) setStatus(res.data);
    });
  }, [location.pathname]);

  if (!moduleOn) {
    return (
      <div className="flex min-h-[60vh] items-center justify-center p-6">
        <Card className="max-w-lg w-full text-center" shadow="md">
          <p className="text-xs font-semibold uppercase tracking-widest text-blue-600 dark:text-blue-400">CMS</p>
          <h1 className="mt-2 text-2xl font-bold text-slate-900 dark:text-slate-100">Service paused</h1>
          <p className="mt-3 text-slate-600 dark:text-slate-400">
            {maintenance?.cms?.message ||
              'CMS is temporarily unavailable due to maintenance. Please try again later.'}
          </p>
          <Button className="mt-6" onClick={() => navigate('/dashboard')}>
            Back to dashboard
          </Button>
        </Card>
      </div>
    );
  }

  const isAdmin = isAdminUser(user);
  const entitled = Boolean(status?.entitled) || isAdmin || status?.next_action === 'admin_ops';
  if (status && !entitled) {
    return (
      <div className="flex min-h-[60vh] items-center justify-center p-6">
        <Card className="max-w-lg w-full text-center" shadow="md">
          <p className="text-xs font-semibold uppercase tracking-widest text-emerald-600 dark:text-emerald-400">CMS</p>
          <h1 className="mt-2 text-2xl font-bold text-slate-900 dark:text-slate-100">CMS not enabled</h1>
          <p className="mt-3 text-slate-600 dark:text-slate-400">
            Ask your Admin to enable CMS on your user profile. Once enabled, you will see CMS here and under Services.
          </p>
          <Button className="mt-6" onClick={() => navigate('/dashboard')}>
            Back to dashboard
          </Button>
        </Card>
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-4 lg:flex-row lg:gap-6">
      <aside className="w-full shrink-0 lg:w-52">
        <div className="rounded-xl border border-slate-200 bg-white p-3 dark:border-slate-700 dark:bg-slate-900">
          <p className="mb-2 px-2 text-[10px] font-bold uppercase tracking-wider text-slate-400">CMS</p>
          <nav className="flex flex-row gap-1 overflow-x-auto lg:flex-col">
            {NAV.map((item) => (
              <NavLink
                key={item.to}
                to={item.to}
                end={item.end}
                className={({ isActive }) =>
                  `whitespace-nowrap rounded-lg px-3 py-2 text-sm font-medium transition ${
                    isActive
                      ? 'bg-blue-600 text-white'
                      : 'text-slate-600 hover:bg-slate-100 dark:text-slate-300 dark:hover:bg-slate-800'
                  }`
                }
              >
                {item.label}
              </NavLink>
            ))}
          </nav>
          {status?.wallet ? (
            <div className="mt-3 border-t border-slate-100 px-2 pt-3 text-xs dark:border-slate-800">
              <p className="text-slate-400">Available</p>
              <p className="text-base font-bold tabular-nums text-slate-900 dark:text-slate-100">
                ₹{Number(status.wallet.available || 0).toLocaleString('en-IN', { minimumFractionDigits: 2 })}
              </p>
            </div>
          ) : null}
        </div>
      </aside>
      <main className="min-w-0 flex-1">{children}</main>
    </div>
  );
};

export default CmsLayout;
