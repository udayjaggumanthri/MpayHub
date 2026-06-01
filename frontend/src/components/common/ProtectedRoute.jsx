import React from 'react';
import { Navigate, useLocation } from 'react-router-dom';
import { useAuth } from '../../context/AuthContext';
import { isOperationalFundBlockedRole } from '../../utils/rolePermissions';
import {
  getBlockedActionNotice,
  shouldBlockPathForUser,
  userMayLogin,
} from '../../utils/accessControl';

const ProtectedRoute = ({ children, requireMPIN = true, blockFinancialTransactions = false }) => {
  const { isAuthenticated, mpinVerified, loading, user, maintenance } = useAuth();
  const location = useLocation();
  const path = location.pathname;

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

  if (!isAuthenticated) {
    return <Navigate to="/login" replace />;
  }

  if (user && !userMayLogin(user)) {
    return <Navigate to="/login" replace state={{ from: path, disabledAccount: true }} />;
  }

  if (user && shouldBlockPathForUser(user, path)) {
    return (
      <Navigate
        to="/dashboard"
        replace
        state={{
          accessBlocked: true,
          message: getBlockedActionNotice(user, path, maintenance),
        }}
      />
    );
  }

  const ob = user?.onboarding;
  const onOnboardingRoute = path.startsWith('/onboarding');
  const onProfileDuringOnboarding = path === '/profile';

  if (ob?.must_change_password) {
    const onSetPassword = path === '/onboarding/set-password';
    if (!onSetPassword && !onProfileDuringOnboarding) {
      return <Navigate to="/onboarding/set-password" replace />;
    }
  }

  if (ob && !ob.account_ready) {
    if (!onOnboardingRoute && !onProfileDuringOnboarding) {
      const next = !ob.kyc_complete ? '/onboarding/kyc' : '/onboarding/mpin-setup';
      return <Navigate to={next} replace />;
    }
  }

  if (ob?.account_ready && requireMPIN && !mpinVerified && path !== '/mpin-verification') {
    return <Navigate to="/mpin-verification" replace />;
  }

  if (
    blockFinancialTransactions &&
    user?.role &&
    isOperationalFundBlockedRole(user.role)
  ) {
    return <Navigate to="/dashboard" replace />;
  }

  return children;
};

export default ProtectedRoute;
