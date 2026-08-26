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
  // Must exceed Fingpay client timeout (~180s) and stay under gunicorn worker timeout (240s).
  timeout: 220000,
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
        (typeof detail === 'object' ? (detail?.message || detail?.string) : null) ||
        (typeof data?.message === 'object' ? (data.message?.message || data.message?.string) : data?.message) ||
        error.message ||
        'Request failed',
      code: (typeof detail === 'object' ? detail?.code : null) || data?.code,
      errors: data?.errors,
      data: data?.data ?? null,
    };
  }
};

export const aepsAPI = {
  meStatus: () => wrap(client.get('/aeps/me/status/')),
  requestAccess: (reason = '') => wrap(client.post('/aeps/access-requests/', { reason })),
  getOnboardingForm: () => wrap(client.get('/aeps/onboarding/draft/')),
  saveOnboardingDraft: (payload) => wrap(client.post('/aeps/onboarding/draft/', { payload })),
  getOnboardingImage: (field) =>
    wrap(client.get(`/aeps/onboarding/image/${encodeURIComponent(field)}/`)),
  submitOnboarding: (body) => wrap(client.post('/aeps/onboarding/submit/', body)),
  registerDevice: (device_imei, scanner_serial = '') =>
    wrap(client.post('/aeps/device/register/', { device_imei, scanner_serial })),
  ekycStart: (body) => wrap(client.post('/aeps/ekyc/start/', body)),
  ekycOtp: (otp) => wrap(client.post('/aeps/ekyc/otp/', { otp })),
  ekycResend: () => wrap(client.post('/aeps/ekyc/resend/', {})),
  ekycStatus: (kycType = 'EKYC') => wrap(client.post('/aeps/ekyc/status/', { kycType })),
  ekycBiometric: (body) => wrap(client.post('/aeps/ekyc/biometric/', body)),
  complete2fa: (body) => wrap(client.post('/aeps/2fa/complete/', body)),
  listBanks: (type = 'aeps', refresh = false) =>
    wrap(client.get('/aeps/banks/', { params: { type, ...(refresh ? { refresh: 1 } : {}) } })),
  syncBanks: () => wrap(client.post('/aeps/banks/sync/')),
  transactions: (params) => wrap(client.get('/aeps/transactions/', { params })),
  cashWithdrawal: (body) => wrap(client.post('/aeps/transactions/cw/', body)),
  balanceEnquiry: (body) => wrap(client.post('/aeps/transactions/be/', body)),
  miniStatement: (body) => wrap(client.post('/aeps/transactions/ms/', body)),
  aadhaarPay: (body) => wrap(client.post('/aeps/transactions/ap/', body)),
  cashDeposit: (body) => wrap(client.post('/aeps/transactions/cd/', body)),
  cashDepositOtpGenerate: (body) => wrap(client.post('/aeps/transactions/cd/otp/generate/', body)),
  cashDepositOtpValidate: (body) => wrap(client.post('/aeps/transactions/cd/otp/validate/', body)),
  cashDepositOtpSubmit: (body) => wrap(client.post('/aeps/transactions/cd/otp/submit/', body)),
  statusCheck: (merchantTranId, body = {}) =>
    wrap(client.post(`/aeps/transactions/${encodeURIComponent(merchantTranId)}/status-check/`, body)),
  acknowledge: (merchantTranId, body = {}) =>
    wrap(client.post(`/aeps/transactions/${encodeURIComponent(merchantTranId)}/acknowledge/`, body)),
  reportsSummary: (params) => wrap(client.get('/aeps/reports/summary/', { params })),
  adminProviderGet: (environment) =>
    wrap(client.get('/aeps/admin/provider-config/', { params: environment ? { environment } : undefined })),
  adminProviderSave: (body) => wrap(client.patch('/aeps/admin/provider-config/', body)),
  adminProviderTest: () => wrap(client.post('/aeps/admin/provider-config/test/')),
  adminDebugLogs: (params) => wrap(client.get('/aeps/admin/debug-logs/', { params })),
  adminDebugLogDetail: (id) => wrap(client.get(`/aeps/admin/debug-logs/${id}/`)),
  adminEnable: (user_id) => wrap(client.post('/aeps/admin/entitlements/enable/', { user_id })),
  adminDisable: (user_id, reason = '') =>
    wrap(client.post('/aeps/admin/entitlements/disable/', { user_id, reason })),
  adminUserEntitlement: (userId) => wrap(client.get(`/aeps/admin/entitlements/user/${userId}/`)),
  adminAccessRequests: (status = 'pending') =>
    wrap(client.get('/aeps/admin/access-requests/', { params: { status } })),
  adminDecideRequest: (id, decision, notes = '') =>
    wrap(client.post(`/aeps/admin/access-requests/${id}/decide/`, { decision, notes })),
  adminMerchants: (params) => wrap(client.get('/aeps/admin/merchants/', { params })),
  adminMerchantDetail: (id) => wrap(client.get(`/aeps/admin/merchants/${id}/`)),
  adminMerchantResetPin: (id, body = {}) => wrap(client.post(`/aeps/admin/merchants/${id}/reset-pin/`, body)),
  adminRecon: () => wrap(client.get('/aeps/admin/recon/')),
};

export default aepsAPI;
