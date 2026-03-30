import React from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../../context/AuthContext';
import { useWallet } from '../../context/WalletContext';
import { canViewCommissionWallet } from '../../utils/rolePermissions';
import WalletCard from './WalletCard';
import AnnouncementBanner from './AnnouncementBanner';
import Card from '../common/Card';
import Button from '../common/Button';
import { FiUser, FiChevronRight } from 'react-icons/fi';
import { FaArrowUp, FaArrowDown, FaMoneyBillWave } from 'react-icons/fa6';

const Dashboard = () => {
  const { user } = useAuth();
  const { wallets, loading } = useWallet();
  const navigate = useNavigate();

  const showCommissionWallet = canViewCommissionWallet(user?.role);

  const quickActions = [
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
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4 sm:gap-6">
        <WalletCard
          type="main"
          amount={wallets.main}
          onClick={() => navigate('/fund-management/load-money')}
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
          onClick={() => navigate('/bill-payments')}
        />
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
        </div>
      )}
    </>
  );
};

export default Dashboard;
