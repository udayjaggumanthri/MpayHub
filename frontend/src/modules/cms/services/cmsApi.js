/**
 * Uber CMS API client — isolated from AEPS and shared ledger reports.
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
  timeout: 60000,
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
        (typeof detail === 'object' ? detail?.message || detail?.string : null) ||
        (typeof data?.message === 'object' ? data.message?.message || data.message?.string : data?.message) ||
        error.message ||
        'Request failed',
      code: (typeof detail === 'object' ? detail?.code : null) || data?.code,
      errors: data?.errors,
      data: data?.data ?? null,
    };
  }
};

export const cmsAPI = {
  meStatus: () => wrap(client.get('/cms/me/status/')),
  launch: (body) => wrap(client.post('/cms/launch/', body)),
  wallet: () => wrap(client.get('/cms/wallet/')),
  fundWallet: (amount) => wrap(client.post('/cms/wallet/fund/', { amount })),
  transactions: (params) => wrap(client.get('/cms/transactions/', { params })),
  reportsSummary: (params) => wrap(client.get('/cms/reports/summary/', { params })),
  exportCsv: async (params) => {
    try {
      const response = await client.get('/cms/reports/export.csv', {
        params,
        responseType: 'blob',
      });
      return { success: true, data: response.data };
    } catch (error) {
      return { success: false, message: error.message || 'Export failed' };
    }
  },
  adminProviderGet: () => wrap(client.get('/cms/admin/provider-config/')),
  adminProviderSave: (body) => wrap(client.patch('/cms/admin/provider-config/', body)),
  adminEnable: (user_id) => wrap(client.post('/cms/admin/entitlements/enable/', { user_id })),
  adminDisable: (user_id, reason = '') =>
    wrap(client.post('/cms/admin/entitlements/disable/', { user_id, reason })),
  adminUserEntitlement: (userId) => wrap(client.get(`/cms/admin/entitlements/user/${userId}/`)),
  adminAgents: () => wrap(client.get('/cms/admin/agents/')),
  adminResetPin: (agentId) => wrap(client.post(`/cms/admin/agents/${agentId}/reset-pin/`)),
  adminAuditLogs: () => wrap(client.get('/cms/admin/audit-logs/')),
};

export default cmsAPI;
