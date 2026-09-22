import React, { useEffect, useMemo, useState } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { useAuth } from '../../context/AuthContext';
import { useWallet, PERIOD_LABELS, periodDateRange } from '../../context/WalletContext';
import {
  canViewCommissionWallet,
  isAdminOperationalIsolationRole,
  isAdminUser,
} from '../../utils/rolePermissions';
import { usersAPI } from '../../services/api';
import WalletCard from './WalletCard';
import GreetingBanner from './GreetingBanner';
import MainWalletBalanceCard from './MainWalletBalanceCard';
import PrimaryActionButtons from './PrimaryActionButtons';
import RecentTransactionsTable from './RecentTransactionsTable';
import TodaysSummaryWidget from './TodaysSummaryWidget';
import TransactionConfidenceBanner from './TransactionConfidenceBanner';
import ServicesGrid from './ServicesGrid';
import AdminDashboardHome from './AdminDashboardHome';
import { buildPrimaryActions, buildServiceTiles } from './dashboardCatalog';
import AnnouncementBanner from './AnnouncementBanner';
import KycProfileSyncAlert from '../onboarding/KycProfileSyncAlert';
import OperatorOptionalBanner from './OperatorOptionalBanner';
import { FiChevronRight } from 'react-icons/fi';
import { FaUsers } from 'react-icons/fa6';

const SECTION_HEADING_CLASS =
  'text-[12px] font-semibold uppercase tracking-[0.12em] text-slate-500 dark:text-slate-400';

const Dashboard = () => {
  const { user, maintenance } = useAuth();
  const {
    wallets,
    loading,
    loadWallets,
    earningsPeriod,
    changeEarningsPeriod,
    earningsRefreshing,
  } = useWallet();
  const navigate = useNavigate();
  const location = useLocation();
  const [flashInfo, setFlashInfo] = useState('');

  useEffect(() => {
    const msg = location.state?.infoMessage;
    if (msg) {
      setFlashInfo(String(msg));
      navigate(location.pathname, { replace: true, state: {} });
    }
  }, [location.state, location.pathname, navigate]);

  useEffect(() => {
    loadWallets();
  }, [loadWallets]);

  useEffect(() => {
    const refresh = () => loadWallets();
    const onVisibility = () => {
      if (document.visibilityState === 'visible') refresh();
    };
    window.addEventListener('focus', refresh);
    document.addEventListener('visibilitychange', onVisibility);
    return () => {
      window.removeEventListener('focus', refresh);
      document.removeEventListener('visibilitychange', onVisibility);
    };
  }, [loadWallets]);

  const showEarnings = canViewCommissionWallet(user?.role);
  const adminOps = isAdminOperationalIsolationRole(user?.role);
  const isOperator = isAdminUser(user);
  const showNetworkCensus = Boolean(user?.role) && user.role !== 'Retailer';

  const [userCensus, setUserCensus] = useState(null);

  useEffect(() => {
    if (adminOps || !showNetworkCensus) {
      setUserCensus(null);
      return undefined;
    }
    let mounted = true;
    usersAPI.getUserStats().then((res) => {
      if (!mounted) return;
      if (res.success && res.data) {
        setUserCensus({
          total: Number(res.data.total) || 0,
          active: Number(res.data.active) || 0,
          disabled: Number(res.data.disabled) || 0,
          restricted: Number(res.data.restricted) || 0,
        });
      } else {
        setUserCensus(null);
      }
    });
    return () => {
      mounted = false;
    };
  }, [user?.id, user?.role, showNetworkCensus, adminOps]);

  const primaryActions = useMemo(
    () => buildPrimaryActions({ user, maintenance, navigate, qrStats: null }),
    [user, maintenance, navigate]
  );

  const serviceTiles = useMemo(
    () =>
      buildServiceTiles({
        user,
        maintenance,
        navigate,
        qrStats: null,
        includeFundActions: false,
      }),
    [user, maintenance, navigate]
  );

  const alerts = (
    <>
      <AnnouncementBanner />
      {flashInfo ? (
        <div className="rounded-lg border border-blue-200 bg-blue-50 px-4 py-3 text-sm text-blue-900 dark:border-blue-800 dark:bg-blue-950/40 dark:text-blue-200">
          {flashInfo}
        </div>
      ) : null}
      <KycProfileSyncAlert />
      <OperatorOptionalBanner user={user} />
    </>
  );

  if (adminOps) {
    return (
      <div className="space-y-5 sm:space-y-6">
        {alerts}
        <AdminDashboardHome user={user} flashInfo={null} />
      </div>
    );
  }

  /** Channel earners (MD / SD / Distributor) — commission sits beside main wallet. */
  const channelCommission = showEarnings && !adminOps;

  const commissionCard = channelCommission ? (
    loading ? (
      <div className="h-full min-h-[88px] animate-pulse rounded-2xl bg-slate-100 dark:bg-slate-800 lg:min-h-[120px]" />
    ) : (
      <WalletCard
        compact
        type="commission"
        amount={wallets.earnings}
        subtitle={`${PERIOD_LABELS[earningsPeriod] || 'Today'} · to main`}
        period={earningsPeriod}
        onPeriodChange={changeEarningsPeriod}
        refreshing={earningsRefreshing}
        onClick={() => {
          const range = periodDateRange(earningsPeriod);
          const q = new URLSearchParams({
            date_from: range.date_from,
            date_to: range.date_to,
          });
          navigate(`/reports/commission?${q.toString()}`);
        }}
      />
    )
  ) : null;

  const networkBlock =
    showNetworkCensus && userCensus ? (
      <section aria-labelledby="dash-users-heading">
        <div className="mb-2.5 flex flex-wrap items-center justify-between gap-2">
          <h2 id="dash-users-heading" className={`flex items-center gap-2 ${SECTION_HEADING_CLASS}`}>
            <FaUsers className="text-slate-400" size={13} aria-hidden />
            {isOperator ? 'Platform users' : 'Your network'}
          </h2>
          <button
            type="button"
            onClick={() => navigate('/user-management/users')}
            className="inline-flex items-center gap-1 text-xs font-semibold text-indigo-600 hover:text-indigo-800 dark:text-indigo-400 dark:hover:text-indigo-300"
          >
            Open directory
            <FiChevronRight size={14} aria-hidden />
          </button>
        </div>
        <div className="flex flex-wrap gap-2">
          {[
            { label: 'Total', value: userCensus.total, status: null },
            { label: 'Active', value: userCensus.active, status: 'active' },
            { label: 'Disabled', value: userCensus.disabled, status: 'disabled' },
            ...(isOperator
              ? [{ label: 'Restricted', value: userCensus.restricted, status: 'restricted' }]
              : []),
          ].map((chip) => (
            <button
              key={chip.label}
              type="button"
              onClick={() =>
                navigate(
                  chip.status
                    ? `/user-management/users?account_status=${chip.status}`
                    : '/user-management/users',
                )
              }
              className="inline-flex items-center gap-2 rounded-lg border border-slate-200 bg-white px-3 py-1.5 text-xs font-semibold text-slate-700 shadow-sm transition hover:border-indigo-200 hover:bg-indigo-50/60 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-300 dark:hover:border-indigo-800 dark:hover:bg-indigo-950/40"
            >
              <span>{chip.label}</span>
              <span className="rounded-md bg-slate-100 px-1.5 py-0.5 tabular-nums text-[11px] text-slate-800 dark:bg-slate-800 dark:text-slate-200">
                {chip.value}
              </span>
            </button>
          ))}
        </div>
      </section>
    ) : null;

  return (
    <div className="mx-auto max-w-7xl space-y-3 pb-8 sm:space-y-6">
      {alerts}

      <GreetingBanner user={user} />

      <section
        className={`grid grid-cols-1 gap-2 sm:gap-3 lg:gap-3 ${
          channelCommission && primaryActions.length >= 2
            ? 'lg:grid-cols-4'
            : primaryActions.length >= 2
              ? 'lg:grid-cols-3'
              : channelCommission
                ? 'sm:grid-cols-2'
                : 'sm:grid-cols-2'
        }`}
        aria-label="Wallet and money actions"
      >
        {channelCommission ? (
          <div className="grid grid-cols-2 gap-2 sm:gap-3 lg:contents">
            <MainWalletBalanceCard compact />
            {commissionCard}
          </div>
        ) : (
          <MainWalletBalanceCard />
        )}
        <PrimaryActionButtons actions={primaryActions} />
      </section>

      <ServicesGrid
        id="dash-services-heading"
        title="Services"
        tiles={serviceTiles}
        columnsClass="grid-cols-2 sm:grid-cols-3"
        headerAction={
          serviceTiles.length ? (
            <button
              type="button"
              onClick={() => navigate('/services')}
              className="text-xs font-semibold text-blue-600 hover:text-blue-800 dark:text-blue-400"
            >
              View All →
            </button>
          ) : null
        }
      />

      <div className="grid grid-cols-1 gap-5 lg:grid-cols-[minmax(0,1fr)_20rem] xl:grid-cols-[minmax(0,1fr)_22rem]">
        <div className="space-y-5">
          <RecentTransactionsTable />
          {networkBlock}
        </div>
        <div className="space-y-5">
          <TodaysSummaryWidget />
        </div>
      </div>

      <TransactionConfidenceBanner />
    </div>
  );
};

export default Dashboard;
