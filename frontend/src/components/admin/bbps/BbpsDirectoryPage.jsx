import React from 'react';
import { Navigate, useLocation } from 'react-router-dom';
import BillerDirectory from './BillerDirectory';

const BbpsDirectoryPage = () => {
  const { pathname } = useLocation();
  const locked = pathname.endsWith('/production')
    ? 'prod'
    : pathname.endsWith('/uat')
      ? 'uat'
      : null;
  if (!locked) return <Navigate to="/admin/bbps/catalog?tab=mdm&mdmEnv=uat" replace />;
  return <BillerDirectory lockedEnvironment={locked} embedded />;
};

export default BbpsDirectoryPage;
