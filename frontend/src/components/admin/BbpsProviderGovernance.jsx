import { Navigate } from 'react-router-dom';

/** @deprecated Use /admin/bbps/sync and dedicated directory routes */
const BbpsProviderGovernance = () => <Navigate to="/admin/bbps/sync" replace />;

export default BbpsProviderGovernance;
