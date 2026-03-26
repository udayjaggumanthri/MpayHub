// Mock Data Service for mPayhub Platform

// Mock Users with different roles
export const mockUsers = [
  {
    id: 'admin1',
    userId: 'ADMIN001',
    name: 'Admin User',
    phone: '9876543210',
    password: 'admin123',
    mpin: '123456',
    email: 'admin@mpayhub.com',
    role: 'Admin',
    wallet: {
      main: 500000.00,
      commission: 45000.00,
      bbps: 25000.00,
    },
  },
  {
    id: 'md1',
    userId: 'MD1',
    name: 'Master Distributor One',
    phone: '9876543211',
    password: 'md123',
    mpin: '111111',
    email: 'md1@mpayhub.com',
    role: 'Master Distributor',
    wallet: {
      main: 245656.21,
      commission: 15000.00,
      bbps: 10000.00,
    },
  },
  {
    id: 'd1',
    userId: 'DT1',
    name: 'Distributor One',
    phone: '9876543212',
    password: 'd123',
    mpin: '222222',
    email: 'd1@mpayhub.com',
    role: 'Distributor',
    wallet: {
      main: 150000.00,
      commission: 8000.00,
      bbps: 5000.00,
    },
  },
  {
    id: 'r1',
    userId: 'R1',
    name: 'Retailer One',
    phone: '9876543213',
    password: 'r123',
    mpin: '333333',
    email: 'r1@mpayhub.com',
    role: 'Retailer',
    wallet: {
      main: 50000.00,
      commission: 0.00,
      bbps: 2000.00,
    },
  },
];

// Mock Transactions
export const mockTransactions = {
  admin1: [
    {
      id: 'txn001',
      date: new Date('2025-11-28T11:05:30'),
      type: 'payin',
      serviceId: 'PMPI2025112900574',
      customerId: 'PMCT11494',
      mode: 'VISA CREDIT CARD',
      amount: 39998,
      charge: 559.972,
      netCredit: 39435.528,
      cardNumber: 'XXXXXXXXXXXX2006',
      cardNetwork: 'VISA',
      bankTransactionId: '4631245850',
      gatewayName: 'NSTPL : TRAVEL',
      status: 'SUCCESS',
    },
    {
      id: 'txn002',
      date: new Date('2025-11-28T10:58:26'),
      type: 'payin',
      serviceId: 'PMPI2025112900533',
      customerId: 'PMCT11494',
      mode: 'VISA CREDIT CARD',
      amount: 49997,
      charge: 699.958,
      netCredit: 49294.542,
      cardNumber: 'XXXXXXXXXXXX2006',
      cardNetwork: 'VISA',
      bankTransactionId: '4631201860',
      gatewayName: 'NSTPL : TRAVEL',
      status: 'SUCCESS',
    },
    {
      id: 'txn003',
      date: new Date('2025-11-28T12:46:58'),
      type: 'payout',
      serviceId: 'PMPO2025111718973',
      retailerId: 'PMRT11140',
      operatorId: 'PAYMAMA - PAYOUT',
      accountNumber: '193410100073146',
      bankName: 'UNION BANK OF INDIA',
      amount: 87930,
      charge: 12.50,
      platformFee: 2.5,
      status: 'SUCCESS',
    },
  ],
  md1: [
    {
      id: 'txn004',
      date: new Date('2025-11-28T09:30:00'),
      type: 'payin',
      serviceId: 'PMPI2025112801234',
      customerId: 'PMCT11495',
      mode: 'UPI',
      amount: 25000,
      charge: 250,
      netCredit: 24750,
      status: 'SUCCESS',
    },
  ],
  d1: [
    {
      id: 'txn005',
      date: new Date('2025-11-28T08:15:00'),
      type: 'payin',
      serviceId: 'PMPI2025112801235',
      customerId: 'PMCT11496',
      mode: 'NET BANKING',
      amount: 15000,
      charge: 150,
      netCredit: 14850,
      status: 'SUCCESS',
    },
  ],
  r1: [
    {
      id: 'txn006',
      date: new Date('2025-11-28T14:20:00'),
      type: 'bbps',
      serviceId: 'PMBB2025112801236',
      biller: 'Federal Bank Credit Card',
      billType: 'Credit Card',
      amount: 46082.34,
      status: 'SUCCESS',
    },
  ],
};

// Mock BBPS Bills
export const mockBills = {
  creditCards: [
    {
      biller: 'Federal Bank Credit Card',
      cardLast4: '3998',
      mobile: '9703013997',
      name: 'MuraliSaiKur Patnala',
      totalDueAmount: 46082.34,
      minimumDueAmount: 4608.23,
      dueDate: '2025-12-07',
      telephoneNumber: '9703013997',
    },
  ],
  electricity: [],
  insurance: [],
  mobileRecharge: [],
  fastTag: [],
  education: [],
};

// Mock Bank Accounts
export const mockBankAccounts = {
  admin1: [
    {
      id: 'acc001',
      accountNumber: '193410100073146',
      ifsc: 'UBI00812455',
      bankName: 'UNION BANK OF INDIA',
      accountHolderName: 'Admin User',
      validated: true,
      beneficiaryName: 'Admin User',
    },
  ],
  md1: [
    {
      id: 'acc002',
      accountNumber: '1234567890123',
      ifsc: 'HDFC0001234',
      bankName: 'HDFC BANK',
      accountHolderName: 'Master Distributor One',
      validated: true,
      beneficiaryName: 'Master Distributor One',
    },
  ],
  d1: [],
  r1: [],
};

// Mock Contacts
export const mockContacts = {
  admin1: [
    {
      id: 'contact001',
      name: 'John Doe',
      email: 'john@example.com',
      phone: '9876543214',
    },
    {
      id: 'contact002',
      name: 'Jane Smith',
      email: 'jane@example.com',
      phone: '9876543215',
    },
  ],
  md1: [
    {
      id: 'contact003',
      name: 'Bob Johnson',
      email: 'bob@example.com',
      phone: '9876543216',
    },
  ],
  d1: [],
  r1: [],
};

// Mock Passbook Entries
export const mockPassbook = {
  admin1: [
    {
      id: 'pb001',
      date: new Date('2025-11-28T12:46:58'),
      service: 'PAYOUT',
      serviceId: 'PMPO2025111718973',
      description: 'PAID FOR PAYOUT, ACCOUNT NUMBER 193410100073146, AMOUNT: 87930, CHARGE: 12.50, PLATFORM FEE: 2.5',
      debitAmount: 87945.00,
      creditAmount: 0.00,
      openingBalance: 111208.87,
      closingBalance: 23263.87,
    },
    {
      id: 'pb002',
      date: new Date('2025-11-28T12:46:32'),
      service: 'WALLET',
      serviceId: 'PMWT202525419002',
      description: 'FOR BANK VERIFICATION: 193410100073146, IFSC CODE: UBI00812455',
      debitAmount: 3.00,
      creditAmount: 0.00,
      openingBalance: 111211.87,
      closingBalance: 111208.87,
    },
  ],
  md1: [],
  d1: [],
  r1: [],
};

// Mock Commission Data
export const mockCommissions = {
  admin1: [],
  md1: [
    {
      id: 'comm001',
      date: new Date('2025-11-28T10:00:00'),
      fromUser: 'DT1',
      fromUserId: 'DT1',
      transactionId: 'txn005',
      transactionAmount: 15000,
      commissionRate: 0.5,
      commissionAmount: 75,
      status: 'SUCCESS',
    },
  ],
  d1: [
    {
      id: 'comm002',
      date: new Date('2025-11-28T14:20:00'),
      fromUser: 'R1',
      fromUserId: 'R1',
      transactionId: 'txn006',
      transactionAmount: 46082.34,
      commissionRate: 0.3,
      commissionAmount: 138.25,
      status: 'SUCCESS',
    },
  ],
};

// Mock Announcements
export const mockAnnouncements = [
  {
    id: 'ann001',
    title: 'Limit Increased!',
    message: 'Your daily transaction limit has been increased to ₹5,00,000',
    date: new Date('2025-11-28'),
    priority: 'high',
    read: false,
  },
  {
    id: 'ann002',
    title: 'New Feature: FastTag Payments',
    message: 'You can now pay FastTag bills directly from the dashboard',
    date: new Date('2025-11-27'),
    priority: 'medium',
    read: false,
  },
];

// Mock API Functions

// Login function
export const login = (phone, password) => {
  const user = mockUsers.find(
    (u) => u.phone === phone && u.password === password
  );
  if (user) {
    return {
      success: true,
      user: {
        id: user.id,
        userId: user.userId,
        name: user.name,
        phone: user.phone,
        email: user.email,
        role: user.role,
      },
    };
  }
  return {
    success: false,
    message: 'Invalid phone number or password',
  };
};

// MPIN Verification
export const verifyMPIN = (userId, mpin) => {
  const user = mockUsers.find((u) => u.id === userId || u.userId === userId);
  if (user && user.mpin === mpin) {
    return { success: true };
  }
  return {
    success: false,
    message: 'Invalid MPIN',
  };
};

// Send OTP (for password reset)
export const sendOTP = (phone, purpose = 'password-reset') => {
  // Check if user exists
  const user = mockUsers.find((u) => u.phone === phone);
  if (!user) {
    return {
      success: false,
      message: 'Phone number not registered. Please check and try again.',
    };
  }

  // Mock OTP sending - in real app, this would send SMS
  return new Promise((resolve) => {
    setTimeout(() => {
      resolve({
        success: true,
        message: `OTP sent to ${phone.substring(0, 2)}****${phone.substring(6)}. Mock OTP: 123456`,
      });
    }, 1000);
  });
};

// Reset Password
export const resetPassword = (phone, otp, newPassword) => {
  // Verify OTP (mock: accept 123456)
  if (otp !== '123456') {
    return {
      success: false,
      message: 'Invalid OTP. Please try again.',
    };
  }

  // Find user and update password
  const user = mockUsers.find((u) => u.phone === phone);
  if (!user) {
    return {
      success: false,
      message: 'User not found. Please check your phone number.',
    };
  }

  // Update password
  user.password = newPassword;

  return {
    success: true,
    message: 'Password reset successfully!',
  };
};

// Get Wallets
export const getWallets = (userId) => {
  const user = mockUsers.find((u) => u.id === userId || u.userId === userId);
  if (user) {
    return {
      success: true,
      wallets: user.wallet,
    };
  }
  return { success: false };
};

// Get Transactions
export const getTransactions = (userId, type = 'all', filters = {}) => {
  const user = mockUsers.find((u) => u.id === userId || u.userId === userId);
  if (!user) return { success: false, transactions: [] };

  let transactions = mockTransactions[user.id] || [];

  // Filter by type
  if (type !== 'all') {
    transactions = transactions.filter((t) => t.type === type);
  }

  // Apply additional filters
  if (filters.serviceId) {
    transactions = transactions.filter((t) =>
      t.serviceId.toLowerCase().includes(filters.serviceId.toLowerCase())
    );
  }

  if (filters.status && filters.status !== 'ALL') {
    transactions = transactions.filter((t) => t.status === filters.status);
  }

  if (filters.dateFrom && filters.dateTo) {
    transactions = transactions.filter((t) => {
      const txnDate = new Date(t.date);
      const fromDate = new Date(filters.dateFrom);
      const toDate = new Date(filters.dateTo);
      toDate.setHours(23, 59, 59, 999); // Include entire end date
      return txnDate >= fromDate && txnDate <= toDate;
    });
  }

  // Sort by date (most recent first)
  transactions.sort((a, b) => new Date(b.date) - new Date(a.date));

  return {
    success: true,
    transactions,
  };
};

// Fetch Bill
export const fetchBill = (biller, cardLast4, mobile) => {
  // For credit cards
  const bill = mockBills.creditCards.find(
    (b) =>
      b.biller.toLowerCase().includes(biller.toLowerCase()) &&
      b.cardLast4 === cardLast4 &&
      b.mobile === mobile
  );

  if (bill) {
    return {
      success: true,
      bill: {
        name: bill.name,
        totalDueAmount: bill.totalDueAmount,
        minimumDueAmount: bill.minimumDueAmount,
        dueDate: bill.dueDate,
        telephoneNumber: bill.telephoneNumber,
      },
    };
  }

  return {
    success: false,
    message: 'Bill not found. Please check the details and try again.',
  };
};

// Validate Bank Account
export const validateBankAccount = (userId, accountNumber, ifsc) => {
  // Mock validation - returns a beneficiary name
  const mockBeneficiaryNames = [
    'Mr REESU MADHU PAVAN',
    'Mrs KAVITHA REDDY',
    'Mr RAVI KUMAR',
    'Ms PRIYA SHARMA',
    'Mr R PAVA',
    'BALR',
    'KONE MAN',
  ];

  // Simulate validation delay
  return new Promise((resolve) => {
    setTimeout(() => {
      const beneficiaryName = mockBeneficiaryNames[
        Math.floor(Math.random() * mockBeneficiaryNames.length)
      ];

      // Record bank verification charge (₹3.00) in passbook
      if (userId) {
        const user = mockUsers.find((u) => u.id === userId || u.userId === userId);
        if (user) {
          const verificationCharge = 3.00;
          const openingBalance = user.wallet.main;
          
          if (user.wallet.main >= verificationCharge) {
            user.wallet.main -= verificationCharge;
            const closingBalance = user.wallet.main;

            // Add passbook entry for bank verification
            if (!mockPassbook[user.id]) {
              mockPassbook[user.id] = [];
            }

            const passbookEntry = {
              id: `pb_${Date.now()}`,
              date: new Date(),
              service: 'Bank Verification',
              serviceId: `BV${new Date().getFullYear()}${String(new Date().getMonth() + 1).padStart(2, '0')}${String(new Date().getDate()).padStart(2, '0')}${Math.floor(Math.random() * 100000)}`,
              description: `BANK VERIFICATION, ACCOUNT: ${accountNumber.substring(accountNumber.length - 4)}, IFSC: ${ifsc}`,
              debitAmount: verificationCharge,
              creditAmount: 0.00,
              openingBalance: openingBalance,
              closingBalance: closingBalance,
            };

            mockPassbook[user.id].unshift(passbookEntry);
          }
        }
      }

      resolve({
        success: true,
        beneficiaryName,
        accountNumber,
        ifsc,
      });
    }, 1000);
  });
};

// Mock Payment Gateways
export const mockPaymentGateways = [
  {
    id: 'slpe-gold-lite',
    name: 'SLPE Gold Travel - Lite',
    chargeRate: 1.0,
    status: 'active', // 'active' or 'down'
    visibleToRoles: ['Admin', 'Master Distributor', 'Distributor', 'Retailer'],
    category: 'slpe-gold',
  },
  {
    id: 'slpe-gold-prime',
    name: 'SLPE Gold Travel - Prime',
    chargeRate: 1.2,
    status: 'active',
    visibleToRoles: ['Admin', 'Master Distributor', 'Distributor', 'Retailer'],
    category: 'slpe-gold',
  },
  {
    id: 'slpe-gold-pure',
    name: 'SLPE Gold Travel - Pure',
    chargeRate: 1.5,
    status: 'active',
    visibleToRoles: ['Admin', 'Master Distributor', 'Distributor'],
    category: 'slpe-gold',
  },
  {
    id: 'slpe-silver-lite',
    name: 'SLPE Silver Prime Edu - Lite',
    chargeRate: 0.9,
    status: 'active',
    visibleToRoles: ['Admin', 'Master Distributor', 'Distributor', 'Retailer'],
    category: 'slpe-silver',
  },
  {
    id: 'slpe-silver-edu',
    name: 'SLPE Silver Prime Edu - Edu',
    chargeRate: 1.0,
    status: 'active',
    visibleToRoles: ['Admin', 'Master Distributor', 'Distributor', 'Retailer'],
    category: 'slpe-silver',
  },
  {
    id: 'razorpay',
    name: 'Razorpay',
    chargeRate: 1.1,
    status: 'active',
    visibleToRoles: ['Admin', 'Master Distributor', 'Distributor', 'Retailer'],
    category: 'third-party',
  },
  {
    id: 'payu',
    name: 'PayU',
    chargeRate: 1.0,
    status: 'active',
    visibleToRoles: ['Admin', 'Master Distributor', 'Distributor', 'Retailer'],
    category: 'third-party',
  },
];

// Mock Payout Gateways
export const mockPayoutGateways = [
  {
    id: 'idfc-payout',
    name: 'IDFC Payout',
    status: 'active',
    visibleToRoles: ['Admin', 'Master Distributor', 'Distributor', 'Retailer'],
  },
  {
    id: 'paymama-payout',
    name: 'PAYMAMA - PAYOUT',
    status: 'active',
    visibleToRoles: ['Admin', 'Master Distributor', 'Distributor', 'Retailer'],
  },
];

// Get Payout Gateways
export const getPayoutGateways = (userRole) => {
  return {
    success: true,
    gateways: mockPayoutGateways.filter(
      (gw) =>
        gw.status === 'active' &&
        (gw.visibleToRoles.includes(userRole) || gw.visibleToRoles.includes('Admin'))
    ),
  };
};

// Get Payment Gateways (filtered by role and status)
export const getPaymentGateways = (userRole) => {
  return {
    success: true,
    gateways: mockPaymentGateways.filter(
      (gw) =>
        gw.status === 'active' &&
        (gw.visibleToRoles.includes(userRole) || gw.visibleToRoles.includes('Admin'))
    ),
  };
};

// Get All Payment Gateways (for Admin)
export const getAllPaymentGateways = () => {
  return {
    success: true,
    gateways: [...mockPaymentGateways],
  };
};

// Add Payment Gateway (Admin only)
export const addPaymentGateway = (gateway) => {
  const newGateway = {
    ...gateway,
    id: gateway.id || `gateway-${Date.now()}`,
    status: gateway.status || 'active',
  };
  mockPaymentGateways.push(newGateway);
  return {
    success: true,
    gateway: newGateway,
  };
};

// Update Payment Gateway (Admin only)
export const updatePaymentGateway = (gatewayId, updates) => {
  const index = mockPaymentGateways.findIndex((gw) => gw.id === gatewayId);
  if (index === -1) {
    return { success: false, message: 'Gateway not found' };
  }

  mockPaymentGateways[index] = {
    ...mockPaymentGateways[index],
    ...updates,
  };

  return {
    success: true,
    gateway: mockPaymentGateways[index],
  };
};

// Delete Payment Gateway (Admin only)
export const deletePaymentGateway = (gatewayId) => {
  const index = mockPaymentGateways.findIndex((gw) => gw.id === gatewayId);
  if (index === -1) {
    return { success: false, message: 'Gateway not found' };
  }

  mockPaymentGateways.splice(index, 1);
  return { success: true };
};

// Toggle Gateway Status (Admin only)
export const toggleGatewayStatus = (gatewayId) => {
  const gateway = mockPaymentGateways.find((gw) => gw.id === gatewayId);
  if (!gateway) {
    return { success: false, message: 'Gateway not found' };
  }

  gateway.status = gateway.status === 'active' ? 'down' : 'active';
  return {
    success: true,
    gateway,
  };
};

// Calculate Service Charge (updated to use gateway-specific rates)
export const calculateServiceCharge = (amount, gatewayId, type = 'payin') => {
  // If gatewayId is provided, use gateway-specific rate
  if (gatewayId) {
    const gateway = mockPaymentGateways.find((gw) => gw.id === gatewayId);
    if (gateway) {
      const chargeRate = gateway.chargeRate / 100; // Convert percentage to decimal
      const charge = amount * chargeRate;
      const netAmount = amount - charge;

      return {
        chargeRate: gateway.chargeRate,
        charge,
        netAmount,
      };
    }
  }

  // Fallback to default rates
  const chargeRate = type === 'payin' ? 0.01 : 0.001; // 1% for payin, 0.1% for payout
  const charge = amount * chargeRate;
  const netAmount = amount - charge;

  return {
    chargeRate: chargeRate * 100, // Percentage
    charge,
    netAmount,
  };
};

// Get Bank Accounts
export const getBankAccounts = (userId) => {
  const user = mockUsers.find((u) => u.id === userId || u.userId === userId);
  if (!user) return { success: false, accounts: [] };

  const accounts = mockBankAccounts[user.id] || [];
  return {
    success: true,
    accounts,
  };
};

// Delete Bank Account
export const deleteBankAccount = (userId, accountId) => {
  const user = mockUsers.find((u) => u.id === userId || u.userId === userId);
  if (!user) return { success: false, message: 'User not found' };

  const accounts = mockBankAccounts[user.id] || [];
  const accountIndex = accounts.findIndex((acc) => acc.id === accountId);

  if (accountIndex === -1) {
    return { success: false, message: 'Bank account not found' };
  }

  accounts.splice(accountIndex, 1);

  return {
    success: true,
    message: 'Bank account deleted successfully',
  };
};

// Get Contacts
export const getContacts = (userId, filters = {}) => {
  const user = mockUsers.find((u) => u.id === userId || u.userId === userId);
  if (!user) return { success: false, contacts: [] };

  let contacts = mockContacts[user.id] || [];

  // Apply filters
  if (filters.name) {
    contacts = contacts.filter((c) =>
      c.name.toLowerCase().includes(filters.name.toLowerCase())
    );
  }

  if (filters.email) {
    contacts = contacts.filter((c) =>
      c.email.toLowerCase().includes(filters.email.toLowerCase())
    );
  }

  if (filters.phone) {
    contacts = contacts.filter((c) => c.phone.includes(filters.phone));
  }

  return {
    success: true,
    contacts,
  };
};

// Get Contact by Phone Number
export const getContactByPhone = (userId, phoneNumber) => {
  const user = mockUsers.find((u) => u.id === userId || u.userId === userId);
  if (!user) return { success: false };

  const contacts = mockContacts[user.id] || [];
  const contact = contacts.find((c) => c.phone === phoneNumber);

  if (contact) {
    return {
      success: true,
      contact,
    };
  }

  return {
    success: false,
    message: 'Contact not found',
  };
};

// Add New Contact
export const addContact = (userId, contactData) => {
  const user = mockUsers.find((u) => u.id === userId || u.userId === userId);
  if (!user) return { success: false, message: 'User not found' };

  // Check if phone number already exists
  const existingContacts = mockContacts[user.id] || [];
  const phoneExists = existingContacts.some((c) => c.phone === contactData.phone);
  if (phoneExists) {
    return { success: false, message: 'Contact with this phone number already exists' };
  }

  const newContact = {
    id: `contact_${Date.now()}`,
    name: contactData.name.trim(),
    email: contactData.email.trim().toLowerCase(),
    phone: contactData.phone,
    createdAt: new Date(),
  };

  if (!mockContacts[user.id]) {
    mockContacts[user.id] = [];
  }

  // Add to beginning (latest first)
  mockContacts[user.id].unshift(newContact);

  return {
    success: true,
    contact: newContact,
  };
};

// Update Contact
export const updateContact = (userId, contactId, contactData) => {
  const user = mockUsers.find((u) => u.id === userId || u.userId === userId);
  if (!user) return { success: false, message: 'User not found' };

  const contacts = mockContacts[user.id] || [];
  const contactIndex = contacts.findIndex((c) => c.id === contactId);

  if (contactIndex === -1) {
    return { success: false, message: 'Contact not found' };
  }

  // Check if phone number already exists (excluding current contact)
  const phoneExists = contacts.some(
    (c) => c.id !== contactId && c.phone === contactData.phone
  );
  if (phoneExists) {
    return { success: false, message: 'Contact with this phone number already exists' };
  }

  // Update contact
  contacts[contactIndex] = {
    ...contacts[contactIndex],
    name: contactData.name.trim(),
    email: contactData.email.trim().toLowerCase(),
    phone: contactData.phone,
    updatedAt: new Date(),
  };

  return {
    success: true,
    contact: contacts[contactIndex],
  };
};

// Get Passbook
export const getPassbook = (userId, filters = {}) => {
  const user = mockUsers.find((u) => u.id === userId || u.userId === userId);
  if (!user) return { success: false, entries: [] };

  let entries = mockPassbook[user.id] || [];

  // Apply filters
  if (filters.dateFrom && filters.dateTo) {
    entries = entries.filter((e) => {
      const entryDate = new Date(e.date);
      return entryDate >= filters.dateFrom && entryDate <= filters.dateTo;
    });
  }

  if (filters.search) {
    entries = entries.filter(
      (e) =>
        e.serviceId.toLowerCase().includes(filters.search.toLowerCase()) ||
        e.description.toLowerCase().includes(filters.search.toLowerCase())
    );
  }

  // Sort by date (most recent first)
  entries.sort((a, b) => new Date(b.date) - new Date(a.date));

  return {
    success: true,
    entries,
  };
};

// Get Commissions
export const getCommissions = (userId) => {
  const user = mockUsers.find((u) => u.id === userId || u.userId === userId);
  if (!user) return { success: false, commissions: [] };

  const commissions = mockCommissions[user.id] || [];
  return {
    success: true,
    commissions: commissions.sort(
      (a, b) => new Date(b.date) - new Date(a.date)
    ),
  };
};

// Get Announcements
export const getAnnouncements = (userId) => {
  // Return all announcements (in real app, this would be filtered by user)
  return {
    success: true,
    announcements: mockAnnouncements.filter((a) => !a.read),
  };
};

// Get Users (for user management)
export const getUsers = (currentUserId, role = 'all') => {
  const currentUser = mockUsers.find(
    (u) => u.id === currentUserId || u.userId === currentUserId
  );
  if (!currentUser) return { success: false, users: [] };

  let users = [...mockUsers];

  // Filter based on current user's role and requested role
  if (currentUser.role === 'Master Distributor') {
    users = users.filter((u) => u.role === 'Distributor' || u.role === 'Retailer');
  } else if (currentUser.role === 'Distributor') {
    users = users.filter((u) => u.role === 'Retailer');
  }

  // Additional role filter
  if (role !== 'all') {
    users = users.filter((u) => u.role === role);
  }

  return {
    success: true,
    users: users.map((u) => ({
      id: u.id,
      userId: u.userId,
      name: u.name,
      phone: u.phone,
      email: u.email,
      role: u.role,
    })),
  };
};

// Generate new user ID based on role with dynamic sequential numbering
export const generateUserId = (role) => {
  // Role-based prefix mapping
  const rolePrefix = {
    Admin: 'ADMIN',
    'Master Distributor': 'MD', // Can also use 'M' or 'MMD' if needed
    Distributor: 'DT', // Changed from 'D' to 'DT' as per requirements (e.g., DT1151)
    Retailer: 'R',
  };

  const prefix = rolePrefix[role] || 'USER';
  
  // Get all existing users of this role
  const existingUsers = mockUsers.filter((u) => u.role === role);
  
  // Extract numeric suffixes from existing user IDs and find the maximum
  const existingNumbers = existingUsers
    .map((user) => {
      const userId = user.userId || '';
      // Match the prefix and extract the number after it
      const match = userId.match(new RegExp(`^${prefix}(\\d+)$`, 'i'));
      return match ? parseInt(match[1], 10) : 0;
    })
    .filter((num) => num > 0); // Filter out invalid numbers

  // Get the next sequential number
  const maxNumber = existingNumbers.length > 0 ? Math.max(...existingNumbers) : 0;
  const nextNumber = maxNumber + 1;

  return `${prefix}${nextNumber}`;
};

// Add new transaction (for processing payments)
export const addTransaction = (userId, transaction) => {
  const user = mockUsers.find((u) => u.id === userId || u.userId === userId);
  if (!user) return { success: false };

  if (!mockTransactions[user.id]) {
    mockTransactions[user.id] = [];
  }

  // Generate Request ID for BBPS transactions (external identifier)
  const generateRequestId = () => {
    const chars = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789';
    let result = '';
    for (let i = 0; i < 20; i++) {
      result += chars.charAt(Math.floor(Math.random() * chars.length));
    }
    return result;
  };

  const newTransaction = {
    ...transaction,
    id: `txn${Date.now()}`,
    date: new Date(),
    serviceId: generateServiceId(transaction.type),
    // Add Request ID for BBPS transactions (external identifier from gateway/biller)
    requestId: transaction.type === 'bbps' ? generateRequestId() : transaction.requestId || null,
  };

  mockTransactions[user.id].unshift(newTransaction);

  // Calculate opening balance (current wallet balance)
  const openingBalance = user.wallet.main;
  let closingBalance = openingBalance;

  // Update wallet if needed
  if (transaction.type === 'payin' && transaction.status === 'SUCCESS') {
    user.wallet.main += transaction.netCredit || transaction.amount;
    closingBalance = user.wallet.main;
  } else if (transaction.type === 'payout' && transaction.status === 'SUCCESS') {
    const totalDeducted = transaction.amount + (transaction.charge || 0) + (transaction.platformFee || 0);
    user.wallet.main -= totalDeducted;
    closingBalance = user.wallet.main;

    // Add passbook entry for payout
    if (!mockPassbook[user.id]) {
      mockPassbook[user.id] = [];
    }

    const passbookEntry = {
      id: `pb_${Date.now()}`,
      date: new Date(),
      service: 'PAYOUT',
      serviceId: newTransaction.serviceId,
      description: `PAID FOR PAYOUT, ACCOUNT NUMBER ${transaction.accountNumber || 'N/A'}, AMOUNT: ${transaction.amount}, CHARGE: ${transaction.charge || 0}, PLATFORM FEE: ${transaction.platformFee || 0}`,
      debitAmount: totalDeducted,
      creditAmount: 0.00,
      openingBalance: openingBalance,
      closingBalance: closingBalance,
    };

    mockPassbook[user.id].unshift(passbookEntry);
  } else if (transaction.type === 'bbps' && transaction.status === 'SUCCESS') {
    // BBPS transactions deduct from BBPS wallet
    const serviceCharge = transaction.charge || 5.00; // Default ₹5.00 service charge
    const totalDeducted = transaction.amount + serviceCharge;
    const openingBalance = user.wallet.bbps || 0;
    
    if (user.wallet.bbps < totalDeducted) {
      return { success: false, message: 'Insufficient BBPS wallet balance' };
    }
    
    user.wallet.bbps -= totalDeducted;
    const closingBalance = user.wallet.bbps;

    // Add passbook entry for BBPS
    if (!mockPassbook[user.id]) {
      mockPassbook[user.id] = [];
    }

    const passbookEntry = {
      id: `pb_${Date.now()}`,
      date: new Date(),
      service: 'BBPS',
      serviceId: newTransaction.serviceId,
      description: `PAID FOR ${transaction.billType || 'BILL PAYMENT'}, BILLER: ${transaction.biller || 'N/A'}, AMOUNT: ${transaction.amount}, CHARGE: ${serviceCharge}`,
      debitAmount: totalDeducted,
      creditAmount: 0.00,
      openingBalance: openingBalance,
      closingBalance: closingBalance,
    };

    mockPassbook[user.id].unshift(passbookEntry);
  }

  return {
    success: true,
    transaction: newTransaction,
  };
};

// Generate service ID
export const generateServiceId = (type) => {
  const prefixes = {
    payin: 'PMPI',
    payout: 'PMPO',
    bbps: 'PMBB',
    wallet: 'PMWT',
  };

  const prefix = prefixes[type] || 'PMTX';
  const date = new Date();
  const dateStr = `${date.getFullYear()}${String(date.getMonth() + 1).padStart(2, '0')}${String(date.getDate()).padStart(2, '0')}`;
  const random = Math.floor(Math.random() * 100000);

  return `${prefix}${dateStr}${random}`;
};

// Calculate BBPS Service Charge
export const calculateBBPSCharge = (amount) => {
  // Fixed service charge of ₹5.00 for BBPS transactions
  return 5.00;
};

// Update wallet balance
export const updateWallet = (userId, walletType, amount) => {
  const user = mockUsers.find((u) => u.id === userId || u.userId === userId);
  if (!user) return { success: false };

  if (user.wallet[walletType] !== undefined) {
    user.wallet[walletType] += amount;
    return { success: true, wallet: user.wallet };
  }

  return { success: false };
};
