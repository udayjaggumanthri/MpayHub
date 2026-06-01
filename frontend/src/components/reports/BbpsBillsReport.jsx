import React from 'react';
import { useAuth } from '../../context/AuthContext';
import { isAdminUser } from '../../utils/rolePermissions';
import BbpsBillsList from '../bbps/BbpsBillsList';

/**
 * Reports → BBPS tab: same UI as Bill Payment → My Bills, with optional platform scope for Admin.
 */
const BbpsBillsReport = () => {
  const { user } = useAuth();
  const admin = isAdminUser(user);

  return (
    <BbpsBillsList
      variant="embedded"
      title="BBPS Bills"
      subtitle={
        admin
          ? 'Bill payment history across the platform — same view as My Bills with receipt download'
          : 'Your BBPS bill payment transaction history'
      }
      defaultScope={admin ? 'platform' : 'self'}
      showScopeToggle={admin}
      showCsvExport
    />
  );
};

export default BbpsBillsReport;
