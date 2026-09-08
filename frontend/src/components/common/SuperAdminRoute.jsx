import React from 'react';
import { Navigate, useLocation } from 'react-router-dom';
import { useAuth } from '../../context/AuthContext';
import { isSuperAdminUser } from '../../utils/rolePermissions';

/**
 * Restricts children to Super Admin only.
 */
const SuperAdminRoute = ({ children }) => {
  const { user, loading } = useAuth();
  const location = useLocation();

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto" />
          <p className="mt-4 text-gray-600 dark:text-slate-400">Loading...</p>
        </div>
      </div>
    );
  }

  if (!user || !isSuperAdminUser(user)) {
    return (
      <Navigate
        to="/dashboard"
        replace
        state={{ from: location.pathname, superAdminRequired: true }}
      />
    );
  }

  return children;
};

export default SuperAdminRoute;
