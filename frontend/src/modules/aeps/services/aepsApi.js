/**
 * AEPS API client — isolated from shared ledger/reports.
 */
import axios from 'axios';

const normalizeApiBaseUrl = (rawBaseUrl) => {
  const fallback = '/api';
  if (!rawBaseUrl) return fallback;
  const trimmed = rawBaseUrl.trim().replace(/\/+$/, '');
  if (!trimmed) return fallback;
  if (trimmed.endsWith('/api')) return trimmed;
  return `${trimmed}/api`;
};

const client = axios.create({
  baseURL: normalizeApiBaseUrl(process.env.REACT_APP_API_BASE_URL),
  timeout: 200000,
});

client.interceptors.request.use((config) => {
  const token = localStorage.getItem('access_token');
  if (token) {
    config.headers = config.headers || {};
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

const wrap = async (promise) => {
  try {
    const response = await promise;
    return { success: true, data: response.data?.data ?? response.data, message: response.data?.message };
  } catch (error) {
    const data = error.response?.data;
    const detail = data?.errors?.detail || data?.detail;
    return {
      success: false,
      message:
        (typeof detail === 'object' ? detail?.message : null) ||
        data?.message ||
        error.message ||
        'Request failed',
      code: (typeof detail === 'object' ? detail?.code : null) || data?.code,
      errors: data?.errors,
    };
  }
};

export const aepsAPI = {
  meStatus: () => wrap(client.get('/aeps/me/status/')),
  requestAccess: (reason = '') => wrap(client.post('/aeps/access-requests/', { reason })),
  saveOnboardingDraft: (payload) => wrap(client.post('/aeps/onboarding/draft/', { payload })),
  submitOnboarding: (body) => wrap(client.post('/aeps/onboarding/submit/', body)),
  registerDevice: (device_imei) => wrap(client.post('/aeps/device/register/', { device_imei })),
  ekycStart: (body) => wrap(client.post('/aeps/ekyc/start/', body)),
  ekycOtp: (otp) => wrap(client.post('/aeps/ekyc/otp/', { otp })),
  ekycBiometric: (body) => wrap(client.post('/aeps/ekyc/biometric/', body)),
  complete2fa: (body) => wrap(client.post('/aeps/2fa/complete/', body)),
  listBanks: (type = 'aeps') => wrap(client.get('/aeps/banks/', { params: { type } })),
  syncBanks: () => wrap(client.post('/aeps/banks/sync/')),
  transactions: (params) => wrap(client.get('/aeps/transactions/', { params })),
  cashWithdrawal: (body) => wrap(client.post('/aeps/transactions/cw/', body)),
  balanceEnquiry: (body) => wrap(client.post('/aeps/transactions/be/', body)),
  miniStatement: (body) => wrap(client.post('/aeps/transactions/ms/', body)),
  aadhaarPay: (body) => wrap(client.post('/aeps/transactions/ap/', body)),
  cashDeposit: (body) => wrap(client.post('/aeps/transactions/cd/', body)),
  statusCheck: (merchantTranId) =>
    wrap(client.post(`/aeps/transactions/${encodeURIComponent(merchantTranId)}/status-check/`)),
  reportsSummary: (params) => wrap(client.get('/aeps/reports/summary/', { params })),
  adminProviderGet: () => wrap(client.get('/aeps/admin/provider-config/')),
  adminProviderSave: (body) => wrap(client.patch('/aeps/admin/provider-config/', body)),
  adminEnable: (user_id) => wrap(client.post('/aeps/admin/entitlements/enable/', { user_id })),
  adminDisable: (user_id, reason = '') =>
    wrap(client.post('/aeps/admin/entitlements/disable/', { user_id, reason })),
  adminUserEntitlement: (userId) => wrap(client.get(`/aeps/admin/entitlements/user/${userId}/`)),
  adminAccessRequests: (status = 'pending') =>
    wrap(client.get('/aeps/admin/access-requests/', { params: { status } })),
  adminDecideRequest: (id, decision, notes = '') =>
    wrap(client.post(`/aeps/admin/access-requests/${id}/decide/`, { decision, notes })),
  adminMerchants: (params) => wrap(client.get('/aeps/admin/merchants/', { params })),
  adminRecon: () => wrap(client.get('/aeps/admin/recon/')),
};

export default aepsAPI;
