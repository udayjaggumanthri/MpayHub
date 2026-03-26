import { format, formatDistanceToNow } from 'date-fns';

// Format currency (Indian Rupees)
export const formatCurrency = (amount) => {
  if (amount === null || amount === undefined) return '₹0.00';
  return new Intl.NumberFormat('en-IN', {
    style: 'currency',
    currency: 'INR',
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(amount);
};

// Format date and time
export const formatDateTime = (date) => {
  if (!date) return '';
  try {
    const dateObj = date instanceof Date ? date : new Date(date);
    return format(dateObj, 'dd MMM, yyyy, hh:mm:ss a');
  } catch (error) {
    return '';
  }
};

// Format date only
export const formatDate = (date) => {
  if (!date) return '';
  try {
    const dateObj = date instanceof Date ? date : new Date(date);
    return format(dateObj, 'dd MMM, yyyy');
  } catch (error) {
    return '';
  }
};

// Format relative time (e.g., "2 hours ago")
export const formatRelativeTime = (date) => {
  if (!date) return '';
  try {
    const dateObj = date instanceof Date ? date : new Date(date);
    return formatDistanceToNow(dateObj, { addSuffix: true });
  } catch (error) {
    return '';
  }
};

// Format phone number (e.g., 9876543210 -> 98765 43210)
export const formatPhone = (phone) => {
  if (!phone) return '';
  const cleaned = phone.replace(/\D/g, '');
  if (cleaned.length === 10) {
    return `${cleaned.slice(0, 5)} ${cleaned.slice(5)}`;
  }
  return phone;
};

// Format account number (mask middle digits)
export const formatAccountNumber = (accountNumber, visibleDigits = 4) => {
  if (!accountNumber) return '';
  const cleaned = accountNumber.replace(/\D/g, '');
  if (cleaned.length <= visibleDigits * 2) return cleaned;
  const start = cleaned.slice(0, visibleDigits);
  const end = cleaned.slice(-visibleDigits);
  const middle = 'X'.repeat(cleaned.length - visibleDigits * 2);
  return `${start}${middle}${end}`;
};

// Format card number (mask middle digits, show last 4)
export const formatCardNumber = (cardNumber, lastDigits = 4) => {
  if (!cardNumber) return '';
  const cleaned = cardNumber.replace(/\D/g, '');
  if (cleaned.length <= lastDigits) return cleaned;
  const masked = 'X'.repeat(cleaned.length - lastDigits);
  const visible = cleaned.slice(-lastDigits);
  return `${masked}${visible}`;
};

// Get status color
export const getStatusColor = (status) => {
  const statusLower = status?.toLowerCase() || '';
  if (statusLower === 'success' || statusLower === 'completed') {
    return 'text-success-green bg-green-50 border-green-200';
  }
  if (statusLower === 'pending' || statusLower === 'processing') {
    return 'text-warning-yellow bg-yellow-50 border-yellow-200';
  }
  if (statusLower === 'failed' || statusLower === 'failure' || statusLower === 'error') {
    return 'text-error-red bg-red-50 border-red-200';
  }
  return 'text-gray-600 bg-gray-50 border-gray-200';
};

// Format user ID for display
export const formatUserId = (userId) => {
  if (!userId) return '';
  return userId.toUpperCase();
};
