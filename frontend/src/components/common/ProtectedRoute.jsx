import React from 'react';
import { Navigate, useLocation } from 'react-router-dom';
import { useAuth } from '../../context/AuthContext';

const ProtectedRoute = ({ children, requireMPIN = true }) => {
  const { isAuthenticated, mpinVerified, loading, user } = useAuth();
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

  if (user && user.is_active === false) {
    return <Navigate to="/login" replace state={{ from: path, disabledAccount: true }} />;
  }

  const ob = user?.onboarding;
  const onOnboardingRoute = path.startsWith('/onboarding');
  const onProfileDuringOnboarding = path === '/profile';

  if (ob && !ob.account_ready) {
    if (!onOnboardingRoute && !onProfileDuringOnboarding) {
      const next = !ob.kyc_complete ? '/onboarding/kyc' : '/onboarding/mpin-setup';
      return <Navigate to={next} replace />;
    }
  }

  if (ob?.account_ready && requireMPIN && !mpinVerified && path !== '/mpin-verification') {
    return <Navigate to="/mpin-verification" replace />;
  }

  return children;
};

export default ProtectedRoute;
