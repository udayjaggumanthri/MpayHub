import React, { useEffect, useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../../context/AuthContext';
import { useWallet } from '../../context/WalletContext';
import { canViewCommissionWallet, isFinancialTxBlockedRole } from '../../utils/rolePermissions';
import { reportsAPI } from '../../services/api';
import { formatCurrency } from '../../utils/formatters';
import WalletCard from './WalletCard';
import AnnouncementBanner from './AnnouncementBanner';
import Card from '../common/Card';
import Button from '../common/Button';
import { FiUser, FiChevronRight } from 'react-icons/fi';
import { FaArrowUp, FaArrowDown, FaMoneyBillWave } from 'react-icons/fa6';

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
  const [analyticsLoading, setAnalyticsLoading] = useState(false);
  const [analyticsRows, setAnalyticsRows] = useState([]);
  const [analyticsGateways, setAnalyticsGateways] = useState([]);
  const [analyticsTotals, setAnalyticsTotals] = useState({
    payin_sales: '0',
    payin_charges: '0',
    platform_profit: '0',
    transactions_count: 0,
  });
  const [analyticsFilters, setAnalyticsFilters] = useState({
    interval: 'daily',
    dateFrom: '',
    dateTo: '',
    gateway: '',
  });

  const quickActions = useMemo(() => {
    const base = [
      {
        id: 'load-money',
        title: 'Load Money',
        description: 'Add funds to wallet',
        icon: FaArrowUp,
        color: 'blue',
        gradient: 'from-blue-500 to-indigo-600',
        onClick: () => navigate('/fund-management/load-money'),
      },
      {
        id: 'payout',
        title: 'Payout',
        description: 'Withdraw funds',
        icon: FaArrowDown,
        color: 'blue',
        gradient: 'from-blue-500 to-indigo-600',
        onClick: () => navigate('/fund-management/payout'),
      },
      {
        id: 'pay-bills',
        title: 'Pay Bills',
        description: 'BBPS bill payments',
        icon: FaMoneyBillWave,
        color: 'blue',
        gradient: 'from-blue-500 to-indigo-600',
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
          color: 'blue',
          gradient: 'from-blue-500 to-indigo-600',
          onClick: () => navigate('/reports/payin'),
        },
        {
          id: 'commission-report',
          title: 'Commission',
          description: 'Commission wallet activity',
          icon: FaArrowDown,
          color: 'blue',
          gradient: 'from-blue-500 to-indigo-600',
          onClick: () => navigate('/reports/commission'),
        },
      ];
    }
    return base;
  }, [txBlocked, navigate]);

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
      if (res.success) {
        setAnalyticsRows(res.data?.rows || []);
        setAnalyticsGateways(res.data?.available_gateways || []);
        setAnalyticsTotals(res.data?.totals || analyticsTotals);
      } else {
        setAnalyticsRows([]);
        setAnalyticsGateways([]);
      }
      setAnalyticsLoading(false);
    };
    loadAnalytics();
    return () => {
      mounted = false;
    };
  }, [analyticsFilters]);

  return (
    <>
      <AnnouncementBanner />
      {loading ? (
        <div className="flex items-center justify-center min-h-[400px]">
          <div className="text-center">
            <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto"></div>
            <p className="mt-4 text-gray-600">Loading dashboard...</p>
          </div>
        </div>
      ) : (
        <div className="space-y-8">
      {/* Welcome Section */}
      <Card
        className="border-t-4 border-t-blue-600"
        padding="lg"
      >
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-3xl font-bold text-gray-900 mb-2">
              Welcome back, {user?.name || 'there'}!
            </h1>
            <div className="flex items-center space-x-4 text-sm text-gray-600">
              <div className="flex items-center space-x-2">
                <FiUser className="text-gray-400" size={16} />
                <span>
                  User ID:{' '}
                  <span className="font-semibold text-gray-900">
                    {user?.userId || user?.user_id || '—'}
                  </span>
                </span>
              </div>
              <span className="text-gray-300">|</span>
              <div>
                Role: <span className="font-semibold text-gray-900">{user?.role}</span>
              </div>
            </div>
          </div>
        </div>
      </Card>

      {/* Wallet Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 sm:gap-6">
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

      {/* Quick Actions */}
      <Card
        title="Quick Actions"
        subtitle="Access frequently used features"
        padding="lg"
      >
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3 sm:gap-4">
          {quickActions.map((action) => {
            const Icon = action.icon;
            const colorConfig = {
              blue: {
                bg: 'bg-blue-50',
                border: 'border-blue-200',
                hover: 'hover:bg-blue-100',
                icon: 'text-blue-600',
              },
            };

            const colors = colorConfig.blue;

            return (
              <button
                key={action.id}
                onClick={action.onClick}
                className={`
                  group relative overflow-hidden
                  flex items-center space-x-4
                  p-5 rounded-2xl border-2
                  transition-all duration-300
                  hover:shadow-xl hover:scale-[1.02] hover:-translate-y-1
                  ${colors.bg} ${colors.border} ${colors.hover}
                `}
              >
                <div className={`flex-shrink-0 p-4 rounded-2xl bg-gradient-to-br ${action.gradient} shadow-lg transform group-hover:scale-110 transition-transform`}>
                  <Icon size={26} className="text-white" />
                </div>
                <div className="flex-1 text-left">
                  <p className="font-bold text-gray-900 mb-1 text-lg">{action.title}</p>
                  <p className="text-sm text-gray-600">{action.description}</p>
                </div>
                <FiChevronRight 
                  className="text-gray-400 group-hover:text-gray-700 group-hover:translate-x-2 transition-all" 
                  size={22}
                />
              </button>
            );
          })}
        </div>
      </Card>

      <Card title="Gateway Sales & Profit" subtitle="Daily/Monthly profitability by payment gateway" padding="lg">
        <div className="mb-4 grid grid-cols-1 gap-3 md:grid-cols-5">
          <select
            value={analyticsFilters.interval}
            onChange={(e) => setAnalyticsFilters((f) => ({ ...f, interval: e.target.value }))}
            className="rounded-lg border border-gray-300 px-3 py-2 text-sm"
          >
            <option value="daily">Daily</option>
            <option value="monthly">Monthly</option>
          </select>
          <input
            type="date"
            value={analyticsFilters.dateFrom}
            onChange={(e) => setAnalyticsFilters((f) => ({ ...f, dateFrom: e.target.value }))}
            className="rounded-lg border border-gray-300 px-3 py-2 text-sm"
          />
          <input
            type="date"
            value={analyticsFilters.dateTo}
            onChange={(e) => setAnalyticsFilters((f) => ({ ...f, dateTo: e.target.value }))}
            className="rounded-lg border border-gray-300 px-3 py-2 text-sm"
          />
          <select
            value={analyticsFilters.gateway}
            onChange={(e) => setAnalyticsFilters((f) => ({ ...f, gateway: e.target.value }))}
            className="rounded-lg border border-gray-300 px-3 py-2 text-sm"
          >
            <option value="">All gateways</option>
            {analyticsGateways.map((g) => (
              <option key={g} value={g}>
                {g}
              </option>
            ))}
          </select>
          <div className="rounded-lg border border-blue-200 bg-blue-50 px-3 py-2 text-sm">
            <p className="font-semibold text-blue-900">
              Total Profit: {formatCurrency(parseFloat(analyticsTotals.platform_profit || 0))}
            </p>
          </div>
        </div>

        {analyticsLoading ? (
          <div className="py-10 text-center text-gray-600">Loading analytics...</div>
        ) : analyticsRows.length === 0 ? (
          <div className="py-10 text-center text-gray-500">No analytics rows for selected filters.</div>
        ) : (
          <div className="overflow-x-auto">
            <table className="min-w-full border-collapse">
              <thead>
                <tr className="border-b border-gray-200 bg-gray-50">
                  <th className="px-3 py-2 text-left text-xs font-semibold uppercase text-gray-600">Period</th>
                  <th className="px-3 py-2 text-left text-xs font-semibold uppercase text-gray-600">Gateway</th>
                  <th className="px-3 py-2 text-right text-xs font-semibold uppercase text-gray-600">Sales</th>
                  <th className="px-3 py-2 text-right text-xs font-semibold uppercase text-gray-600">Charges</th>
                  <th className="px-3 py-2 text-right text-xs font-semibold uppercase text-gray-600">Profit</th>
                  <th className="px-3 py-2 text-right text-xs font-semibold uppercase text-gray-600">Count</th>
                </tr>
              </thead>
              <tbody>
                {analyticsRows.map((r, i) => (
                  <tr key={`${r.period}-${r.gateway}-${i}`} className="border-b border-gray-100">
                    <td className="px-3 py-2 text-sm text-gray-700">{r.period}</td>
                    <td className="px-3 py-2 text-sm text-gray-700">{r.gateway}</td>
                    <td className="px-3 py-2 text-right text-sm text-gray-900">
                      {formatCurrency(parseFloat(r.payin_sales || 0))}
                    </td>
                    <td className="px-3 py-2 text-right text-sm text-amber-800">
                      {formatCurrency(parseFloat(r.payin_charges || 0))}
                    </td>
                    <td className="px-3 py-2 text-right text-sm font-semibold text-green-700">
                      {formatCurrency(parseFloat(r.platform_profit || 0))}
                    </td>
                    <td className="px-3 py-2 text-right text-sm text-gray-700">{r.transactions_count || 0}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>
        </div>
      )}
    </>
  );
};

export default Dashboard;
