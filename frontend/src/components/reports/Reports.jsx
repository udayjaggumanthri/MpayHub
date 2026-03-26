import React, { useState } from 'react';
import { useAuth } from '../../context/AuthContext';
import { canViewCommissionWallet } from '../../utils/rolePermissions';
import TransactionReport from './TransactionReport';
import CommissionReport from './CommissionReport';
import Passbook from './Passbook';

const Reports = () => {
  const { user } = useAuth();
  const [activeTab, setActiveTab] = useState('payin');

  const showCommission = canViewCommissionWallet(user?.role);

  const tabs = [
    { id: 'payin', name: 'Pay In', component: () => <TransactionReport type="payin" /> },
    { id: 'payout', name: 'Pay Out', component: () => <TransactionReport type="payout" /> },
    { id: 'bbps', name: 'BBPS', component: () => <TransactionReport type="bbps" /> },
    { id: 'passbook', name: 'Passbook', component: () => <Passbook /> },
    ...(showCommission
      ? [{ id: 'commission', name: 'Commission', component: () => <CommissionReport /> }]
      : []),
  ];

  return (
    <div className="space-y-6">
      <div className="bg-white rounded-xl shadow-sm border border-gray-200">
        {/* Tabs */}
        <div className="border-b border-gray-200">
          <nav className="flex flex-wrap -mb-px px-6">
            {tabs.map((tab) => (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id)}
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

        {/* Tab Content */}
        <div className="p-6">
          {tabs.find((tab) => tab.id === activeTab)?.component()}
        </div>
      </div>
    </div>
  );
};

export default Reports;
