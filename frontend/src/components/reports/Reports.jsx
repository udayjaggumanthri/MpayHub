import React, { useEffect, useMemo, useState } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { useAuth } from '../../context/AuthContext';
import { canViewCommissionWallet } from '../../utils/rolePermissions';
import TransactionReport from './TransactionReport';
import CommissionReport from './CommissionReport';
import Passbook from './Passbook';

const pathToTab = {
  '/reports/payin': 'payin',
  '/reports/payout': 'payout',
  '/reports/bbps': 'bbps',
  '/reports/passbook': 'passbook',
  '/reports/commission': 'commission',
};

const tabToPath = {
  payin: '/reports/payin',
  payout: '/reports/payout',
  bbps: '/reports/bbps',
  passbook: '/reports/passbook',
  commission: '/reports/commission',
};

const Reports = () => {
  const { user } = useAuth();
  const location = useLocation();
  const navigate = useNavigate();
  const showCommission = canViewCommissionWallet(user?.role);

  const routeTab = useMemo(() => {
    const t = pathToTab[location.pathname];
    if (t === 'commission' && !showCommission) return 'payin';
    return t || 'payin';
  }, [location.pathname, showCommission]);

  const [activeTab, setActiveTab] = useState(routeTab);

  useEffect(() => {
    setActiveTab(routeTab);
  }, [routeTab]);

  useEffect(() => {
    if (location.pathname === '/reports') {
      navigate('/reports/payin', { replace: true });
    }
  }, [location.pathname, navigate]);

  const tabs = [
    { id: 'payin', name: 'Pay In', component: () => <TransactionReport type="payin" /> },
    { id: 'payout', name: 'Pay Out', component: () => <TransactionReport type="payout" /> },
    { id: 'bbps', name: 'BBPS', component: () => <TransactionReport type="bbps" /> },
    { id: 'passbook', name: 'Passbook', component: () => <Passbook /> },
    ...(showCommission
      ? [{ id: 'commission', name: 'Commission', component: () => <CommissionReport /> }]
      : []),
  ];

  const selectTab = (id) => {
    const path = tabToPath[id];
    if (path) navigate(path);
  };

  return (
    <div className="space-y-6">
      <div className="bg-white rounded-xl shadow-sm border border-gray-200">
        <div className="border-b border-gray-200">
          <nav className="flex flex-wrap -mb-px px-6">
            {tabs.map((tab) => (
              <button
                key={tab.id}
                type="button"
                onClick={() => selectTab(tab.id)}
                className={`px-6 py-4 text-sm font-medium border-b-2 transition-colors ${
                  activeTab === tab.id
                    ? 'border-blue-600 text-blue-600'
                    : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
                }`}
              >
                {tab.name}
              </button>
            ))}
          </nav>
        </div>

        <div className="p-6">{tabs.find((tab) => tab.id === activeTab)?.component()}</div>
      </div>
    </div>
  );
};

export default Reports;
