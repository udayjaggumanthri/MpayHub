import React, { useEffect, useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../../context/AuthContext';
import { useWallet } from '../../context/WalletContext';
import {
  canViewCommissionWallet,
  isAdminOperationalIsolationRole,
  isFinancialTxBlockedRole,
} from '../../utils/rolePermissions';
import { reportsAPI } from '../../services/api';
import { formatCurrency } from '../../utils/formatters';
import WalletCard from './WalletCard';
import AnnouncementBanner from './AnnouncementBanner';
import Card from '../common/Card';
import DashboardAnalyticsCharts from './DashboardAnalyticsCharts';
import { FiUser, FiChevronRight } from 'react-icons/fi';
import {
  FaArrowUp,
  FaArrowDown,
  FaMoneyBillWave,
  FaGear,
  FaBoxOpen,
  FaBullhorn,
  FaChartLine,
  FaWallet,
  FaBolt,
  FaChartPie,
} from 'react-icons/fa6';

function todayIsoDate() {
  return new Date().toISOString().slice(0, 10);
}

const Dashboard = () => {
  const { user } = useAuth();
  const { wallets, loading, loadWallets } = useWallet();
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

  const quickActions = useMemo(() => {
    if (adminOps) {
      return [
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
        title: 'BBPS — Pay bills',
        description: 'Electricity, mobile, DTH & more',
        icon: FaMoneyBillWave,
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
  }, [adminOps, txBlocked, navigate]);

  useEffect(() => {
    let mounted = true;
    const loadAnalytics = async () => {
      setAnalyticsLoading(true);
      const params = { interval: analyticsFilters.interval };
      if (analyticsFilters.dateFrom) params.date_from = analyticsFilters.dateFrom;
      if (analyticsFilters.dateTo) params.date_to = analyticsFilters.dateTo;
      if (analyticsFilters.gateway) params.gateway = analyticsFilters.gateway;
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
  }, [analyticsFilters]);

  const gatewayCardSubtitle = adminOps
    ? 'Compare gateways, switch daily/monthly, and drill into the table below. Defaults to today.'
    : 'Track pay-in sales, fees, and platform profit. Defaults to today’s activity.';

  const quickSectionTitle = adminOps ? 'Administration' : 'Payments & services';
  const quickSectionSubtitle = adminOps
    ? 'Gateways, commercial packages, announcements, and reports'
    : txBlocked
      ? 'Reports and team visibility (your role cannot initiate wallet movements)'
      : 'Load money, withdraw, or pay bills via BBPS';

  return (
    <>
      <AnnouncementBanner />
      {loading ? (
        <div className="flex min-h-[400px] items-center justify-center">
          <div className="text-center">
            <div className="mx-auto h-12 w-12 animate-spin rounded-full border-b-2 border-blue-600" />
            <p className="mt-4 text-slate-600">Loading dashboard…</p>
          </div>
        </div>
      ) : (
        <div className="mx-auto max-w-7xl space-y-10 pb-10">
          <Card className="border border-slate-200/90 shadow-sm" padding="lg">
            <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
              <div>
                <h1 className="text-2xl font-bold tracking-tight text-slate-900 sm:text-3xl">
                  Welcome back, {user?.name || 'there'}!
                </h1>
                <div className="mt-3 flex flex-wrap items-center gap-x-4 gap-y-1 text-sm text-slate-600">
                  <span className="inline-flex items-center gap-1.5">
                    <FiUser className="text-slate-400" size={16} />
                    <span>
                      ID{' '}
                      <span className="font-semibold text-slate-900">
                        {user?.userId || user?.user_id || '—'}
                      </span>
                    </span>
                  </span>
                  <span className="hidden text-slate-300 sm:inline">|</span>
                  <span>
                    Role: <span className="font-semibold text-slate-900">{user?.role}</span>
                  </span>
                </div>
              </div>
              <div className="rounded-xl border border-slate-100 bg-slate-50/80 px-4 py-2 text-xs text-slate-500">
                Enterprise overview · balances first, then actions, then performance
              </div>
            </div>
          </Card>

          {/* 1 — Wallets & commission */}
          <section aria-labelledby="dash-wallets-heading">
            <div className="mb-5 flex flex-col gap-1 border-b border-slate-100 pb-4 sm:flex-row sm:items-end sm:justify-between">
              <div>
                <h2
                  id="dash-wallets-heading"
                  className="flex items-center gap-2 text-lg font-semibold tracking-tight text-slate-900"
                >
                  <span className="flex h-9 w-9 items-center justify-center rounded-lg bg-blue-50 text-blue-700">
                    <FaWallet className="h-5 w-5" />
                  </span>
                  Wallets &amp; commission
                </h2>
                <p className="mt-1 max-w-2xl text-sm text-slate-500">
                  Balances across your wallets. Open ledger history for any card.
                </p>
              </div>
            </div>
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
              <WalletCard
                type="main"
                amount={wallets.main}
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
          </section>

          {/* 2 — Operational / admin quick actions */}
          <section aria-labelledby="dash-actions-heading">
            <div className="mb-5 flex flex-col gap-1 border-b border-slate-100 pb-4">
              <h2
                id="dash-actions-heading"
                className="flex items-center gap-2 text-lg font-semibold tracking-tight text-slate-900"
              >
                <span className="flex h-9 w-9 items-center justify-center rounded-lg bg-amber-50 text-amber-700">
                  <FaBolt className="h-5 w-5" />
                </span>
                {quickSectionTitle}
              </h2>
              <p className="text-sm text-slate-500">{quickSectionSubtitle}</p>
            </div>
            <div
              className={`grid grid-cols-1 gap-4 sm:grid-cols-2 ${
                adminOps ? 'lg:grid-cols-4' : 'lg:grid-cols-3'
              }`}
            >
              {quickActions.map((action) => {
                const Icon = action.icon;
                return (
                  <button
                    key={action.id}
                    type="button"
                    onClick={action.onClick}
                    className="group flex items-center gap-4 rounded-2xl border border-slate-200/90 bg-white p-5 text-left shadow-sm transition-all hover:-translate-y-0.5 hover:border-slate-300 hover:shadow-md"
                  >
                    <div
                      className={`flex-shrink-0 rounded-2xl bg-gradient-to-br p-4 shadow-md ${action.gradient}`}
                    >
                      <Icon size={24} className="text-white" />
                    </div>
                    <div className="min-w-0 flex-1">
                      <p className="font-semibold text-slate-900">{action.title}</p>
                      <p className="mt-0.5 text-sm text-slate-500">{action.description}</p>
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

          {/* 3 — Analytics & gateway performance */}
          <section aria-labelledby="dash-analytics-heading" className="space-y-4">
            <div className="flex flex-col gap-1 border-b border-slate-100 pb-4">
              <h2
                id="dash-analytics-heading"
                className="flex items-center gap-2 text-lg font-semibold tracking-tight text-slate-900"
              >
                <span className="flex h-9 w-9 items-center justify-center rounded-lg bg-emerald-50 text-emerald-700">
                  <FaChartPie className="h-5 w-5" />
                </span>
                Gateway sales &amp; profit
              </h2>
              <p className="text-sm text-slate-500">{gatewayCardSubtitle}</p>
            </div>

            <Card className="border border-slate-200/90 shadow-sm" padding="lg">
              <div className="mb-6 grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
                <div className="rounded-xl border border-slate-100 bg-white p-4 shadow-sm">
                  <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">Sales (period)</p>
                  <p className="mt-1 text-xl font-bold tabular-nums text-slate-900">
                    {formatCurrency(parseFloat(analyticsTotals.payin_sales || 0))}
                  </p>
                </div>
                <div className="rounded-xl border border-slate-100 bg-white p-4 shadow-sm">
                  <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">Charges (period)</p>
                  <p className="mt-1 text-xl font-bold tabular-nums text-amber-900">
                    {formatCurrency(parseFloat(analyticsTotals.payin_charges || 0))}
                  </p>
                </div>
                <div className="rounded-xl border border-emerald-100 bg-emerald-50/50 p-4 shadow-sm">
                  <p className="text-xs font-semibold uppercase tracking-wide text-emerald-800">Platform profit</p>
                  <p className="mt-1 text-xl font-bold tabular-nums text-emerald-900">
                    {formatCurrency(parseFloat(analyticsTotals.platform_profit || 0))}
                  </p>
                </div>
                <div className="rounded-xl border border-slate-100 bg-white p-4 shadow-sm">
                  <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">Transactions</p>
                  <p className="mt-1 text-xl font-bold tabular-nums text-slate-900">
                    {analyticsTotals.transactions_count ?? 0}
                  </p>
                </div>
              </div>

              <div className="mb-8 flex flex-wrap gap-3 rounded-xl border border-slate-100 bg-slate-50/50 p-4">
                <select
                  value={analyticsFilters.interval}
                  onChange={(e) => setAnalyticsFilters((f) => ({ ...f, interval: e.target.value }))}
                  className="min-w-[140px] rounded-lg border border-slate-200 bg-white px-3 py-2.5 text-sm font-medium text-slate-800 shadow-sm"
                >
                  <option value="daily">Daily buckets</option>
                  <option value="monthly">Monthly buckets</option>
                </select>
                <input
                  type="date"
                  value={analyticsFilters.dateFrom}
                  onChange={(e) => setAnalyticsFilters((f) => ({ ...f, dateFrom: e.target.value }))}
                  className="rounded-lg border border-slate-200 bg-white px-3 py-2.5 text-sm shadow-sm"
                  aria-label="From date"
                />
                <input
                  type="date"
                  value={analyticsFilters.dateTo}
                  onChange={(e) => setAnalyticsFilters((f) => ({ ...f, dateTo: e.target.value }))}
                  className="rounded-lg border border-slate-200 bg-white px-3 py-2.5 text-sm shadow-sm"
                  aria-label="To date"
                />
                <select
                  value={analyticsFilters.gateway}
                  onChange={(e) => setAnalyticsFilters((f) => ({ ...f, gateway: e.target.value }))}
                  className="min-w-[180px] flex-1 rounded-lg border border-slate-200 bg-white px-3 py-2.5 text-sm font-medium text-slate-800 shadow-sm"
                >
                  <option value="">All gateways</option>
                  {analyticsGateways.map((g) => (
                    <option key={g} value={g}>
                      {g}
                    </option>
                  ))}
                </select>
              </div>

              <DashboardAnalyticsCharts rows={analyticsRows} loading={analyticsLoading} />

              <div className="mt-8 border-t border-slate-100 pt-6">
                <h3 className="mb-3 text-sm font-semibold text-slate-800">Detailed breakdown</h3>
                {analyticsLoading ? (
                  <div className="py-10 text-center text-sm text-slate-500">Loading table…</div>
                ) : analyticsRows.length === 0 ? (
                  <div className="py-10 text-center text-sm text-slate-500">
                    No rows for the selected filters. Adjust dates or gateway.
                  </div>
                ) : (
                  <div className="overflow-x-auto rounded-xl border border-slate-100">
                    <table className="min-w-full border-collapse text-sm">
                      <thead>
                        <tr className="border-b border-slate-200 bg-slate-50/90">
                          <th className="px-4 py-3 text-left font-semibold text-slate-600">Period</th>
                          <th className="px-4 py-3 text-left font-semibold text-slate-600">Gateway</th>
                          <th className="px-4 py-3 text-right font-semibold text-slate-600">Sales</th>
                          <th className="px-4 py-3 text-right font-semibold text-slate-600">Charges</th>
                          <th className="px-4 py-3 text-right font-semibold text-slate-600">Profit</th>
                          <th className="px-4 py-3 text-right font-semibold text-slate-600">Count</th>
                        </tr>
                      </thead>
                      <tbody>
                        {analyticsRows.map((r, i) => (
                          <tr key={`${r.period}-${r.gateway}-${i}`} className="border-b border-slate-100/90 hover:bg-slate-50/50">
                            <td className="px-4 py-3 text-slate-700">{r.period}</td>
                            <td className="px-4 py-3 text-slate-800">{r.gateway}</td>
                            <td className="px-4 py-3 text-right tabular-nums text-slate-900">
                              {formatCurrency(parseFloat(r.payin_sales || 0))}
                            </td>
                            <td className="px-4 py-3 text-right tabular-nums text-amber-900">
                              {formatCurrency(parseFloat(r.payin_charges || 0))}
                            </td>
                            <td className="px-4 py-3 text-right font-medium tabular-nums text-emerald-800">
                              {formatCurrency(parseFloat(r.platform_profit || 0))}
                            </td>
                            <td className="px-4 py-3 text-right text-slate-700">{r.transactions_count || 0}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
              </div>
            </Card>
          </section>
        </div>
      )}
    </>
  );
};

export default Dashboard;
