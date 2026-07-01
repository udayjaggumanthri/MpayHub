// Role-based menu configuration

export const roleMenus = {
  Admin: [
    {
      name: 'Dashboard',
      path: '/dashboard',
      icon: 'dashboard',
    },
    {
      name: 'User Management',
      path: '/user-management',
      icon: 'users',
      submenu: [
        { name: 'Users', path: '/user-management/users' },
        { name: 'Contacts', path: '/user-management/contacts' },
        { name: 'Bank Accounts', path: '/user-management/bank-accounts' },
      ],
    },
    {
      name: 'Reports',
      path: '/reports',
      icon: 'reports',
      submenu: [
        { name: 'Pay In', path: '/reports/payin' },
        { name: 'Pay Out', path: '/reports/payout' },
        { name: 'BBPS', path: '/reports/bbps' },
        { name: 'Passbook', path: '/reports/passbook' },
      ],
    },
    {
      name: 'Profile & Settings',
      path: '/profile',
      icon: 'profile',
    },
    {
      name: 'Announcements',
      path: '/admin/announcements',
      icon: 'profile',
    },
    {
      name: 'Maintenance mode',
      path: '/admin/maintenance',
      icon: 'profile',
    },
    {
      name: 'Gateways & pay-in',
      path: '/admin/gateways',
      icon: 'profile',
      submenu: [
        { name: 'API Master', path: '/admin/api-master' },
        { name: 'Payment gateways', path: '/admin/gateways' },
        { name: 'Pay-in packages', path: '/admin/pay-in-packages' },
        { name: 'SMTP settings', path: '/admin/smtp-settings' },
        { name: 'Email notifications', path: '/admin/email-notifications' },
        { name: 'SMS settings', path: '/admin/sms-settings' },
      ],
    },
    {
      name: 'BBPS Configuration',
      path: '/admin/billavenue-settings',
      icon: 'profile',
      submenu: [
        { name: 'BillAvenue Settings', path: '/admin/billavenue-settings' },
        { name: 'Provider Governance', path: '/admin/bbps-governance' },
        { name: 'BBPS Ops Console', path: '/admin/bbps-ops' },
      ],
    },
  ],
  'Super Distributor': [
    {
      name: 'Dashboard',
      path: '/dashboard',
      icon: 'dashboard',
    },
    {
      name: 'Bill Payment',
      path: '/bill-payments',
      icon: 'bbps-mnemonic',
      submenu: [
        { name: 'Pay Bill', path: '/bill-payments/pay' },
        { name: 'Complaints', path: '/bill-payments/complaints' },
        { name: 'Fund wallet', path: '/bill-payments/fund-wallet' },
        { name: 'My Bills', path: '/bill-payments/my-bills' },
      ],
    },
    {
      name: 'User Management',
      path: '/user-management',
      icon: 'users',
      submenu: [
        { name: 'Users', path: '/user-management/users' },
        { name: 'Contacts', path: '/user-management/contacts' },
        { name: 'Bank Accounts', path: '/user-management/bank-accounts' },
      ],
    },
    {
      name: 'Reports',
      path: '/reports',
      icon: 'reports',
      submenu: [
        { name: 'Pay In', path: '/reports/payin' },
        { name: 'Pay Out', path: '/reports/payout' },
        { name: 'BBPS', path: '/reports/bbps' },
        { name: 'Passbook', path: '/reports/passbook' },
        { name: 'Commission', path: '/reports/commission' },
      ],
    },
    {
      name: 'Profile & Settings',
      path: '/profile',
      icon: 'profile',
    },
  ],
  'Master Distributor': [
    {
      name: 'Dashboard',
      path: '/dashboard',
      icon: 'dashboard',
    },
    {
      name: 'Bill Payment',
      path: '/bill-payments',
      icon: 'bbps-mnemonic',
      submenu: [
        { name: 'Pay Bill', path: '/bill-payments/pay' },
        { name: 'Complaints', path: '/bill-payments/complaints' },
        { name: 'Fund wallet', path: '/bill-payments/fund-wallet' },
        { name: 'My Bills', path: '/bill-payments/my-bills' },
      ],
    },
    {
      name: 'User Management',
      path: '/user-management',
      icon: 'users',
      submenu: [
        { name: 'Users', path: '/user-management/users' },
        { name: 'Contacts', path: '/user-management/contacts' },
        { name: 'Bank Accounts', path: '/user-management/bank-accounts' },
      ],
    },
    {
      name: 'Reports',
      path: '/reports',
      icon: 'reports',
    },
    {
      name: 'Profile & Settings',
      path: '/profile',
      icon: 'profile',
    },
  ],
  Distributor: [
    {
      name: 'Dashboard',
      path: '/dashboard',
      icon: 'dashboard',
    },
    {
      name: 'Bill Payment',
      path: '/bill-payments',
      icon: 'bbps-mnemonic',
      submenu: [
        { name: 'Pay Bill', path: '/bill-payments/pay' },
        { name: 'Complaints', path: '/bill-payments/complaints' },
        { name: 'Fund wallet', path: '/bill-payments/fund-wallet' },
        { name: 'My Bills', path: '/bill-payments/my-bills' },
      ],
    },
    {
      name: 'User Management',
      path: '/user-management',
      icon: 'users',
      submenu: [
        { name: 'Users', path: '/user-management/users' },
        { name: 'Contacts', path: '/user-management/contacts' },
        { name: 'Bank Accounts', path: '/user-management/bank-accounts' },
      ],
    },
    {
      name: 'Reports',
      path: '/reports',
      icon: 'reports',
    },
    {
      name: 'Profile & Settings',
      path: '/profile',
      icon: 'profile',
    },
  ],
  Retailer: [
    {
      name: 'Dashboard',
      path: '/dashboard',
      icon: 'dashboard',
    },
    {
      name: 'Bill Payment',
      path: '/bill-payments',
      icon: 'bbps-mnemonic',
      submenu: [
        { name: 'Pay Bill', path: '/bill-payments/pay' },
        { name: 'Complaints', path: '/bill-payments/complaints' },
        { name: 'Fund wallet', path: '/bill-payments/fund-wallet' },
        { name: 'My Bills', path: '/bill-payments/my-bills' },
      ],
    },
    {
      name: 'User Management',
      path: '/user-management',
      icon: 'users',
      submenu: [
        { name: 'Contacts', path: '/user-management/contacts' },
        { name: 'Bank Accounts', path: '/user-management/bank-accounts' },
      ],
    },
    {
      name: 'Reports',
      path: '/reports',
      icon: 'reports',
    },
    {
      name: 'Profile & Settings',
      path: '/profile',
      icon: 'profile',
    },
  ],
};

// Get menu for a role
export const getMenuForRole = (role) => {
  return roleMenus[role] || roleMenus.Retailer;
};

/**
 * Mirror of backend ``apps/users/hierarchy_policy.py`` — keep in sync when changing onboarding rules.
 */
export const HIERARCHY_ROLE_ORDER = [
  'Admin',
  'Super Distributor',
  'Master Distributor',
  'Distributor',
  'Retailer',
];

export const CREATABLE_CHILD_ROLES = {
  Admin: ['Super Distributor', 'Master Distributor', 'Distributor', 'Retailer'],
  'Super Distributor': ['Master Distributor', 'Distributor', 'Retailer'],
  'Master Distributor': ['Distributor', 'Retailer'],
  Distributor: ['Retailer'],
  Retailer: [],
};

export const creatableRolesFor = (currentUserRole) => {
  const allowed = new Set(CREATABLE_CHILD_ROLES[currentUserRole] || []);
  return HIERARCHY_ROLE_ORDER.filter((role) => allowed.has(role));
};

// Check if user can create a specific role
export const canCreateRole = (currentUserRole, targetRole) => {
  return (CREATABLE_CHILD_ROLES[currentUserRole] || []).includes(targetRole);
};

// Check if user can view commission wallet
export const canViewCommissionWallet = (role) => {
  return [
    'Admin',
    'Super Distributor',
    'Master Distributor',
    'Distributor',
  ].includes(role);
};

/**
 * Platform roles blocked from personal pay-in, pay-out, and BBPS (mirrors backend FINANCIAL_TX_BLOCKED_ROLES).
 */
export const OPERATIONAL_FINANCE_BLOCKED_ROLES = ['Admin'];

/** True when role cannot use load-money, payout, or BBPS operational routes. */
export const isOperationalFundBlockedRole = (role) =>
  OPERATIONAL_FINANCE_BLOCKED_ROLES.includes(role);

/** Alias used by dashboard quick actions — same policy as operational fund block. */
export const isFinancialTxBlockedRole = (role) => isOperationalFundBlockedRole(role);

/** Admin UI: hide retailer/distributor-style money movement; show admin tools instead. */
export const isAdminOperationalIsolationRole = (role) => role === 'Admin';

/** Roles that may request downline-scoped reports (scope=team). */
export const canUseTeamReportScope = (role) =>
  ['Admin', 'Super Distributor', 'Master Distributor', 'Distributor'].includes(role);

/** Platform admin (e.g. pay-in commission / fee-split visibility in reports). */
export const isAdminUser = (user) => (user?.role || '') === 'Admin';

export { isPayInOnlySession, userMayLogin } from './userAccess';
