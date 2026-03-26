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
      name: 'Gateway Management',
      path: '/admin/gateways',
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
    Admin: ['Master Distributor', 'Distributor', 'Retailer'],
    'Master Distributor': ['Distributor', 'Retailer'],
    Distributor: ['Retailer'],
    Retailer: [],
  };

  return permissions[currentUserRole]?.includes(targetRole) || false;
};

// Check if user can view commission wallet
export const canViewCommissionWallet = (role) => {
  return ['Admin', 'Master Distributor', 'Distributor'].includes(role);
};
