// Validation utilities

// Validate phone number (10 digits)
export const validatePhone = (phone) => {
  if (!phone) return { valid: false, message: 'Phone number is required' };
  if (!/^\d{10}$/.test(phone)) {
    return { valid: false, message: 'Phone number must be 10 digits' };
  }
  return { valid: true };
};

// Validate email
export const validateEmail = (email) => {
  if (!email) return { valid: false, message: 'Email is required' };
  const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
  if (!emailRegex.test(email)) {
    return { valid: false, message: 'Invalid email format' };
  }
  return { valid: true };
};

// Validate MPIN (6 digits)
export const validateMPIN = (mpin) => {
  if (!mpin) return { valid: false, message: 'MPIN is required' };
  if (!/^\d{6}$/.test(mpin)) {
    return { valid: false, message: 'MPIN must be 6 digits' };
  }
  return { valid: true };
};

// Validate PAN (10 characters, alphanumeric)
export const validatePAN = (pan) => {
  if (!pan) return { valid: false, message: 'PAN is required' };
  const panRegex = /^[A-Z]{5}[0-9]{4}[A-Z]{1}$/;
  if (!panRegex.test(pan.toUpperCase())) {
    return { valid: false, message: 'Invalid PAN format' };
  }
  return { valid: true };
};

// Validate Aadhaar (12 digits)
export const validateAadhaar = (aadhaar) => {
  if (!aadhaar) return { valid: false, message: 'Aadhaar is required' };
  if (!/^\d{12}$/.test(aadhaar)) {
    return { valid: false, message: 'Aadhaar must be 12 digits' };
  }
  return { valid: true };
};

// Validate IFSC (11 characters)
export const validateIFSC = (ifsc) => {
  if (!ifsc) return { valid: false, message: 'IFSC is required' };
  const ifscRegex = /^[A-Z]{4}0[A-Z0-9]{6}$/;
  if (!ifscRegex.test(ifsc.toUpperCase())) {
    return { valid: false, message: 'Invalid IFSC format' };
  }
  return { valid: true };
};

// Validate account number (minimum 9 digits)
export const validateAccountNumber = (accountNumber) => {
  if (!accountNumber) return { valid: false, message: 'Account number is required' };
  if (!/^\d{9,18}$/.test(accountNumber)) {
    return { valid: false, message: 'Account number must be 9-18 digits' };
  }
  return { valid: true };
};

// Validate amount (positive number)
export const validateAmount = (amount) => {
  if (!amount || amount <= 0) {
    return { valid: false, message: 'Amount must be greater than 0' };
  }
  if (amount > 10000000) {
    return { valid: false, message: 'Amount exceeds maximum limit' };
  }
  return { valid: true };
};
