// Role-based menu configuration

export const roleMenus = {
  Admin: [
    {
      name: 'Dashboard',
      path: '/dashboard',
      icon: 'dashboard',
    },
    {
      name: 'Bill Payments',
      path: '/bill-payments',
      icon: 'bills',
      submenu: [
        { name: 'Pay Bills', path: '/bill-payments/pay' },
        { name: 'Fund BBPS wallet', path: '/bill-payments/fund-wallet' },
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
      name: 'Gateways & pay-in',
      path: '/admin/gateways',
      icon: 'profile',
      submenu: [
        { name: 'Payment gateways', path: '/admin/gateways' },
        { name: 'Pay-in packages', path: '/admin/pay-in-packages' },
      ],
    },
    {
      name: 'API Master',
      path: '/admin/api-master',
      icon: 'profile',
    },
  ],
  'Super Distributor': [
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
      name: 'Bill Payments',
      path: '/bill-payments',
      icon: 'bills',
      submenu: [
        { name: 'Pay Bills', path: '/bill-payments/pay' },
        { name: 'Fund BBPS wallet', path: '/bill-payments/fund-wallet' },
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
      name: 'Bill Payments',
      path: '/bill-payments',
      icon: 'bills',
      submenu: [
        { name: 'Pay Bills', path: '/bill-payments/pay' },
        { name: 'Fund BBPS wallet', path: '/bill-payments/fund-wallet' },
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
      name: 'Bill Payments',
      path: '/bill-payments',
      icon: 'bills',
      submenu: [
        { name: 'Pay Bills', path: '/bill-payments/pay' },
        { name: 'Fund BBPS wallet', path: '/bill-payments/fund-wallet' },
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

// Check if user can create a specific role
export const canCreateRole = (currentUserRole, targetRole) => {
  const permissions = {
    Admin: [
      'Super Distributor',
      'Master Distributor',
      'Distributor',
      'Retailer',
    ],
    'Super Distributor': ['Distributor', 'Retailer'],
    'Master Distributor': ['Distributor', 'Retailer'],
    Distributor: ['Retailer'],
    Retailer: [],
  };

  return permissions[currentUserRole]?.includes(targetRole) || false;
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

/** Roles that cannot load money, payout, pay BBPS bills, or transfer to BBPS (management-only). */
export const isFinancialTxBlockedRole = (role) => role === 'Super Distributor';

/** Roles that may request downline-scoped reports (scope=team). */
export const canUseTeamReportScope = (role) =>
  ['Admin', 'Super Distributor', 'Master Distributor', 'Distributor'].includes(role);
