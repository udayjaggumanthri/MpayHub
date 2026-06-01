import React, { useEffect, useMemo, useState } from 'react';
import { Link, useLocation, useNavigate, useSearchParams } from 'react-router-dom';
import { useAuth } from '../../context/AuthContext';
import { canViewCommissionWallet } from '../../utils/rolePermissions';
import {
  buildModuleReportDrillDownUrl,
  parseDrillDownSearchParams,
} from '../../utils/dashboardDrillDown';
import TransactionReport from './TransactionReport';
import BbpsBillsReport from './BbpsBillsReport';
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

const DRILLDOWN_HUB_MODULES = [
  { id: 'payin', name: 'Pay In', description: 'Load money / pay-in ledger' },
  { id: 'payout', name: 'Pay Out', description: 'Payout transfers' },
  { id: 'bbps', name: 'BBPS', description: 'Bill payments' },
];

function DashboardDrillDownHub({ drillDown }) {
  const { filters } = drillDown;
  const statusLabel =
    filters.status === 'FAILURE'
      ? 'Failed'
      : filters.status === 'ALL'
        ? 'All statuses'
        : filters.status.charAt(0) + filters.status.slice(1).toLowerCase();
  const period =
    filters.dateFrom && filters.dateTo && filters.dateFrom === filters.dateTo
      ? filters.dateFrom
      : [filters.dateFrom, filters.dateTo].filter(Boolean).join(' – ');

  return (
    <div className="mb-6 rounded-xl border border-blue-200 bg-blue-50/80 p-4 sm:p-5">
      <h3 className="text-sm font-semibold text-slate-900">Dashboard drill-down</h3>
      <p className="mt-1 text-sm text-slate-600">
        {statusLabel}
        {period ? ` · ${period}` : ''} — choose a module to view matching transactions.
      </p>
      <div className="mt-4 grid grid-cols-1 gap-3 sm:grid-cols-3">
        {DRILLDOWN_HUB_MODULES.map((mod) => (
          <Link
            key={mod.id}
            to={buildModuleReportDrillDownUrl({
              module: mod.id,
              status: filters.status === 'ALL' ? '' : filters.status,
              dateFrom: filters.dateFrom,
              dateTo: filters.dateTo,
            })}
            className="block rounded-lg border border-white bg-white px-4 py-3 shadow-sm transition hover:border-blue-300 hover:shadow-md focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-500"
          >
            <span className="font-semibold text-slate-900">{mod.name}</span>
            <span className="mt-1 block text-xs text-slate-500">{mod.description}</span>
          </Link>
        ))}
      </div>
    </div>
  );
}

const Reports = () => {
  const { user } = useAuth();
  const location = useLocation();
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const drillDown = useMemo(() => parseDrillDownSearchParams(searchParams), [searchParams]);
  const showDrillDownHub = drillDown.fromDashboard && drillDown.moduleAll;
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
    { id: 'bbps', name: 'BBPS', component: () => <BbpsBillsReport /> },
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

        <div className="p-6">
          {showDrillDownHub ? (
            <DashboardDrillDownHub drillDown={drillDown} />
          ) : (
            tabs.find((tab) => tab.id === activeTab)?.component()
          )}
        </div>
      </div>
    </div>
  );
};

export default Reports;
