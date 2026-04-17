import React from 'react';
import { Routes, Route, Navigate } from 'react-router-dom';
import ProtectedRoute from '../components/common/ProtectedRoute';
import Layout from '../components/common/Layout';

// Auth components
import Login from '../components/auth/Login';
import MPINVerification from '../components/auth/MPINVerification';
import ForgotPassword from '../components/auth/ForgotPassword';

// Dashboard
import Dashboard from '../components/dashboard/Dashboard';

// Fund Management
import LoadMoney from '../components/fundManagement/LoadMoney';
import Payout from '../components/fundManagement/Payout';

// BBPS
import BillPayment from '../components/bbps/BillPayment';
import MyBills from '../components/bbps/MyBills';
import BbpsWalletFund from '../components/bbps/BbpsWalletFund';

// Reports
import Reports from '../components/reports/Reports';

// User Management
import UserManagement from '../components/userManagement/UserManagement';
import UserDetail from '../components/userManagement/UserDetail';
import Contacts from '../components/contacts/Contacts';
import BankAccounts from '../components/bankManagement/BankAccounts';

// Profile
import ProfileSettings from '../components/profile/ProfileSettings';
import OnboardingKYC from '../components/onboarding/OnboardingKYC';
import OnboardingMPINSetup from '../components/onboarding/OnboardingMPINSetup';

// Admin
import AnnouncementManagement from '../components/admin/AnnouncementManagement';
import PaymentGatewaysAdmin from '../components/admin/PaymentGatewaysAdmin';
import PayInPackagesAdmin from '../components/admin/PayInPackagesAdmin';
import APIMasterManagement from '../components/admin/APIMasterManagement';
import WalletHistoryPage from '../components/wallets/WalletHistoryPage';

const AppRoutes = () => {
  return (
    <Routes>
      {/* Public Routes */}
      <Route path="/login" element={<Login />} />
      <Route path="/forgot-password" element={<ForgotPassword />} />
      <Route path="/mpin-verification" element={<MPINVerification />} />

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
        path="/admin/users/:userId"
        element={
          <ProtectedRoute>
            <Layout>
              <UserDetail />
            </Layout>
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

      {/* Admin - Announcement Management */}
      <Route
        path="/admin/announcements"
        element={
          <ProtectedRoute>
            <Layout>
              <AnnouncementManagement />
            </Layout>
          </ProtectedRoute>
        }
      />

      {/* Admin - Payment gateways */}
      <Route
        path="/admin/gateways"
        element={
          <ProtectedRoute>
            <Layout>
              <PaymentGatewaysAdmin />
            </Layout>
          </ProtectedRoute>
        }
      />

      {/* Admin - Pay-in packages */}
      <Route
        path="/admin/pay-in-packages"
        element={
          <ProtectedRoute>
            <Layout>
              <PayInPackagesAdmin />
            </Layout>
          </ProtectedRoute>
        }
      />

      {/* Admin - API Master */}
      <Route
        path="/admin/api-master"
        element={
          <ProtectedRoute>
            <Layout>
              <APIMasterManagement />
            </Layout>
          </ProtectedRoute>
        }
      />

      {/* 404 - Redirect to dashboard */}
      <Route path="*" element={<Navigate to="/dashboard" replace />} />
    </Routes>
  );
};

export default AppRoutes;
