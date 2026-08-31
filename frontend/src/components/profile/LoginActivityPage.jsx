import React from 'react';
import { Link } from 'react-router-dom';
import { FaArrowLeft } from 'react-icons/fa6';
import ActivityAuditPanel from '../userManagement/profile/ActivityAuditPanel';

/**
 * Dedicated login / auth activity audit for the signed-in account.
 */
const LoginActivityPage = () => {
  return (
    <div className="mx-auto max-w-6xl space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <Link
            to="/profile"
            className="mb-2 inline-flex items-center gap-1.5 text-sm font-medium text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-slate-100"
          >
            <FaArrowLeft size={12} />
            Back to profile
          </Link>
          <h1 className="text-2xl font-bold tracking-tight text-slate-900 dark:text-slate-100">Login activity</h1>
          <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">
            Every sign-in, sign-out, and session event for your account — with IP, location, and device.
          </p>
        </div>
      </div>
      <ActivityAuditPanel
        mode="self"
        title="Login & session audit"
        defaultCategory="all"
        showDeviceColumns
      />
    </div>
  );
};

export default LoginActivityPage;
