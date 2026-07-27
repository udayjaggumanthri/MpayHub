import React, { useMemo } from 'react';
import { Link } from 'react-router-dom';
import { useAuth } from '../../context/AuthContext';
import ActivityAuditPanel from '../userManagement/profile/ActivityAuditPanel';

/**
 * Audit logs from the header profile menu.
 * Admin only: all users. Everyone else (SD/MD/Distributor/Retailer): own account only.
 */
const AuditLogsPage = () => {
  const { user } = useAuth();
  const canViewAllUsers = useMemo(
    () => String(user?.role || '').trim() === 'Admin',
    [user?.role]
  );

  return (
    <div className="mx-auto max-w-6xl space-y-4">
      <div>
        <p className="text-xs font-semibold uppercase tracking-widest text-indigo-600">Security</p>
        <h1 className="mt-1 text-2xl font-bold tracking-tight text-slate-900">Audit logs</h1>
        <p className="mt-1 text-sm text-slate-500">
          {canViewAllUsers
            ? 'Login, money, contacts, reports, and admin events across all accounts. Filter by user, category, or date. Times are IST.'
            : 'Your own login, money, contacts, and report activity only. Other accounts are never shown. Times are IST.'}
        </p>
        {!canViewAllUsers ? (
          <Link
            to="/profile/login-activity"
            className="mt-2 inline-block text-sm font-semibold text-indigo-600 hover:text-indigo-800"
          >
            Open login activity →
          </Link>
        ) : null}
      </div>
      <ActivityAuditPanel
        mode={canViewAllUsers ? 'admin' : 'self'}
        title={canViewAllUsers ? 'All account activity' : 'My audit logs'}
        defaultCategory="all"
        showDeviceColumns
      />
    </div>
  );
};

export default AuditLogsPage;
