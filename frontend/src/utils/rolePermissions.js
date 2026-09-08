// Role-based menu configuration

export const roleMenus = {
  'Super Admin': null, // filled below from Admin + extras
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
      name: 'Pay-in setup',
      path: '/admin/gateways',
      icon: 'payin',
      submenu: [
        { name: 'API Master', path: '/admin/api-master' },
        { name: 'Payment gateways', path: '/admin/gateways' },
        { name: 'Pay-in packages', path: '/admin/pay-in-packages' },
      ],
    },
    {
      name: 'Manual QR',
      path: '/admin/pay-in-qr-operations',
      icon: 'qr',
      submenu: [
        { name: 'Operations queue', path: '/admin/pay-in-qr-operations' },
        { name: 'Collection accounts', path: '/admin/pay-in-qr-accounts' },
      ],
    },
    {
      name: 'Wallet Adjustments',
      path: '/admin/wallet-adjustments',
      icon: 'wallet',
    },
    {
      name: 'BBPS Console',
      path: '/admin/bbps',
      icon: 'bbps-console',
      submenu: [
        { name: 'Overview', path: '/admin/bbps', exactEnd: true },
        { name: 'Catalog', path: '/admin/bbps/catalog' },
        { name: 'Provider Float', path: '/admin/bbps/float' },
        { name: 'Ops Tools', path: '/admin/bbps/ops' },
        { name: 'BillAvenue Settings', path: '/admin/bbps/settings' },
      ],
    },
    {
      name: 'AEPS',
      path: '/aeps',
      icon: 'aeps',
      submenu: [
        { name: 'Workspace', path: '/aeps' },
        { name: 'Provider', path: '/admin/aeps/provider' },
        { name: 'Debug logs', path: '/admin/aeps/debug-logs' },
        { name: 'Access requests', path: '/admin/aeps/requests' },
        { name: 'Merchants', path: '/admin/aeps/merchants' },
        { name: 'Reports', path: '/aeps/reports' },
        { name: 'Recon', path: '/admin/aeps/recon' },
      ],
    },
    {
      name: 'Notifications',
      path: '/admin/smtp-settings',
      icon: 'notifications',
      submenu: [
        { name: 'SMTP settings', path: '/admin/smtp-settings' },
        { name: 'Email notifications', path: '/admin/email-notifications' },
        { name: 'SMS settings', path: '/admin/sms-settings' },
      ],
    },
    {
      name: 'Platform settings',
      // Virtual parent path (no single module) so RBAC filters children independently
      path: '/admin/platform-settings',
      icon: 'settings',
      submenu: [
        { name: 'Announcements', path: '/admin/announcements' },
        { name: 'Appearance & theme', path: '/admin/appearance' },
        { name: 'Maintenance mode', path: '/admin/maintenance' },
        { name: 'Roles & permissions', path: '/admin/roles-permissions' },
      ],
    },
    {
      name: 'Profile',
      path: '/profile',
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
      name: 'AEPS',
      path: '/aeps',
      icon: 'aeps',
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
      name: 'AEPS',
      path: '/aeps',
      icon: 'aeps',
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
      name: 'AEPS',
      path: '/aeps',
      icon: 'aeps',
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
      name: 'AEPS',
      path: '/aeps',
      icon: 'aeps',
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

// Super Admin = Admin menus + Test usage under Platform settings
roleMenus['Super Admin'] = roleMenus.Admin.map((item) => {
  if (item.path !== '/admin/platform-settings') {
    return item;
  }
  return {
    ...item,
    submenu: [
      ...(item.submenu || []),
      { name: 'Test usage mode', path: '/admin/test-usage' },
    ],
  };
});

// Get menu for a role
export const getMenuForRole = (role) => {
  return roleMenus[role] || roleMenus.Retailer;
};

/**
 * Map menu item path → module code for DB-backed RBAC filtering.
 * Empty API modules list = no filtering (hardcoded menus remain).
 */
export const MENU_PATH_MODULE = [
  ['/admin/roles-permissions', 'roles_permissions'],
  ['/admin/test-usage', 'test_usage'],
  ['/admin/announcements', 'announcements'],
  ['/admin/maintenance', 'maintenance'],
  ['/admin/appearance', 'appearance'],
  ['/admin/wallet-adjustments', 'wallet_adjustments'],
  ['/admin/api-master', 'pay_in_setup'],
  ['/admin/gateways', 'pay_in_setup'],
  ['/admin/pay-in-packages', 'pay_in_setup'],
  ['/admin/pay-in-qr', 'manual_qr'],
  ['/admin/smtp-settings', 'notifications'],
  ['/admin/email-notifications', 'notifications'],
  ['/admin/sms-settings', 'notifications'],
  ['/admin/bbps', 'bbps_console'],
  ['/admin/aeps', 'aeps'],
  ['/user-management', 'user_management'],
  ['/fund-management', 'fund_management'],
  ['/bbps', 'bbps'],
  ['/aeps', 'aeps'],
  ['/reports', 'reports'],
  ['/dashboard', 'dashboard'],
  ['/profile', 'profile'],
];

export const moduleCodeForPath = (path) => {
  const p = path || '';
  for (const [prefix, code] of MENU_PATH_MODULE) {
    if (p === prefix || p.startsWith(`${prefix}/`)) return code;
  }
  return null;
};

export const filterMenusByModules = (menuItems, enabledModules) => {
  if (!Array.isArray(enabledModules) || enabledModules.length === 0) {
    return menuItems;
  }
  const allowed = new Set(enabledModules);
  return (menuItems || [])
    .map((item) => {
      if (item.submenu?.length) {
        const submenu = item.submenu.filter((sub) => {
          const sc = moduleCodeForPath(sub.path);
          return !sc || allowed.has(sc);
        });
        if (!submenu.length) return null;
        return { ...item, submenu };
      }
      const code = moduleCodeForPath(item.path);
      if (code && !allowed.has(code)) return null;
      return item;
    })
    .filter(Boolean);
};

/**
 * Mirror of backend ``apps/users/hierarchy_policy.py`` — keep in sync when changing onboarding rules.
 */
export const HIERARCHY_ROLE_ORDER = [
  'Super Admin',
  'Admin',
  'Super Distributor',
  'Master Distributor',
  'Distributor',
  'Retailer',
];

export const CREATABLE_CHILD_ROLES = {
  'Super Admin': [
    'Super Admin',
    'Admin',
    'Super Distributor',
    'Master Distributor',
    'Distributor',
    'Retailer',
  ],
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
    'Super Admin',
    'Admin',
    'Super Distributor',
    'Master Distributor',
    'Distributor',
  ].includes(role);
};

/**
 * Platform roles blocked from personal pay-in, pay-out, and BBPS (mirrors backend FINANCIAL_TX_BLOCKED_ROLES).
 */
export const OPERATIONAL_FINANCE_BLOCKED_ROLES = ['Super Admin', 'Admin'];

/** True when role cannot use load-money, payout, or BBPS operational routes. */
export const isOperationalFundBlockedRole = (role) =>
  OPERATIONAL_FINANCE_BLOCKED_ROLES.includes(role);

/** Alias used by dashboard quick actions — same policy as operational fund block. */
export const isFinancialTxBlockedRole = (role) => isOperationalFundBlockedRole(role);

/** Admin UI: hide retailer/distributor-style money movement; show admin tools instead. */
export const isAdminOperationalIsolationRole = (role) =>
  role === 'Admin' || role === 'Super Admin';

/** Roles that may request downline-scoped reports (scope=team). */
export const canUseTeamReportScope = (role) =>
  ['Super Admin', 'Admin', 'Super Distributor', 'Master Distributor', 'Distributor'].includes(
    role
  );

/** Platform operator (Admin or Super Admin). */
export const isAdminUser = (user) => {
  const role = user?.role || '';
  return role === 'Admin' || role === 'Super Admin';
};

export const isSuperAdminUser = (user) => (user?.role || '') === 'Super Admin';

export { isPayInOnlySession, userMayLogin } from './userAccess';
