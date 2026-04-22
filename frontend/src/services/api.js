/**
 * API Service Layer for mPayhub Platform
 * Handles all API communication with the backend
 *
 * Security note: JWTs stored in browser storage (e.g. localStorage / sessionStorage) are readable by any
 * script on the page. Mitigate XSS risk with a strict Content-Security-Policy, dependency review, and
 * keeping third-party bundles patched; for stronger token isolation consider httpOnly cookies (separate workstream).
 */

import axios from 'axios';
import { normalizeAuthUser } from '../utils/authUser';

const normalizeApiBaseUrl = (rawBaseUrl) => {
  const fallback = '/api';
  if (!rawBaseUrl) return fallback;

  const trimmed = rawBaseUrl.trim().replace(/\/+$/, '');
  if (!trimmed) return fallback;

  // Accept both:
  // - http://localhost:8000
  // - http://localhost:8000/api
  // and normalize to .../api
  if (trimmed.endsWith('/api')) {
    return trimmed;
  }
  return `${trimmed}/api`;
};

// API Base URL - configured via environment variable with normalization
const API_BASE_URL = normalizeApiBaseUrl(process.env.REACT_APP_API_BASE_URL);

if (!process.env.REACT_APP_API_BASE_URL) {
  // Keep app running in local/reverse-proxy scenarios, but highlight missing env setup.
  // For explicit backend target, set REACT_APP_API_BASE_URL in frontend/.env.
  // eslint-disable-next-line no-console
  console.warn('REACT_APP_API_BASE_URL is not set. Falling back to relative /api.');
}

// Create axios instance with default config
const apiClient = axios.create({
  baseURL: API_BASE_URL,
  timeout: 30000, // 30 seconds
  headers: {
    'Content-Type': 'application/json',
  },
});

/**
 * Public auth endpoints must not send Bearer tokens. A stale/invalid JWT in storage
 * causes SimpleJWT to return 401 ("Given token not valid for any token type") before
 * AllowAny login logic runs.
 */
const isPublicAuthApiUrl = (config) => {
  const url = config?.url || '';
  return (
    url.includes('/auth/login') ||
    url.includes('/auth/send-otp') ||
    url.includes('/auth/verify-otp') ||
    url.includes('/auth/reset-password')
  );
};

// Request interceptor - Add auth token to requests
apiClient.interceptors.request.use(
  (config) => {
    if (isPublicAuthApiUrl(config)) {
      delete config.headers.Authorization;
      return config;
    }
    const token = localStorage.getItem('access_token') || sessionStorage.getItem('access_token');
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  },
  (error) => {
    return Promise.reject(error);
  }
);

/**
 * Paths that return 401 for invalid credentials or public auth flows.
 * Do not attempt JWT refresh on these — avoids retry loops and wrong refresh behavior.
 */
const skipTokenRefreshForUrl = (config) => {
  const url = config?.url || '';
  return isPublicAuthApiUrl(config) || url.includes('/auth/refresh-token');
};

// Response interceptor - Handle token refresh and errors
apiClient.interceptors.response.use(
  (response) => {
    return response;
  },
  async (error) => {
    const originalRequest = error.config;

    // Handle 401 Unauthorized - Token expired
    if (
      error.response?.status === 401 &&
      originalRequest &&
      !originalRequest._retry &&
      !skipTokenRefreshForUrl(originalRequest)
    ) {
      originalRequest._retry = true;

      try {
        const refreshToken = localStorage.getItem('refresh_token') || sessionStorage.getItem('refresh_token');
        if (refreshToken) {
          const response = await axios.post(`${API_BASE_URL}/auth/refresh-token/`, {
            refresh: refreshToken,
          });

          const tokens = response.data?.data?.tokens;
          if (tokens?.access) {
            localStorage.setItem('access_token', tokens.access);
            if (tokens.refresh) {
              localStorage.setItem('refresh_token', tokens.refresh);
            }

            originalRequest.headers.Authorization = `Bearer ${tokens.access}`;
            return apiClient(originalRequest);
          }
        }
      } catch (refreshError) {
        // Refresh failed - logout user
        localStorage.removeItem('access_token');
        localStorage.removeItem('refresh_token');
        sessionStorage.removeItem('mpayhub_user');
        sessionStorage.removeItem('mpayhub_mpin_verified');
        window.location.href = '/login';
        return Promise.reject(refreshError);
      }
    }

    return Promise.reject(error);
  }
);

/**
 * Extract data from API response
 * Backend returns: { success, data, message, errors }
 */
const extractData = (response) => {
  if (response.data && response.data.success !== undefined) {
    return response.data;
  }
  return { success: true, data: response.data, message: 'Success', errors: [] };
};

/**
 * Flatten DRF / app error payloads into a string array for UI.
 */
const normalizeErrorsList = (errors) => {
  if (errors == null) return [];
  if (Array.isArray(errors)) return errors.map((e) => String(e));
  if (typeof errors === 'object') {
    return Object.entries(errors).flatMap(([key, val]) => {
      if (Array.isArray(val)) return val.map((item) => `${key}: ${item}`);
      return [`${key}: ${val}`];
    });
  }
  return [String(errors)];
};

/**
 * Handle API errors consistently
 */
const handleError = (error) => {
  if (error.response) {
    // Server responded with error
    const apiError = error.response.data || {};
    const normalizedErrors = normalizeErrorsList(apiError.errors);
    const detail = apiError.detail;
    const detailMessage = Array.isArray(detail)
      ? detail.map((d) => (typeof d === 'string' ? d : d?.message || String(d))).join(' ')
      : typeof detail === 'string'
        ? detail
        : '';
    return {
      success: false,
      message: apiError.message || detailMessage || 'An error occurred',
      errors: normalizedErrors,
      status: error.response.status,
    };
  } else if (error.request) {
    // Request made but no response
    return {
      success: false,
      message: 'Network error. Please check your connection.',
      errors: [],
    };
  } else {
    // Something else happened
    return {
      success: false,
      message: error.message || 'An unexpected error occurred',
      errors: [],
    };
  }
};

/** Multipart requests must not use the default JSON Content-Type (boundary required). */
const formDataRequestConfig = (body) =>
  typeof FormData !== 'undefined' && body instanceof FormData
    ? {
        transformRequest: [
          (data, headers) => {
            if (data instanceof FormData) {
              delete headers['Content-Type'];
            }
            return data;
          },
        ],
      }
    : {};

// ==================== AUTHENTICATION APIs ====================

export const authAPI = {
  /**
   * Login user
   * POST /api/auth/login/
   */
  login: async (phone, password) => {
    try {
      const response = await apiClient.post('/auth/login/', {
        phone: String(phone ?? '').trim(),
        password,
      });
      const result = extractData(response);
      
      if (result.success && result.data?.tokens) {
        // Store tokens
        localStorage.setItem('access_token', result.data.tokens.access);
        localStorage.setItem('refresh_token', result.data.tokens.refresh);
        
        // Store user data (normalized for UI: name, userId)
        if (result.data.user) {
          sessionStorage.setItem(
            'mpayhub_user',
            JSON.stringify(normalizeAuthUser(result.data.user))
          );
        }
      }
      
      return result;
    } catch (error) {
      return handleError(error);
    }
  },

  /**
   * Verify MPIN
   * POST /api/auth/verify-mpin/
   */
  verifyMPIN: async (mpin) => {
    try {
      const response = await apiClient.post('/auth/verify-mpin/', { mpin });
      const result = extractData(response);
      
      if (result.success) {
        sessionStorage.setItem('mpayhub_mpin_verified', 'true');
      }
      
      return result;
    } catch (error) {
      return handleError(error);
    }
  },

  /**
   * Send OTP
   * POST /api/auth/send-otp/
   */
  sendOTP: async (phone, purpose = 'password-reset') => {
    try {
      const response = await apiClient.post('/auth/send-otp/', {
        phone: String(phone ?? '').trim(),
        purpose,
      });
      return extractData(response);
    } catch (error) {
      return handleError(error);
    }
  },

  /**
   * Verify OTP
   * POST /api/auth/verify-otp/
   */
  verifyOTP: async (phone, code, purpose = 'password-reset') => {
    try {
      const response = await apiClient.post('/auth/verify-otp/', {
        phone: String(phone ?? '').trim(),
        code: String(code ?? '').trim(),
        purpose,
      });
      return extractData(response);
    } catch (error) {
      return handleError(error);
    }
  },

  /**
   * Reset Password
   * POST /api/auth/reset-password/
   */
  resetPassword: async (phone, otp, newPassword, confirmPassword) => {
    try {
      const response = await apiClient.post('/auth/reset-password/', {
        phone: String(phone ?? '').trim(),
        otp: String(otp ?? '').trim(),
        new_password: newPassword,
        confirm_password: confirmPassword,
      });
      return extractData(response);
    } catch (error) {
      return handleError(error);
    }
  },

  /**
   * Refresh Token
   * POST /api/auth/refresh-token/
   */
  refreshToken: async () => {
    try {
      const refreshToken = localStorage.getItem('refresh_token') || sessionStorage.getItem('refresh_token');
      const response = await apiClient.post('/auth/refresh-token/', { refresh: refreshToken });
      const result = extractData(response);
      
      if (result.success && result.data?.tokens) {
        localStorage.setItem('access_token', result.data.tokens.access);
        localStorage.setItem('refresh_token', result.data.tokens.refresh);
      }
      
      return result;
    } catch (error) {
      return handleError(error);
    }
  },

  /**
   * Get Current User
   * GET /api/auth/me/
   */
  getCurrentUser: async () => {
    try {
      const response = await apiClient.get('/auth/me/');
      const result = extractData(response);
      
      if (result.success && result.data?.user) {
        sessionStorage.setItem(
          'mpayhub_user',
          JSON.stringify(normalizeAuthUser(result.data.user))
        );
      }
      
      return result;
    } catch (error) {
      return handleError(error);
    }
  },

  /**
   * KYC step 1: verify PAN. POST /api/auth/onboarding/kyc/pan/
   */
  verifyOnboardingPan: async (pan) => {
    try {
      const response = await apiClient.post('/auth/onboarding/kyc/pan/', {
        pan: String(pan ?? '').toUpperCase().trim(),
      });
      const result = extractData(response);
      if (result.success && result.data?.user) {
        sessionStorage.setItem(
          'mpayhub_user',
          JSON.stringify(normalizeAuthUser(result.data.user))
        );
      }
      return result;
    } catch (error) {
      return handleError(error);
    }
  },

  /**
   * KYC step 2a: Aadhaar + send OTP to registered mobile.
   * POST /api/auth/onboarding/kyc/aadhaar/send-otp/
   */
  sendOnboardingAadhaarOtp: async (aadhaar) => {
    try {
      const response = await apiClient.post('/auth/onboarding/kyc/aadhaar/send-otp/', {
        aadhaar: String(aadhaar ?? '').replace(/\D/g, '').slice(0, 12),
      });
      const result = extractData(response);
      if (result.success && result.data?.user) {
        sessionStorage.setItem(
          'mpayhub_user',
          JSON.stringify(normalizeAuthUser(result.data.user))
        );
      }
      return result;
    } catch (error) {
      return handleError(error);
    }
  },

  /**
   * KYC step 2b: verify Aadhaar OTP (SMS or demo 123456).
   * POST /api/auth/onboarding/kyc/aadhaar/verify-otp/
   */
  verifyOnboardingAadhaarOtp: async (otp) => {
    try {
      const response = await apiClient.post('/auth/onboarding/kyc/aadhaar/verify-otp/', {
        otp: String(otp ?? '').trim(),
      });
      const result = extractData(response);
      if (result.success && result.data?.user) {
        sessionStorage.setItem(
          'mpayhub_user',
          JSON.stringify(normalizeAuthUser(result.data.user))
        );
      }
      return result;
    } catch (error) {
      return handleError(error);
    }
  },

  /**
   * First-time MPIN after KYC.
   * POST /api/auth/onboarding/setup-mpin/
   */
  setupOnboardingMPIN: async (mpin, confirmMpin) => {
    try {
      const response = await apiClient.post('/auth/onboarding/setup-mpin/', {
        mpin: String(mpin ?? '').trim(),
        confirm_mpin: String(confirmMpin ?? '').trim(),
      });
      const result = extractData(response);
      if (result.success && result.data?.user) {
        sessionStorage.setItem(
          'mpayhub_user',
          JSON.stringify(normalizeAuthUser(result.data.user))
        );
      }
      return result;
    } catch (error) {
      return handleError(error);
    }
  },

  /**
   * Logout
   * POST /api/auth/logout/
   */
  logout: async () => {
    try {
      await apiClient.post('/auth/logout/');
    } catch (error) {
      // Continue with logout even if API call fails
      console.error('Logout API error:', error);
    } finally {
      // Clear all stored data
      localStorage.removeItem('access_token');
      localStorage.removeItem('refresh_token');
      sessionStorage.removeItem('mpayhub_user');
      sessionStorage.removeItem('mpayhub_mpin_verified');
      sessionStorage.removeItem('mpayhub_post_mpin_dashboard');
    }
  },

  /**
   * Change Password
   * POST /api/auth/change-password/
   */
  changePassword: async ({ current_password, new_password }) => {
    try {
      const response = await apiClient.post('/auth/change-password/', {
        current_password,
        new_password,
      });
      return extractData(response);
    } catch (error) {
      return handleError(error);
    }
  },

  /**
   * Change MPIN
   * POST /api/auth/change-mpin/
   */
  changeMPIN: async ({ current_mpin, new_mpin }) => {
    try {
      const response = await apiClient.post('/auth/change-mpin/', {
        current_mpin,
        new_mpin,
      });
      return extractData(response);
    } catch (error) {
      return handleError(error);
    }
  },
};

// ==================== USERS APIs ====================

export const usersAPI = {
  /**
   * List Users
   * GET /api/users/
   */
  listUsers: async (params = {}) => {
    try {
      const response = await apiClient.get('/users/', { params });
      return extractData(response);
    } catch (error) {
      return handleError(error);
    }
  },

  /**
   * Create User
   * POST /api/users/
   */
  createUser: async (userData) => {
    try {
      const response = await apiClient.post('/users/', userData);
      return extractData(response);
    } catch (error) {
      return handleError(error);
    }
  },

  /**
   * Get User Detail
   * GET /api/users/{id}/
   */
  getUserDetail: async (userId) => {
    try {
      const response = await apiClient.get(`/users/${userId}/`);
      return extractData(response);
    } catch (error) {
      return handleError(error);
    }
  },

  /**
   * Update User
   * PUT /api/users/{id}/
   */
  updateUser: async (userId, userData) => {
    try {
      const response = await apiClient.put(`/users/${userId}/`, userData);
      return extractData(response);
    } catch (error) {
      return handleError(error);
    }
  },

  /**
   * Partial Update User
   * PATCH /api/users/{id}/
   */
  partialUpdateUser: async (userId, userData) => {
    try {
      const response = await apiClient.patch(`/users/${userId}/`, userData);
      return extractData(response);
    } catch (error) {
      return handleError(error);
    }
  },

  /**
   * PATCH /api/users/{id}/role/ — Admin only; hierarchy-validated role change.
   */
  updateUserRole: async (userId, role) => {
    try {
      const response = await apiClient.patch(`/users/${userId}/role/`, { role });
      return extractData(response);
    } catch (error) {
      return handleError(error);
    }
  },

  /**
   * Admin only: enable or disable user account (blocks login and API access).
   * PATCH /api/users/{id}/active-status/
   */
  setUserActiveStatus: async (userId, isActive) => {
    try {
      const response = await apiClient.patch(`/users/${userId}/active-status/`, {
        is_active: Boolean(isActive),
      });
      return extractData(response);
    } catch (error) {
      return handleError(error);
    }
  },

  /**
   * Delete User
   * DELETE /api/users/{id}/
   */
  deleteUser: async (userId) => {
    try {
      const response = await apiClient.delete(`/users/${userId}/`);
      return extractData(response);
    } catch (error) {
      return handleError(error);
    }
  },

  /**
   * Verify PAN
   * POST /api/users/{id}/verify-pan/
   */
  verifyPAN: async (userId, pan) => {
    try {
      const response = await apiClient.post(`/users/${userId}/verify-pan/`, { pan });
      return extractData(response);
    } catch (error) {
      return handleError(error);
    }
  },

  /**
   * Send Aadhaar OTP
   * POST /api/users/{id}/send-aadhaar-otp/
   */
  sendAadhaarOTP: async (userId, aadhaar) => {
    try {
      const response = await apiClient.post(`/users/${userId}/send-aadhaar-otp/`, { aadhaar });
      return extractData(response);
    } catch (error) {
      return handleError(error);
    }
  },

  /**
   * Verify Aadhaar OTP
   * POST /api/users/{id}/verify-aadhaar-otp/
   */
  verifyAadhaarOTP: async (userId, aadhaar, otp) => {
    try {
      const response = await apiClient.post(`/users/${userId}/verify-aadhaar-otp/`, { aadhaar, otp });
      return extractData(response);
    } catch (error) {
      return handleError(error);
    }
  },

  /**
   * Get Subordinates
   * GET /api/users/subordinates/
   */
  getSubordinates: async () => {
    try {
      const response = await apiClient.get('/users/subordinates/');
      return extractData(response);
    } catch (error) {
      return handleError(error);
    }
  },
};

// ==================== WALLETS APIs ====================

export const walletsAPI = {
  /**
   * Get All Wallets
   * GET /api/wallets/
   */
  getAllWallets: async () => {
    try {
      const response = await apiClient.get('/wallets/');
      return extractData(response);
    } catch (error) {
      return handleError(error);
    }
  },

  /**
   * Get Wallet by Type
   * GET /api/wallets/{type}/
   */
  getWalletByType: async (type) => {
    try {
      const response = await apiClient.get(`/wallets/${type}/`);
      return extractData(response);
    } catch (error) {
      return handleError(error);
    }
  },

  /**
   * Get Wallet History
   * GET /api/wallets/{type}/history/
   */
  getWalletHistory: async (type, params = {}) => {
    try {
      const response = await apiClient.get(`/wallets/${type}/history/`, { params });
      return extractData(response);
    } catch (error) {
      return handleError(error);
    }
  },

  /**
   * Transfer main → BBPS wallet (MPIN required)
   * POST /api/wallets/transfer-to-bbps/
   */
  transferMainToBbps: async ({ amount, mpin }) => {
    try {
      const response = await apiClient.post('/wallets/transfer-to-bbps/', { amount, mpin });
      return extractData(response);
    } catch (error) {
      return handleError(error);
    }
  },
};

// ==================== FUND MANAGEMENT APIs ====================

export const fundManagementAPI = {
  /**
   * Pay-in packages (admin-configured)
   * GET /api/fund-management/pay-in/packages/
   */
  listPayInPackages: async () => {
    try {
      const response = await apiClient.get('/fund-management/pay-in/packages/');
      return extractData(response);
    } catch (error) {
      return handleError(error);
    }
  },

  /**
   * Pay-in fee quote
   * POST /api/fund-management/pay-in/quote/
   */
  payInQuote: async ({ packageId, amount }) => {
    try {
      const response = await apiClient.post('/fund-management/pay-in/quote/', {
        package_id: packageId,
        amount,
      });
      return extractData(response);
    } catch (error) {
      return handleError(error);
    }
  },

  /**
   * Create pay-in order (Razorpay or mock)
   * POST /api/fund-management/pay-in/create-order/
   */
  payInCreateOrder: async ({ packageId, amount, contactId }) => {
    try {
      const response = await apiClient.post('/fund-management/pay-in/create-order/', {
        package_id: packageId,
        amount,
        contact_id: contactId,
      });
      return extractData(response);
    } catch (error) {
      return handleError(error);
    }
  },

  /**
   * Verify Razorpay Checkout response and credit wallet (signature + payment fetch).
   * POST /api/fund-management/pay-in/verify-razorpay/
   */
  payInVerifyRazorpay: async ({
    transactionId,
    razorpayOrderId,
    razorpayPaymentId,
    razorpaySignature,
  }) => {
    try {
      const response = await apiClient.post('/fund-management/pay-in/verify-razorpay/', {
        transaction_id: transactionId,
        razorpay_order_id: razorpayOrderId,
        razorpay_payment_id: razorpayPaymentId,
        razorpay_signature: razorpaySignature,
      });
      return extractData(response);
    } catch (error) {
      return handleError(error);
    }
  },

  /**
   * Payout quote (max eligible + slab hints)
   * GET /api/fund-management/payout/quote/
   */
  getPayoutQuote: async (params = {}) => {
    try {
      const response = await apiClient.get('/fund-management/payout/quote/', { params });
      return extractData(response);
    } catch (error) {
      return handleError(error);
    }
  },

  /**
   * Load Money (legacy immediate success)
   * POST /api/fund-management/load-money/
   */
  loadMoney: async (amount, gateway) => {
    try {
      const response = await apiClient.post('/fund-management/load-money/', {
        amount,
        gateway,
      });
      return extractData(response);
    } catch (error) {
      return handleError(error);
    }
  },

  /**
   * Get Load Money List
   * GET /api/fund-management/load-money/list/
   */
  getLoadMoneyList: async (params = {}) => {
    try {
      const response = await apiClient.get('/fund-management/load-money/list/', { params });
      return extractData(response);
    } catch (error) {
      return handleError(error);
    }
  },

  /**
   * Payout
   * POST /api/fund-management/payout/
   */
  payout: async ({ bankAccountId, amount, mpin, transferMode = 'IMPS', gateway = null }) => {
    try {
      const body = {
        bank_account_id: bankAccountId,
        amount,
        mpin,
        transfer_mode: transferMode,
      };
      if (gateway != null && gateway !== '') {
        body.gateway = gateway;
      }
      const response = await apiClient.post('/fund-management/payout/', body);
      return extractData(response);
    } catch (error) {
      return handleError(error);
    }
  },

  /**
   * Get Payout List
   * GET /api/fund-management/payout/list/
   */
  getPayoutList: async (params = {}) => {
    try {
      const response = await apiClient.get('/fund-management/payout/list/', { params });
      return extractData(response);
    } catch (error) {
      return handleError(error);
    }
  },

  /**
   * Get Gateways
   * GET /api/fund-management/gateways/?type=payment|payout
   */
  getGateways: async (params = {}) => {
    try {
      const response = await apiClient.get('/fund-management/gateways/', { params });
      return extractData(response);
    } catch (error) {
      return handleError(error);
    }
  },

  // ─────────────────────────────────────────────────────────────────────────
  // Package Assignment
  // ─────────────────────────────────────────────────────────────────────────

  /**
   * Get packages assigned to a specific user
   * GET /api/fund-management/packages/user/<userId>/
   */
  getUserPackages: async (userId) => {
    try {
      const response = await apiClient.get(`/fund-management/packages/user/${userId}/`);
      return extractData(response);
    } catch (error) {
      return handleError(error);
    }
  },

  /**
   * Get packages the current user can assign to their downline
   * GET /api/fund-management/packages/assignable/
   */
  getAssignablePackages: async () => {
    try {
      const response = await apiClient.get('/fund-management/packages/assignable/');
      return extractData(response);
    } catch (error) {
      return handleError(error);
    }
  },

  /**
   * Assign a package to a user
   * POST /api/fund-management/packages/assign/
   */
  assignPackageToUser: async (userId, packageId) => {
    try {
      const response = await apiClient.post('/fund-management/packages/assign/', {
        user_id: userId,
        package_id: packageId,
      });
      return extractData(response);
    } catch (error) {
      return handleError(error);
    }
  },

  /**
   * Remove a package assignment from a user
   * POST /api/fund-management/packages/unassign/
   */
  removePackageAssignment: async (userId, packageId) => {
    try {
      const response = await apiClient.post('/fund-management/packages/unassign/', {
        user_id: userId,
        package_id: packageId,
      });
      return extractData(response);
    } catch (error) {
      return handleError(error);
    }
  },
};

// ==================== BBPS APIs ====================

export const bbpsAPI = {
  /**
   * Get Categories
   * GET /api/bbps/categories/
   */
  getCategories: async () => {
    try {
      const response = await apiClient.get('/bbps/categories/');
      return extractData(response);
    } catch (error) {
      return handleError(error);
    }
  },

  /**
   * Get Billers by Category
   * GET /api/bbps/billers/{category}/
   */
  getBillers: async (category) => {
    try {
      const response = await apiClient.get(`/bbps/billers/${category}/`);
      return extractData(response);
    } catch (error) {
      return handleError(error);
    }
  },

  /**
   * Fetch Bill
   * POST /api/bbps/fetch-bill/
   */
  fetchBill: async (billerId, customerParams) => {
    try {
      const response = await apiClient.post('/bbps/fetch-bill/', {
        biller_id: billerId,
        ...customerParams,
      });
      return extractData(response);
    } catch (error) {
      return handleError(error);
    }
  },

  /**
   * Pay Bill
   * POST /api/bbps/pay/
   */
  payBill: async (billId, amount, mpin) => {
    try {
      const response = await apiClient.post('/bbps/pay/', {
        bill_id: billId,
        amount,
        mpin,
      });
      return extractData(response);
    } catch (error) {
      return handleError(error);
    }
  },

  /**
   * Get Bill Payments List
   * GET /api/bbps/payments/
   */
  getBillPayments: async (params = {}) => {
    try {
      const response = await apiClient.get('/bbps/payments/', { params });
      return extractData(response);
    } catch (error) {
      return handleError(error);
    }
  },

  /**
   * Get Bill Payment Detail
   * GET /api/bbps/payments/{id}/
   */
  getBillPaymentDetail: async (paymentId) => {
    try {
      const response = await apiClient.get(`/bbps/payments/${paymentId}/`);
      return extractData(response);
    } catch (error) {
      return handleError(error);
    }
  },
};

// ==================== CONTACTS APIs ====================

export const contactsAPI = {
  /**
   * List Contacts
   * GET /api/contacts/
   */
  listContacts: async (params = {}) => {
    try {
      const response = await apiClient.get('/contacts/', { params });
      return extractData(response);
    } catch (error) {
      return handleError(error);
    }
  },

  /**
   * Create Contact
   * POST /api/contacts/
   */
  createContact: async (contactData) => {
    try {
      const response = await apiClient.post('/contacts/', contactData);
      return extractData(response);
    } catch (error) {
      return handleError(error);
    }
  },

  /**
   * Get Contact Detail
   * GET /api/contacts/{id}/
   */
  getContactDetail: async (contactId) => {
    try {
      const response = await apiClient.get(`/contacts/${contactId}/`);
      return extractData(response);
    } catch (error) {
      return handleError(error);
    }
  },

  /**
   * Update Contact
   * PUT /api/contacts/{id}/
   */
  updateContact: async (contactId, contactData) => {
    try {
      const response = await apiClient.put(`/contacts/${contactId}/`, contactData);
      return extractData(response);
    } catch (error) {
      return handleError(error);
    }
  },

  /**
   * Partial Update Contact
   * PATCH /api/contacts/{id}/
   */
  partialUpdateContact: async (contactId, contactData) => {
    try {
      const response = await apiClient.patch(`/contacts/${contactId}/`, contactData);
      return extractData(response);
    } catch (error) {
      return handleError(error);
    }
  },

  /**
   * Delete Contact
   * DELETE /api/contacts/{id}/
   */
  deleteContact: async (contactId) => {
    try {
      const response = await apiClient.delete(`/contacts/${contactId}/`);
      return extractData(response);
    } catch (error) {
      return handleError(error);
    }
  },

  /**
   * Search Contact by Phone
   * GET /api/contacts/search/?phone={phone}
   */
  searchContactByPhone: async (phone) => {
    try {
      const digits = String(phone ?? '')
        .replace(/\D/g, '')
        .slice(0, 10);
      const response = await apiClient.get('/contacts/search/', { params: { phone: digits } });
      return extractData(response);
    } catch (error) {
      return handleError(error);
    }
  },

  /**
   * Search contact for transactions: phone (10 digits) or name (unique match).
   * GET /api/contacts/search/?phone=... OR ?name=...
   */
  /**
   * Typeahead: partial name or phone match (min 2 chars).
   * GET /api/contacts/suggest/?q=...
   */
  suggestContacts: async (q) => {
    try {
      const trimmed = String(q ?? '').trim();
      const response = await apiClient.get('/contacts/suggest/', {
        params: { q: trimmed },
      });
      return extractData(response);
    } catch (error) {
      return handleError(error);
    }
  },

  searchContactForTransaction: async ({ phone, name } = {}) => {
    try {
      const digits = String(phone ?? '')
        .replace(/\D/g, '')
        .slice(0, 10);
      const params = {};
      if (digits.length === 10) {
        params.phone = digits;
      } else if (name != null && String(name).trim().length >= 2) {
        params.name = String(name).trim();
      } else {
        return {
          success: false,
          message: 'Enter a 10-digit phone number or at least 2 characters of the contact name',
          errors: [],
        };
      }
      const response = await apiClient.get('/contacts/search/', { params });
      return extractData(response);
    } catch (error) {
      return handleError(error);
    }
  },
};

// ==================== BANK ACCOUNTS APIs ====================

export const bankAccountsAPI = {
  /**
   * List Bank Accounts
   * GET /api/bank-accounts/
   */
  listBankAccounts: async (params = {}) => {
    try {
      const response = await apiClient.get('/bank-accounts/', { params });
      return extractData(response);
    } catch (error) {
      return handleError(error);
    }
  },

  /**
   * Validate Bank Account
   * POST /api/bank-accounts/validate/
   */
  validateBankAccount: async (accountNumber, ifsc) => {
    try {
      const response = await apiClient.post('/bank-accounts/validate/', {
        account_number: accountNumber,
        ifsc,
      });
      return extractData(response);
    } catch (error) {
      return handleError(error);
    }
  },

  /**
   * Create Bank Account
   * POST /api/bank-accounts/
   */
  createBankAccount: async (bankAccountData) => {
    try {
      const response = await apiClient.post('/bank-accounts/', bankAccountData);
      return extractData(response);
    } catch (error) {
      return handleError(error);
    }
  },

  /**
   * Get Bank Account Detail
   * GET /api/bank-accounts/{id}/
   */
  getBankAccountDetail: async (bankAccountId) => {
    try {
      const response = await apiClient.get(`/bank-accounts/${bankAccountId}/`);
      return extractData(response);
    } catch (error) {
      return handleError(error);
    }
  },

  /**
   * Update Bank Account
   * PUT /api/bank-accounts/{id}/
   */
  updateBankAccount: async (bankAccountId, bankAccountData) => {
    try {
      const response = await apiClient.put(`/bank-accounts/${bankAccountId}/`, bankAccountData);
      return extractData(response);
    } catch (error) {
      return handleError(error);
    }
  },

  /**
   * Delete Bank Account
   * DELETE /api/bank-accounts/{id}/
   */
  deleteBankAccount: async (bankAccountId) => {
    try {
      const response = await apiClient.delete(`/bank-accounts/${bankAccountId}/`);
      return extractData(response);
    } catch (error) {
      return handleError(error);
    }
  },
};

// ==================== TRANSACTIONS APIs ====================

export const transactionsAPI = {
  /**
   * List Transactions
   * GET /api/transactions/
   */
  listTransactions: async (params = {}) => {
    try {
      const response = await apiClient.get('/transactions/', { params });
      return extractData(response);
    } catch (error) {
      return handleError(error);
    }
  },

  /**
   * Get Transaction Detail
   * GET /api/transactions/{id}/
   */
  getTransactionDetail: async (transactionId) => {
    try {
      const response = await apiClient.get(`/transactions/${transactionId}/`);
      return extractData(response);
    } catch (error) {
      return handleError(error);
    }
  },
};

// ==================== PASSBOOK APIs ====================

export const passbookAPI = {
  /**
   * Get Passbook Entries
   * GET /api/passbook/
   */
  getPassbookEntries: async (params = {}) => {
    try {
      const response = await apiClient.get('/passbook/', { params });
      return extractData(response);
    } catch (error) {
      return handleError(error);
    }
  },
};

// ==================== REPORTS APIs ====================

export const reportsAPI = {
  /**
   * Get Pay In Report
   * GET /api/reports/payin/
   */
  getPayInReport: async (params = {}) => {
    try {
      const response = await apiClient.get('/reports/payin/', { params });
      return extractData(response);
    } catch (error) {
      return handleError(error);
    }
  },

  /**
   * Get Pay Out Report
   * GET /api/reports/payout/
   */
  getPayOutReport: async (params = {}) => {
    try {
      const response = await apiClient.get('/reports/payout/', { params });
      return extractData(response);
    } catch (error) {
      return handleError(error);
    }
  },

  /**
   * Get BBPS Report
   * GET /api/reports/bbps/
   */
  getBBPSReport: async (params = {}) => {
    try {
      const response = await apiClient.get('/reports/bbps/', { params });
      return extractData(response);
    } catch (error) {
      return handleError(error);
    }
  },

  /**
   * Get Commission Report
   * GET /api/reports/commission/
   */
  getCommissionReport: async (params = {}) => {
    try {
      const response = await apiClient.get('/reports/commission/', { params });
      return extractData(response);
    } catch (error) {
      return handleError(error);
    }
  },

  /**
   * Analytics summary grouped by gateway + interval
   * GET /api/reports/analytics/summary/
   */
  getAnalyticsSummary: async (params = {}) => {
    try {
      const response = await apiClient.get('/reports/analytics/summary/', { params });
      return extractData(response);
    } catch (error) {
      return handleError(error);
    }
  },

  /** Download CSV (blob). Caller should create object URL or save file. */
  downloadReportCsv: async (path, params = {}) => {
    try {
      const response = await apiClient.get(path, {
        params,
        responseType: 'blob',
      });
      return { success: true, blob: response.data, filename: path.split('/').filter(Boolean).join('_') };
    } catch (error) {
      return handleError(error);
    }
  },
};

// ==================== ADMIN APIs ====================

export const adminAPI = {
  /**
   * List Announcements
   * GET /api/admin/announcements/
   */
  listAnnouncements: async (params = {}) => {
    try {
      const response = await apiClient.get('/admin/announcements/', { params });
      return extractData(response);
    } catch (error) {
      return handleError(error);
    }
  },

  /**
   * Create Announcement
   * POST /api/admin/announcements/
   */
  createAnnouncement: async (announcementData) => {
    try {
      const response = await apiClient.post(
        '/admin/announcements/',
        announcementData,
        formDataRequestConfig(announcementData)
      );
      return extractData(response);
    } catch (error) {
      return handleError(error);
    }
  },

  /**
   * Get Announcement Detail
   * GET /api/admin/announcements/{id}/
   */
  getAnnouncementDetail: async (announcementId) => {
    try {
      const response = await apiClient.get(`/admin/announcements/${announcementId}/`);
      return extractData(response);
    } catch (error) {
      return handleError(error);
    }
  },

  /**
   * Update Announcement
   * PUT /api/admin/announcements/{id}/
   */
  updateAnnouncement: async (announcementId, announcementData) => {
    try {
      const response = await apiClient.put(
        `/admin/announcements/${announcementId}/`,
        announcementData,
        formDataRequestConfig(announcementData)
      );
      return extractData(response);
    } catch (error) {
      return handleError(error);
    }
  },

  /**
   * PATCH /api/admin/announcements/{id}/ (e.g. is_active)
   */
  patchAnnouncement: async (announcementId, partialData) => {
    try {
      const response = await apiClient.patch(
        `/admin/announcements/${announcementId}/`,
        partialData
      );
      return extractData(response);
    } catch (error) {
      return handleError(error);
    }
  },

  /**
   * Delete Announcement
   * DELETE /api/admin/announcements/{id}/
   */
  deleteAnnouncement: async (announcementId) => {
    try {
      const response = await apiClient.delete(`/admin/announcements/${announcementId}/`);
      return extractData(response);
    } catch (error) {
      return handleError(error);
    }
  },

  /**
   * List Payment Gateways
   * GET /api/admin/gateways/
   */
  listPaymentGateways: async () => {
    try {
      const response = await apiClient.get('/admin/gateways/');
      return extractData(response);
    } catch (error) {
      return handleError(error);
    }
  },

  /**
   * Create Payment Gateway
   * POST /api/admin/gateways/
   */
  createPaymentGateway: async (gatewayData) => {
    try {
      const response = await apiClient.post('/admin/gateways/', gatewayData);
      return extractData(response);
    } catch (error) {
      return handleError(error);
    }
  },

  /**
   * Get Payment Gateway Detail
   * GET /api/admin/gateways/{id}/
   */
  getPaymentGatewayDetail: async (gatewayId) => {
    try {
      const response = await apiClient.get(`/admin/gateways/${gatewayId}/`);
      return extractData(response);
    } catch (error) {
      return handleError(error);
    }
  },

  /**
   * Update Payment Gateway
   * PUT /api/admin/gateways/{id}/
   */
  updatePaymentGateway: async (gatewayId, gatewayData) => {
    try {
      const response = await apiClient.put(`/admin/gateways/${gatewayId}/`, gatewayData);
      return extractData(response);
    } catch (error) {
      return handleError(error);
    }
  },

  /**
   * Delete Payment Gateway
   * DELETE /api/admin/gateways/{id}/
   */
  deletePaymentGateway: async (gatewayId) => {
    try {
      const response = await apiClient.delete(`/admin/gateways/${gatewayId}/`);
      return extractData(response);
    } catch (error) {
      return handleError(error);
    }
  },

  /**
   * Toggle Payment Gateway Status
   * POST /api/admin/gateways/{id}/toggle-status/
   */
  togglePaymentGatewayStatus: async (gatewayId) => {
    try {
      const response = await apiClient.post(`/admin/gateways/${gatewayId}/toggle-status/`);
      return extractData(response);
    } catch (error) {
      return handleError(error);
    }
  },

  /**
   * List Pay-in Packages (Admin)
   * GET /api/admin/pay-in-packages/
   */
  listPayInPackages: async (params = {}) => {
    try {
      const response = await apiClient.get('/admin/pay-in-packages/', { params });
      return extractData(response);
    } catch (error) {
      return handleError(error);
    }
  },

  /**
   * Create Pay-in Package (Admin)
   * POST /api/admin/pay-in-packages/
   */
  createPayInPackage: async (payload) => {
    try {
      const response = await apiClient.post('/admin/pay-in-packages/', payload);
      return extractData(response);
    } catch (error) {
      return handleError(error);
    }
  },

  /**
   * Update Pay-in Package (Admin)
   * PUT /api/admin/pay-in-packages/{id}/
   */
  updatePayInPackage: async (packageId, payload) => {
    try {
      const response = await apiClient.put(`/admin/pay-in-packages/${packageId}/`, payload);
      return extractData(response);
    } catch (error) {
      return handleError(error);
    }
  },

  /**
   * Delete Pay-in Package (Admin)
   * DELETE /api/admin/pay-in-packages/{id}/
   */
  deletePayInPackage: async (packageId) => {
    try {
      const response = await apiClient.delete(`/admin/pay-in-packages/${packageId}/`);
      return extractData(response);
    } catch (error) {
      return handleError(error);
    }
  },

  /**
   * Preview Pay-in Package settlement for amount (Admin)
   * POST /api/admin/pay-in-packages/{id}/preview/
   */
  previewPayInPackage: async (packageId, amount) => {
    try {
      const response = await apiClient.post(`/admin/pay-in-packages/${packageId}/preview/`, { amount });
      return extractData(response);
    } catch (error) {
      return handleError(error);
    }
  },

  /**
   * Get payout slab config (Admin)
   * GET /api/admin/payout-slab-config/
   */
  getPayoutSlabConfig: async () => {
    try {
      const response = await apiClient.get('/admin/payout-slab-config/');
      return extractData(response);
    } catch (error) {
      return handleError(error);
    }
  },

  /**
   * Update payout slab config (Admin)
   * PUT /api/admin/payout-slab-config/
   */
  updatePayoutSlabConfig: async (payload) => {
    try {
      const response = await apiClient.put('/admin/payout-slab-config/', payload);
      return extractData(response);
    } catch (error) {
      return handleError(error);
    }
  },

  /**
   * List API Masters
   * GET /api/integrations/api-masters/
   */
  listApiMasters: async (params = {}) => {
    try {
      const response = await apiClient.get('/integrations/api-masters/', { params });
      return extractData(response);
    } catch (error) {
      return handleError(error);
    }
  },

  /**
   * Create API Master
   * POST /api/integrations/api-masters/
   */
  createApiMaster: async (payload) => {
    try {
      const response = await apiClient.post('/integrations/api-masters/', payload);
      return extractData(response);
    } catch (error) {
      return handleError(error);
    }
  },

  /**
   * Update API Master
   * PUT /api/integrations/api-masters/{id}/
   */
  updateApiMaster: async (id, payload) => {
    try {
      const response = await apiClient.put(`/integrations/api-masters/${id}/`, payload);
      return extractData(response);
    } catch (error) {
      return handleError(error);
    }
  },

  /**
   * Delete API Master
   * DELETE /api/integrations/api-masters/{id}/
   */
  deleteApiMaster: async (id) => {
    try {
      const response = await apiClient.delete(`/integrations/api-masters/${id}/`);
      return extractData(response);
    } catch (error) {
      return handleError(error);
    }
  },

  /**
   * Test API Master connection
   * POST /api/integrations/api-masters/{id}/test_connection/
   */
  testApiMasterConnection: async (id) => {
    try {
      const response = await apiClient.post(`/integrations/api-masters/${id}/test_connection/`);
      return extractData(response);
    } catch (error) {
      return handleError(error);
    }
  },

  /**
   * Clone API Master
   * POST /api/integrations/api-masters/{id}/clone/
   */
  cloneApiMaster: async (id) => {
    try {
      const response = await apiClient.post(`/integrations/api-masters/${id}/clone/`);
      return extractData(response);
    } catch (error) {
      return handleError(error);
    }
  },

  // ─────────────────────────────────────────────────────────────────────────
  // Package Assignment (Admin)
  // ─────────────────────────────────────────────────────────────────────────

  /**
   * Set default package (Admin only)
   * POST /api/fund-management/packages/set-default/
   */
  setDefaultPackage: async (packageId) => {
    try {
      const response = await apiClient.post('/fund-management/packages/set-default/', {
        package_id: packageId,
      });
      return extractData(response);
    } catch (error) {
      return handleError(error);
    }
  },

  /**
   * Clear default package (Admin only)
   * POST /api/fund-management/packages/clear-default/
   */
  clearDefaultPackage: async () => {
    try {
      const response = await apiClient.post('/fund-management/packages/clear-default/');
      return extractData(response);
    } catch (error) {
      return handleError(error);
    }
  },
};

// Export default API client for custom requests
export default apiClient;
