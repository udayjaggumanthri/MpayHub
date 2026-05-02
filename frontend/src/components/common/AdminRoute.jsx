import React from 'react';
import { Navigate, useLocation } from 'react-router-dom';
import { useAuth } from '../../context/AuthContext';

/**
 * Restricts children to users with role Admin (matches backend IsAdmin).
 * Use inside ProtectedRoute so the user is authenticated first.
 */
const AdminRoute = ({ children }) => {
  const { user, loading } = useAuth();
  const location = useLocation();

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto" />
          <p className="mt-4 text-gray-600">Loading...</p>
        </div>
      </div>
    );
  }

  if (!user || user.role !== 'Admin') {
    return (
      <Navigate
        to="/dashboard"
        replace
        state={{ from: location.pathname, adminRequired: true }}
      />
    );
  }

  return children;
};

export default AdminRoute;
