import React from 'react';
import { Routes, Route, Navigate, useParams } from 'react-router-dom';
import ProtectedRoute from '../components/common/ProtectedRoute';
import AdminRoute from '../components/common/AdminRoute';
import Layout from '../components/common/Layout';

// Auth components
import Login from '../components/auth/Login';
import MPINVerification from '../components/auth/MPINVerification';
import ForgotPassword from '../components/auth/ForgotPassword';
import ForgotMPIN from '../components/auth/ForgotMPIN';

// Dashboard
import Dashboard from '../components/dashboard/Dashboard';

// Fund Management
import LoadMoney from '../components/fundManagement/LoadMoney';
import Payout from '../components/fundManagement/Payout';

// BBPS
import BillPayment from '../components/bbps/BillPayment';
import MyBills from '../components/bbps/MyBills';
import BbpsWalletFund from '../components/bbps/BbpsWalletFund';
import BbpsTransactionQuery from '../components/bbps/BbpsTransactionQuery';
import BbpsComplaintsModule from '../components/bbps/complaints/BbpsComplaintsModule';
import ComplaintsHub from '../components/bbps/complaints/ComplaintsHub';
import ComplaintsRegister from '../components/bbps/complaints/ComplaintsRegister';
import ComplaintsTrack from '../components/bbps/complaints/ComplaintsTrack';
import ComplaintHistoryPanel from '../components/bbps/complaints/ComplaintHistoryPanel';

// Reports
import Reports from '../components/reports/Reports';

// User Management
import UserManagement from '../components/userManagement/UserManagement';
import UserDetail from '../components/userManagement/UserDetail';
import Contacts from '../components/contacts/Contacts';
import BankAccounts from '../components/bankManagement/BankAccounts';

// Profile
import ProfileSettings from '../components/profile/ProfileSettings';
import LoginActivityPage from '../components/profile/LoginActivityPage';
import AuditLogsPage from '../components/profile/AuditLogsPage';
import OnboardingKYC from '../components/onboarding/OnboardingKYC';
import OnboardingDigilockerCallback from '../components/onboarding/OnboardingDigilockerCallback';
import OnboardingMPINSetup from '../components/onboarding/OnboardingMPINSetup';
import SetPasswordOnboarding from '../components/onboarding/SetPasswordOnboarding';

// Admin
import AnnouncementManagement from '../components/admin/AnnouncementManagement';
import PaymentGatewaysAdmin from '../components/admin/PaymentGatewaysAdmin';
import PayInPackagesAdmin from '../components/admin/PayInPackagesAdmin';
import APIMasterManagement from '../components/admin/APIMasterManagement';
import BillAvenueSettings from '../components/admin/BillAvenueSettings';
import SmtpSettings from '../components/admin/SmtpSettings';
import EmailNotifications from '../components/admin/EmailNotifications';
import SmsSettings from '../components/admin/SmsSettings';
import BbpsOpsConsole from '../components/admin/BbpsOpsConsole';
import BbpsBillerDetails from '../components/admin/BbpsBillerDetails';
import BbpsProviderGovernance from '../components/admin/BbpsProviderGovernance';
import MaintenanceMode from '../components/admin/MaintenanceMode';
import UserManagementSettings from '../components/admin/UserManagementSettings';
import WalletHistoryPage from '../components/wallets/WalletHistoryPage';
import AepsLayout from '../modules/aeps/pages/AepsLayout';
import AepsOverview from '../modules/aeps/pages/AepsOverview';
import AepsSetup from '../modules/aeps/pages/AepsSetup';
import AepsDevice from '../modules/aeps/pages/AepsDevice';
import AepsHistory from '../modules/aeps/pages/AepsHistory';
import AepsReports from '../modules/aeps/pages/AepsReports';
import {
  AepsWithdraw,
  AepsBalance,
  AepsMiniStatement,
  AepsAadhaarPay,
  AepsDeposit,
} from '../modules/aeps/pages/AepsProductPages';
import {
  AepsAdminProvider,
  AepsAdminRequests,
  AepsAdminMerchants,
  AepsAdminRecon,
} from '../modules/aeps/admin/AepsAdminPages';

/** Old URL `/admin/users/:id` → canonical user profile (all roles that may view a profile). */
function LegacyAdminUserDetailRedirect() {
  const { userId } = useParams();
  return <Navigate to={`/user-management/users/${userId}`} replace />;
}

const AppRoutes = () => {
  return (
    <Routes>
      {/* Public Routes */}
      <Route path="/login" element={<Login />} />
      <Route path="/forgot-password" element={<ForgotPassword />} />
      <Route path="/forgot-mpin" element={<ForgotMPIN />} />
      <Route path="/mpin-verification" element={<MPINVerification />} />

      <Route
        path="/onboarding/set-password"
        element={
          <ProtectedRoute requireMPIN={false}>
            <Layout>
              <SetPasswordOnboarding />
            </Layout>
          </ProtectedRoute>
        }
      />
      <Route
        path="/onboarding/kyc"
        element={
          <ProtectedRoute requireMPIN={false}>
            <Layout>
              <OnboardingKYC />
            </Layout>
          </ProtectedRoute>
        }
      />
      <Route
        path="/onboarding/kyc/digilocker/callback"
        element={
          <ProtectedRoute requireMPIN={false}>
            <Layout>
              <OnboardingDigilockerCallback />
            </Layout>
          </ProtectedRoute>
        }
      />
      <Route
        path="/onboarding/mpin-setup"
        element={
          <ProtectedRoute requireMPIN={false}>
            <Layout>
              <OnboardingMPINSetup />
            </Layout>
          </ProtectedRoute>
        }
      />

      {/* Protected Routes */}
      <Route
        path="/"
        element={
          <ProtectedRoute>
            <Layout>
              <Navigate to="/dashboard" replace />
            </Layout>
          </ProtectedRoute>
        }
      />

      <Route
        path="/dashboard"
        element={
          <ProtectedRoute>
            <Layout>
              <Dashboard />
            </Layout>
          </ProtectedRoute>
        }
      />

      {/* Fund Management */}
      <Route
        path="/fund-management/load-money"
        element={
          <ProtectedRoute blockFinancialTransactions>
            <Layout>
              <LoadMoney />
            </Layout>
          </ProtectedRoute>
        }
      />

      <Route
        path="/fund-management/payout"
        element={
          <ProtectedRoute blockFinancialTransactions>
            <Layout>
              <Payout />
            </Layout>
          </ProtectedRoute>
        }
      />

      {/* Bill Payments */}
      <Route
        path="/bill-payments"
        element={
          <ProtectedRoute blockFinancialTransactions>
            <Layout>
              <BillPayment />
            </Layout>
          </ProtectedRoute>
        }
      />

      <Route
        path="/bill-payments/pay"
        element={
          <ProtectedRoute blockFinancialTransactions>
            <Layout>
              <BillPayment />
            </Layout>
          </ProtectedRoute>
        }
      />

      <Route
        path="/bill-payments/pay/:category"
        element={
          <ProtectedRoute blockFinancialTransactions>
            <Layout>
              <BillPayment />
            </Layout>
          </ProtectedRoute>
        }
      />

      <Route
        path="/bill-payments/my-bills"
        element={
          <ProtectedRoute blockFinancialTransactions>
            <Layout>
              <MyBills />
            </Layout>
          </ProtectedRoute>
        }
      />
      <Route
        path="/bill-payments/complaints"
        element={
          <ProtectedRoute blockFinancialTransactions>
            <Layout>
              <BbpsComplaintsModule />
            </Layout>
          </ProtectedRoute>
        }
      >
        <Route index element={<ComplaintsHub />} />
        <Route path="register" element={<ComplaintsRegister />} />
        <Route path="track" element={<ComplaintsTrack />} />
        <Route path="search-transaction" element={<BbpsTransactionQuery variant="complaints" />} />
        <Route path="history" element={<ComplaintHistoryPanel />} />
      </Route>

      <Route
        path="/bill-payments/fund-wallet"
        element={
          <ProtectedRoute blockFinancialTransactions>
            <Layout>
              <BbpsWalletFund />
            </Layout>
          </ProtectedRoute>
        }
      />

      {/* User Management */}
      <Route
        path="/user-management"
        element={
          <ProtectedRoute>
            <Layout>
              <Navigate to="/user-management/users" replace />
            </Layout>
          </ProtectedRoute>
        }
      />

      <Route
        path="/user-management/users"
        element={
          <ProtectedRoute>
            <Layout>
              <UserManagement />
            </Layout>
          </ProtectedRoute>
        }
      />

      <Route
        path="/user-management/users/:userId"
        element={
          <ProtectedRoute>
            <Layout>
              <UserDetail />
            </Layout>
          </ProtectedRoute>
        }
      />

      <Route
        path="/admin/users/:userId"
        element={
          <ProtectedRoute>
            <LegacyAdminUserDetailRedirect />
          </ProtectedRoute>
        }
      />

      <Route
        path="/user-management/contacts"
        element={
          <ProtectedRoute>
            <Layout>
              <Contacts />
            </Layout>
          </ProtectedRoute>
        }
      />

      <Route
        path="/user-management/bank-accounts"
        element={
          <ProtectedRoute>
            <Layout>
              <BankAccounts />
            </Layout>
          </ProtectedRoute>
        }
      />

      {/* Reports */}
      <Route
        path="/reports"
        element={
          <ProtectedRoute>
            <Layout>
              <Navigate to="/reports/payin" replace />
            </Layout>
          </ProtectedRoute>
        }
      />

      <Route
        path="/reports/payin"
        element={
          <ProtectedRoute>
            <Layout>
              <Reports />
            </Layout>
          </ProtectedRoute>
        }
      />

      <Route
        path="/reports/payout"
        element={
          <ProtectedRoute>
            <Layout>
              <Reports />
            </Layout>
          </ProtectedRoute>
        }
      />

      <Route
        path="/reports/bbps"
        element={
          <ProtectedRoute>
            <Layout>
              <Reports />
            </Layout>
          </ProtectedRoute>
        }
      />

      <Route
        path="/reports/passbook"
        element={
          <ProtectedRoute>
            <Layout>
              <Reports />
            </Layout>
          </ProtectedRoute>
        }
      />

      <Route
        path="/reports/commission"
        element={
          <ProtectedRoute>
            <Layout>
              <Reports />
            </Layout>
          </ProtectedRoute>
        }
      />

      <Route
        path="/wallets/:walletType-history"
        element={
          <ProtectedRoute>
            <Layout>
              <WalletHistoryPage />
            </Layout>
          </ProtectedRoute>
        }
      />
      <Route
        path="/wallets/:walletType"
        element={
          <ProtectedRoute>
            <Layout>
              <WalletHistoryPage />
            </Layout>
          </ProtectedRoute>
        }
      />

      {/* Profile & Settings */}
      <Route
        path="/profile"
        element={
          <ProtectedRoute>
            <Layout>
              <ProfileSettings />
            </Layout>
          </ProtectedRoute>
        }
      />
      <Route
        path="/profile/login-activity"
        element={
          <ProtectedRoute>
            <Layout>
              <LoginActivityPage />
            </Layout>
          </ProtectedRoute>
        }
      />
      <Route
        path="/audit-logs"
        element={
          <ProtectedRoute>
            <Layout>
              <AuditLogsPage />
            </Layout>
          </ProtectedRoute>
        }
      />

      {/* Admin - Announcement Management */}
      <Route
        path="/admin/announcements"
        element={
          <ProtectedRoute>
            <AdminRoute>
              <Layout>
                <AnnouncementManagement />
              </Layout>
            </AdminRoute>
          </ProtectedRoute>
        }
      />

      {/* Admin - Maintenance mode */}
      <Route
        path="/admin/maintenance"
        element={
          <ProtectedRoute>
            <AdminRoute>
              <Layout>
                <MaintenanceMode />
              </Layout>
            </AdminRoute>
          </ProtectedRoute>
        }
      />

      {/* Admin - User management session security settings */}
      <Route
        path="/admin/user-management-settings"
        element={
          <ProtectedRoute>
            <AdminRoute>
              <Layout>
                <UserManagementSettings />
              </Layout>
            </AdminRoute>
          </ProtectedRoute>
        }
      />

      {/* Admin - Payment gateways */}
      <Route
        path="/admin/gateways"
        element={
          <ProtectedRoute>
            <AdminRoute>
              <Layout>
                <PaymentGatewaysAdmin />
              </Layout>
            </AdminRoute>
          </ProtectedRoute>
        }
      />

      {/* Admin - Pay-in packages */}
      <Route
        path="/admin/pay-in-packages"
        element={
          <ProtectedRoute>
            <AdminRoute>
              <Layout>
                <PayInPackagesAdmin />
              </Layout>
            </AdminRoute>
          </ProtectedRoute>
        }
      />

      {/* Admin - API Master */}
      <Route
        path="/admin/api-master"
        element={
          <ProtectedRoute>
            <AdminRoute>
              <Layout>
                <APIMasterManagement />
              </Layout>
            </AdminRoute>
          </ProtectedRoute>
        }
      />

      <Route
        path="/admin/billavenue-settings"
        element={
          <ProtectedRoute>
            <AdminRoute>
              <Layout>
                <BillAvenueSettings />
              </Layout>
            </AdminRoute>
          </ProtectedRoute>
        }
      />

      <Route
        path="/admin/smtp-settings/*"
        element={
          <ProtectedRoute>
            <AdminRoute>
              <Layout>
                <SmtpSettings />
              </Layout>
            </AdminRoute>
          </ProtectedRoute>
        }
      />

      <Route
        path="/admin/sms-settings/*"
        element={
          <ProtectedRoute>
            <AdminRoute>
              <Layout>
                <SmsSettings />
              </Layout>
            </AdminRoute>
          </ProtectedRoute>
        }
      />

      <Route
        path="/admin/email-notifications/*"
        element={
          <ProtectedRoute>
            <AdminRoute>
              <Layout>
                <EmailNotifications />
              </Layout>
            </AdminRoute>
          </ProtectedRoute>
        }
      />

      <Route
        path="/admin/bbps-ops"
        element={
          <ProtectedRoute>
            <AdminRoute>
              <Layout>
                <BbpsOpsConsole />
              </Layout>
            </AdminRoute>
          </ProtectedRoute>
        }
      />

      <Route
        path="/admin/bbps-governance"
        element={
          <ProtectedRoute>
            <AdminRoute>
              <Layout>
                <BbpsProviderGovernance />
              </Layout>
            </AdminRoute>
          </ProtectedRoute>
        }
      />
      <Route
        path="/admin/bbps-governance/biller/:billerPk"
        element={
          <ProtectedRoute>
            <AdminRoute>
              <Layout>
                <BbpsBillerDetails />
              </Layout>
            </AdminRoute>
          </ProtectedRoute>
        }
      />

      {/* AEPS module (independent; reports stay inside AEPS) */}
      <Route
        path="/aeps"
        element={
          <ProtectedRoute>
            <Layout>
              <AepsLayout>
                <AepsOverview />
              </AepsLayout>
            </Layout>
          </ProtectedRoute>
        }
      />
      <Route
        path="/aeps/setup"
        element={
          <ProtectedRoute>
            <Layout>
              <AepsLayout>
                <AepsSetup />
              </AepsLayout>
            </Layout>
          </ProtectedRoute>
        }
      />
      <Route
        path="/aeps/device"
        element={
          <ProtectedRoute>
            <Layout>
              <AepsLayout>
                <AepsDevice />
              </AepsLayout>
            </Layout>
          </ProtectedRoute>
        }
      />
      <Route
        path="/aeps/withdraw"
        element={
          <ProtectedRoute>
            <Layout>
              <AepsLayout>
                <AepsWithdraw />
              </AepsLayout>
            </Layout>
          </ProtectedRoute>
        }
      />
      <Route
        path="/aeps/balance"
        element={
          <ProtectedRoute>
            <Layout>
              <AepsLayout>
                <AepsBalance />
              </AepsLayout>
            </Layout>
          </ProtectedRoute>
        }
      />
      <Route
        path="/aeps/mini-statement"
        element={
          <ProtectedRoute>
            <Layout>
              <AepsLayout>
                <AepsMiniStatement />
              </AepsLayout>
            </Layout>
          </ProtectedRoute>
        }
      />
      <Route
        path="/aeps/aadhaar-pay"
        element={
          <ProtectedRoute>
            <Layout>
              <AepsLayout>
                <AepsAadhaarPay />
              </AepsLayout>
            </Layout>
          </ProtectedRoute>
        }
      />
      <Route
        path="/aeps/deposit"
        element={
          <ProtectedRoute>
            <Layout>
              <AepsLayout>
                <AepsDeposit />
              </AepsLayout>
            </Layout>
          </ProtectedRoute>
        }
      />
      <Route
        path="/aeps/history"
        element={
          <ProtectedRoute>
            <Layout>
              <AepsLayout>
                <AepsHistory />
              </AepsLayout>
            </Layout>
          </ProtectedRoute>
        }
      />
      <Route
        path="/aeps/reports"
        element={
          <ProtectedRoute>
            <Layout>
              <AepsLayout>
                <AepsReports />
              </AepsLayout>
            </Layout>
          </ProtectedRoute>
        }
      />
      <Route
        path="/admin/aeps/provider"
        element={
          <ProtectedRoute>
            <AdminRoute>
              <Layout>
                <AepsAdminProvider />
              </Layout>
            </AdminRoute>
          </ProtectedRoute>
        }
      />
      <Route
        path="/admin/aeps/requests"
        element={
          <ProtectedRoute>
            <AdminRoute>
              <Layout>
                <AepsAdminRequests />
              </Layout>
            </AdminRoute>
          </ProtectedRoute>
        }
      />
      <Route
        path="/admin/aeps/merchants"
        element={
          <ProtectedRoute>
            <AdminRoute>
              <Layout>
                <AepsAdminMerchants />
              </Layout>
            </AdminRoute>
          </ProtectedRoute>
        }
      />
      <Route
        path="/admin/aeps/recon"
        element={
          <ProtectedRoute>
            <AdminRoute>
              <Layout>
                <AepsAdminRecon />
              </Layout>
            </AdminRoute>
          </ProtectedRoute>
        }
      />

      {/* 404 - Redirect to dashboard */}
      <Route path="*" element={<Navigate to="/dashboard" replace />} />
    </Routes>
  );
};

export default AppRoutes;
