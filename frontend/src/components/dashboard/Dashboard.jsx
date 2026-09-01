import React, { useEffect, useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../../context/AuthContext';
import { useWallet } from '../../context/WalletContext';
import {
  canViewCommissionWallet,
  isAdminOperationalIsolationRole,
  isFinancialTxBlockedRole,
} from '../../utils/rolePermissions';
import { reportsAPI, adminAPI } from '../../services/api';
import { formatCurrency } from '../../utils/formatters';
import WalletCard from './WalletCard';
import AnnouncementBanner from './AnnouncementBanner';
import KycProfileSyncAlert from '../onboarding/KycProfileSyncAlert';
import Card from '../common/Card';
import DashboardAnalyticsCharts from './DashboardAnalyticsCharts';
import DashboardTransactionStatus from './DashboardTransactionStatus';
import ReportDateRange from '../common/ReportDateRange';
import { todayIsoDate } from '../../utils/reportDate';
import { FiUser, FiChevronRight } from 'react-icons/fi';
import bMnemonicPrimary from '../../assets/bbps/b-mnemonic-primary.svg';
import {
  FaArrowUp,
  FaArrowDown,
  FaMoneyBillWave,
  FaGear,
  FaBoxOpen,
  FaBullhorn,
  FaChartLine,
  FaQrcode,
} from 'react-icons/fa6';

function periodDatesForInterval(interval) {
  const today = todayIsoDate();
  if (interval === 'monthly') {
    const [y, m] = today.split('-');
    return { dateFrom: `${y}-${m}-01`, dateTo: today };
  }
  return { dateFrom: today, dateTo: today };
}

const Dashboard = () => {
  const { user } = useAuth();
  const { wallets, walletMeta, loading, loadWallets } = useWallet();
  const navigate = useNavigate();

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

  const showCommissionWallet = canViewCommissionWallet(user?.role);
  const showProfitWallet = String(user?.role || '').toLowerCase() === 'admin';
  const txBlocked = isFinancialTxBlockedRole(user?.role);
  const adminOps = isAdminOperationalIsolationRole(user?.role);

  const [analyticsLoading, setAnalyticsLoading] = useState(false);
  const [analyticsRows, setAnalyticsRows] = useState([]);
  const [analyticsGateways, setAnalyticsGateways] = useState([]);
  const [analyticsTotals, setAnalyticsTotals] = useState({
    payin_sales: '0',
    payin_charges: '0',
    platform_profit: '0',
    transactions_count: 0,
  });
  const [analyticsFilters, setAnalyticsFilters] = useState(() => ({
    interval: 'daily',
    dateFrom: todayIsoDate(),
    dateTo: todayIsoDate(),
    gateway: '',
  }));
  const [appliedAnalytics, setAppliedAnalytics] = useState(() => ({
    interval: 'daily',
    dateFrom: todayIsoDate(),
    dateTo: todayIsoDate(),
    gateway: '',
  }));
  const [qrStats, setQrStats] = useState(null);

  useEffect(() => {
    if (!adminOps) return undefined;
    let mounted = true;
    adminAPI.getQrOperationsStats().then((res) => {
      if (mounted && res.success) setQrStats(res.data);
    });
    return () => {
      mounted = false;
    };
  }, [adminOps]);

  const quickActions = useMemo(() => {
    if (adminOps) {
      const pendingQr = qrStats?.pending_count ?? 0;
      return [
        {
          id: 'admin-qr-ops',
          title: 'QR operations',
          description:
            pendingQr > 0
              ? `${pendingQr} submission${pendingQr === 1 ? '' : 's'} awaiting review`
              : 'Review manual QR pay-in submissions',
          icon: FaQrcode,
          gradient: 'from-amber-500 to-orange-600',
          badge: pendingQr > 0 ? pendingQr : null,
          onClick: () => navigate('/admin/pay-in-qr-operations?status=PENDING_REVIEW'),
        },
        {
          id: 'admin-gateways',
          title: 'Payment gateways',
          description: 'Configure payment gateways',
          icon: FaGear,
          gradient: 'from-slate-600 to-slate-800',
          onClick: () => navigate('/admin/gateways'),
        },
        {
          id: 'admin-packages',
          title: 'Pay-in packages',
          description: 'Commission splits and payout slabs',
          icon: FaBoxOpen,
          gradient: 'from-indigo-600 to-blue-700',
          onClick: () => navigate('/admin/pay-in-packages'),
        },
        {
          id: 'admin-announcements',
          title: 'Announcements',
          description: 'Platform notices and banners',
          icon: FaBullhorn,
          gradient: 'from-violet-600 to-purple-700',
          onClick: () => navigate('/admin/announcements'),
        },
        {
          id: 'admin-payin-report',
          title: 'Pay-in report',
          description: 'Review load-money transactions',
          icon: FaChartLine,
          gradient: 'from-emerald-600 to-teal-700',
          onClick: () => navigate('/reports/payin'),
        },
      ];
    }
    const base = [
      {
        id: 'load-money',
        title: 'Load Money',
        description: 'Add funds from your bank to main wallet',
        icon: FaArrowUp,
        gradient: 'from-blue-600 to-indigo-700',
        onClick: () => navigate('/fund-management/load-money'),
      },
      {
        id: 'payout',
        title: 'Payout',
        description: 'Withdraw to your linked bank account',
        icon: FaArrowDown,
        gradient: 'from-sky-600 to-blue-700',
        onClick: () => navigate('/fund-management/payout'),
      },
      {
        id: 'pay-bills',
        title: 'Pay Bill',
        description: 'Electricity, mobile, DTH & more',
        icon: FaMoneyBillWave,
        iconImage: bMnemonicPrimary,
        gradient: 'from-violet-600 to-fuchsia-700',
        onClick: () => navigate('/bill-payments/pay'),
      },
    ];
    if (txBlocked) {
      return [
        {
          id: 'team-payin',
          title: 'Team activity',
          description: 'Pay-in and passbook for your downline',
          icon: FaArrowUp,
          gradient: 'from-blue-600 to-indigo-700',
          onClick: () => navigate('/reports/payin'),
        },
        {
          id: 'commission-report',
          title: 'Commission',
          description: 'Commission wallet activity',
          icon: FaArrowDown,
          gradient: 'from-emerald-600 to-teal-700',
          onClick: () => navigate('/reports/commission'),
        },
      ];
    }
    return base;
  }, [adminOps, txBlocked, navigate, qrStats]);

  useEffect(() => {
    if (!adminOps) return undefined;
    let mounted = true;
    const loadAnalytics = async () => {
      setAnalyticsLoading(true);
      const params = { interval: appliedAnalytics.interval };
      if (appliedAnalytics.dateFrom) params.date_from = appliedAnalytics.dateFrom;
      if (appliedAnalytics.dateTo) params.date_to = appliedAnalytics.dateTo;
      if (appliedAnalytics.gateway) params.gateway = appliedAnalytics.gateway;
      const res = await reportsAPI.getAnalyticsSummary(params);
      if (!mounted) return;
      const emptyTotals = {
        payin_sales: '0',
        payin_charges: '0',
        platform_profit: '0',
        transactions_count: 0,
      };
      if (res.success) {
        setAnalyticsRows(res.data?.rows || []);
        setAnalyticsGateways(res.data?.available_gateways || []);
        setAnalyticsTotals(res.data?.totals ?? emptyTotals);
      } else {
        setAnalyticsRows([]);
        setAnalyticsGateways([]);
        setAnalyticsTotals(emptyTotals);
      }
      setAnalyticsLoading(false);
    };
    loadAnalytics();
    return () => {
      mounted = false;
    };
  }, [adminOps, appliedAnalytics]);

  const quickSectionTitle = adminOps ? 'Administration' : 'Payments & services';

  return (
    <>
      <AnnouncementBanner />
      <KycProfileSyncAlert className="mx-auto mb-6 max-w-7xl" />
        <div className="mx-auto max-w-7xl space-y-10 pb-10">
          <Card className="border border-slate-200/90 dark:border-slate-700/90 shadow-sm" padding="lg">
            <div
              className={
                adminOps
                  ? 'flex flex-col gap-5 xl:flex-row xl:items-start xl:justify-between xl:gap-8'
                  : 'flex flex-col gap-4'
              }
            >
              <div className="min-w-0 shrink-0">
                <h1 className="text-2xl font-bold tracking-tight text-slate-900 dark:text-slate-100 sm:text-3xl">
                  Welcome back, {user?.name || 'there'}!
                </h1>
                <div className="mt-2 flex flex-wrap items-center gap-x-3 gap-y-1 text-sm text-slate-600 dark:text-slate-400">
                  <span className="inline-flex items-center gap-1.5">
                    <FiUser className="text-slate-400 dark:text-slate-500" size={15} aria-hidden />
                    <span className="font-semibold text-slate-900 dark:text-slate-100">
                      {user?.displayCode || user?.userId || user?.user_id || user?.memberId || '—'}
                    </span>
                  </span>
                  <span className="text-slate-300" aria-hidden>
                    ·
                  </span>
                  <span className="text-slate-600 dark:text-slate-400">{user?.role}</span>
                </div>
              </div>
              {adminOps ? (
                <div className="w-full min-w-0 xl:max-w-[min(100%,32rem)] xl:flex-1">
                  <DashboardTransactionStatus variant="compact" />
                </div>
              ) : null}
            </div>
          </Card>

          {/* 1 — Wallets & commission */}
          <section aria-labelledby="dash-wallets-heading">
            <h2
              id="dash-wallets-heading"
              className="mb-4 text-base font-semibold tracking-tight text-slate-900 dark:text-slate-100"
            >
              Wallets
            </h2>
      {loading ? (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4" aria-busy="true">
          {(showProfitWallet || showCommissionWallet ? [0, 1, 2, 3] : [0, 1, 2]).map((i) => (
            <div
              key={i}
              className="h-36 animate-pulse rounded-2xl border border-slate-200/90 dark:border-slate-700/90 bg-slate-100 dark:bg-slate-800"
            />
          ))}
        </div>
      ) : (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
              <WalletCard
                type="main"
                amount={wallets.main}
                subtitle={
                  walletMeta?.main?.source === 'network_total'
                    ? "All users' main wallets"
                    : undefined
                }
                onClick={() => navigate('/reports/passbook')}
              />
              {showCommissionWallet && (
                <WalletCard
                  type="commission"
                  amount={wallets.commission}
                  onClick={() => navigate('/reports/commission')}
                />
              )}
              <WalletCard
                type="bbps"
                amount={wallets.bbps}
                subtitle={
                  walletMeta?.bbps?.source === 'network_total'
                    ? "All users' BBPS wallets"
                    : undefined
                }
                onClick={() => navigate('/reports/bbps')}
              />
              {showProfitWallet && (
                <WalletCard
                  type="profit"
                  amount={wallets.profit}
                  onClick={() => navigate('/wallets/profit')}
                />
              )}
            </div>
          )}
          </section>

          {/* 2 — Operational / admin quick actions */}
          <section aria-labelledby="dash-actions-heading">
            {adminOps && (qrStats?.pending_count ?? 0) > 0 ? (
              <div className="mb-4 flex flex-col gap-3 rounded-xl border border-amber-200 dark:border-amber-800 bg-amber-50 dark:bg-amber-950/40 px-4 py-4 sm:flex-row sm:items-center sm:justify-between">
                <div>
                  <p className="font-semibold text-amber-900 dark:text-amber-300">
                    {qrStats.pending_count} manual QR pay-in
                    {qrStats.pending_count === 1 ? '' : 's'} awaiting review
                  </p>
                  <p className="mt-1 text-sm text-amber-800 dark:text-amber-300">
                    Retailers have submitted UTR proof. Approve or reject in the operations queue.
                  </p>
                </div>
                <button
                  type="button"
                  onClick={() => navigate('/admin/pay-in-qr-operations?status=PENDING_REVIEW')}
                  className="shrink-0 rounded-lg bg-amber-600 px-4 py-2 text-sm font-semibold text-white hover:bg-amber-700"
                >
                  Open QR queue
                </button>
              </div>
            ) : null}
            <h2
              id="dash-actions-heading"
              className="mb-4 text-base font-semibold tracking-tight text-slate-900 dark:text-slate-100"
            >
              {quickSectionTitle}
            </h2>
            <div
              className={`grid grid-cols-1 gap-4 sm:grid-cols-2 ${
                adminOps ? 'lg:grid-cols-4' : 'lg:grid-cols-3'
              }`}
            >
              {quickActions.map((action) => {
                const Icon = action.icon;
                const usesImageIcon = Boolean(action.iconImage);
                return (
                  <button
                    key={action.id}
                    type="button"
                    onClick={action.onClick}
                    className="group flex items-center gap-4 rounded-2xl border border-slate-200/90 dark:border-slate-700/90 bg-white dark:bg-slate-900 p-5 text-left shadow-sm transition-all hover:-translate-y-0.5 hover:border-slate-300 dark:hover:border-slate-600 hover:shadow-md"
                  >
                    <div
                      className={`flex-shrink-0 rounded-2xl p-4 ${
                        usesImageIcon ? '' : `bg-gradient-to-br shadow-md ${action.gradient}`
                      }`}
                    >
                      {usesImageIcon ? (
                        <img
                          src={action.iconImage}
                          alt="Bharat Connect B mnemonic"
                          className="h-10 w-10 object-contain"
                        />
                      ) : (
                        <Icon size={24} className="text-white" />
                      )}
                    </div>
                    <div className="min-w-0 flex-1">
                      <div className="flex items-center gap-2">
                        <p className="font-semibold text-slate-900 dark:text-slate-100">{action.title}</p>
                        {action.badge ? (
                          <span className="inline-flex min-w-[1.25rem] items-center justify-center rounded-full bg-amber-500 px-1.5 py-0.5 text-xs font-bold text-white">
                            {action.badge}
                          </span>
                        ) : null}
                      </div>
                      <p className="mt-0.5 text-sm text-slate-500 dark:text-slate-400">{action.description}</p>
                    </div>
                    <FiChevronRight
                      className="flex-shrink-0 text-slate-300 transition group-hover:translate-x-0.5 group-hover:text-slate-500"
                      size={22}
                    />
                  </button>
                );
              })}
            </div>
          </section>

          {adminOps ? (
          /* 3 — Analytics & gateway performance (Admin only) */
          <section aria-labelledby="dash-analytics-heading" className="space-y-4">
            <h2
              id="dash-analytics-heading"
              className="text-base font-semibold tracking-tight text-slate-900 dark:text-slate-100"
            >
              Gateway sales &amp; profit
            </h2>

            <Card className="border border-slate-200/90 dark:border-slate-700/90 shadow-sm" padding="lg">
              <div className="mb-6 grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
                <div className={`rounded-xl border border-slate-100 dark:border-slate-700 bg-white dark:bg-slate-800/60 p-4 shadow-sm ${analyticsLoading ? 'animate-pulse' : ''}`}>
                  <p className="text-xs font-semibold uppercase tracking-wide text-slate-500 dark:text-slate-400">Sales (period)</p>
                  <p className="mt-1 text-xl font-bold tabular-nums text-slate-900 dark:text-slate-100">
                    {analyticsLoading ? '—' : formatCurrency(parseFloat(analyticsTotals.payin_sales || 0))}
                  </p>
                </div>
                <div className={`rounded-xl border border-slate-100 dark:border-slate-700 bg-white dark:bg-slate-800/60 p-4 shadow-sm ${analyticsLoading ? 'animate-pulse' : ''}`}>
                  <p className="text-xs font-semibold uppercase tracking-wide text-slate-500 dark:text-slate-400">Charges (period)</p>
                  <p className="mt-1 text-xl font-bold tabular-nums text-amber-900 dark:text-amber-300">
                    {analyticsLoading ? '—' : formatCurrency(parseFloat(analyticsTotals.payin_charges || 0))}
                  </p>
                </div>
                <div className={`rounded-xl border border-emerald-100 dark:border-emerald-800/70 bg-emerald-50/50 dark:bg-emerald-950/50 p-4 shadow-sm ${analyticsLoading ? 'animate-pulse' : ''}`}>
                  <p className="text-xs font-semibold uppercase tracking-wide text-emerald-800 dark:text-emerald-300">Platform profit</p>
                  <p className="mt-1 text-xl font-bold tabular-nums text-emerald-900 dark:text-emerald-300">
                    {analyticsLoading ? '—' : formatCurrency(parseFloat(analyticsTotals.platform_profit || 0))}
                  </p>
                </div>
                <div className={`rounded-xl border border-slate-100 dark:border-slate-700 bg-white dark:bg-slate-800/60 p-4 shadow-sm ${analyticsLoading ? 'animate-pulse' : ''}`}>
                  <p className="text-xs font-semibold uppercase tracking-wide text-slate-500 dark:text-slate-400">Transactions</p>
                  <p className="mt-1 text-xl font-bold tabular-nums text-slate-900 dark:text-slate-100">
                    {analyticsLoading ? '—' : (analyticsTotals.transactions_count ?? 0)}
                  </p>
                </div>
              </div>

              {/* items-start stops the selects stretching to the tallest cell */}
              <div className="mb-8 flex flex-wrap items-start gap-3 rounded-xl border border-slate-100 dark:border-slate-700/70 bg-slate-50/50 dark:bg-slate-800/40 p-4">
                <select
                  value={analyticsFilters.interval}
                  onChange={(e) => {
                    const interval = e.target.value;
                    const { dateFrom, dateTo } = periodDatesForInterval(interval);
                    setAnalyticsFilters((f) => ({ ...f, interval, dateFrom, dateTo }));
                    setAppliedAnalytics((f) => ({ ...f, interval, dateFrom, dateTo }));
                  }}
                  className="min-h-[44px] w-full min-w-[140px] rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900 px-3 py-2.5 text-sm font-medium text-slate-800 dark:text-slate-200 shadow-sm sm:w-auto"
                >
                  <option value="daily">Daily buckets</option>
                  <option value="monthly">Monthly buckets</option>
                </select>
                <div className="min-w-0 w-full flex-1 md:min-w-[26rem]">
                  <ReportDateRange
                    idPrefix="dash-analytics"
                    showApply
                    applyInline
                    applyLabel="Apply"
                    dateFrom={analyticsFilters.dateFrom}
                    dateTo={analyticsFilters.dateTo}
                    fromLabel=""
                    toLabel=""
                    onChange={({ dateFrom, dateTo }) =>
                      setAnalyticsFilters((f) => ({ ...f, dateFrom, dateTo }))
                    }
                    onApply={({ dateFrom, dateTo }) =>
                      setAppliedAnalytics((f) => ({ ...f, dateFrom, dateTo }))
                    }
                  />
                </div>
                <select
                  value={analyticsFilters.gateway}
                  onChange={(e) => {
                    const gateway = e.target.value;
                    setAnalyticsFilters((f) => ({ ...f, gateway }));
                    setAppliedAnalytics((f) => ({ ...f, gateway }));
                  }}
                  className="min-h-[44px] w-full min-w-[180px] rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900 px-3 py-2.5 text-sm font-medium text-slate-800 dark:text-slate-200 shadow-sm sm:w-auto sm:flex-1"
                >
                  <option value="">All gateways</option>
                  {analyticsGateways.map((g) => (
                    <option key={g} value={g}>
                      {g}
                    </option>
                  ))}
                </select>
              </div>

              <DashboardAnalyticsCharts
                rows={analyticsRows}
                loading={analyticsLoading}
                gatewayNames={analyticsGateways}
              />

              <div className="mt-8 border-t border-slate-100 dark:border-slate-800 pt-6">
                <h3 className="mb-3 text-sm font-semibold text-slate-800 dark:text-slate-200">Detailed breakdown</h3>
                {analyticsLoading ? (
                  <div className="py-10 text-center text-sm text-slate-500 dark:text-slate-400">Loading table…</div>
                ) : analyticsRows.length === 0 ? (
                  <div className="py-10 text-center text-sm text-slate-500 dark:text-slate-400">
                    No rows for the selected filters. Adjust dates or gateway.
                  </div>
                ) : (
                  <div className="overflow-x-auto rounded-xl border border-slate-100 dark:border-slate-700">
                    <table className="min-w-full border-collapse text-sm">
                      <thead>
                        <tr className="border-b border-slate-200 dark:border-slate-700 bg-slate-50/90 dark:bg-slate-800/50">
                          <th className="px-4 py-3 text-left font-semibold text-slate-600 dark:text-slate-400">Period</th>
                          <th className="px-4 py-3 text-left font-semibold text-slate-600 dark:text-slate-400">Gateway</th>
                          <th className="px-4 py-3 text-right font-semibold text-slate-600 dark:text-slate-400">Sales</th>
                          <th className="px-4 py-3 text-right font-semibold text-slate-600 dark:text-slate-400">Charges</th>
                          <th className="px-4 py-3 text-right font-semibold text-slate-600 dark:text-slate-400">Profit</th>
                          <th className="px-4 py-3 text-right font-semibold text-slate-600 dark:text-slate-400">Count</th>
                        </tr>
                      </thead>
                      <tbody>
                        {analyticsRows.map((r, i) => (
                          <tr key={`${r.period}-${r.gateway}-${i}`} className="border-b border-slate-100/90 dark:border-slate-800/90 hover:bg-slate-50/50 dark:hover:bg-slate-800/50">
                            <td className="px-4 py-3 text-slate-700 dark:text-slate-300">{r.period}</td>
                            <td className="px-4 py-3 text-slate-800 dark:text-slate-200">{r.gateway}</td>
                            <td className="px-4 py-3 text-right tabular-nums text-slate-900 dark:text-slate-100">
                              {formatCurrency(parseFloat(r.payin_sales || 0))}
                            </td>
                            <td className="px-4 py-3 text-right tabular-nums text-amber-900 dark:text-amber-300">
                              {formatCurrency(parseFloat(r.payin_charges || 0))}
                            </td>
                            <td className="px-4 py-3 text-right font-medium tabular-nums text-emerald-800 dark:text-emerald-300">
                              {formatCurrency(parseFloat(r.platform_profit || 0))}
                            </td>
                            <td className="px-4 py-3 text-right text-slate-700 dark:text-slate-300">{r.transactions_count || 0}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
              </div>
            </Card>
          </section>
          ) : null}
        </div>
    </>
  );
};

export default Dashboard;
