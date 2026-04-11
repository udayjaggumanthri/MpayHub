import React, { useEffect, useMemo, useState } from 'react';
import Card from '../common/Card';
import Input from '../common/Input';
import Button from '../common/Button';
import { adminAPI } from '../../services/api';
import { FaPlus, FaPenToSquare, FaTrash, FaXmark, FaPlug, FaPowerOff } from 'react-icons/fa6';

const parseList = (result) => {
  const d = result?.data;
  if (!d) return [];
  if (Array.isArray(d)) return d;
  if (Array.isArray(d.results)) return d.results;
  return [];
};

const authTypes = ['api_key', 'bearer', 'basic', 'oauth2', 'custom'];
const statusOptions = ['active', 'inactive', 'down', 'sandbox'];
const kycServiceOptions = [
  { code: 'aadhaar_ekyc', name: 'Aadhaar eKYC' },
  { code: 'pan_verify', name: 'PAN Verification' },
];

const APIMasterManagement = () => {
  const [rows, setRows] = useState([]);
  const [activeModule, setActiveModule] = useState('kyc');
  const [loading, setLoading] = useState(false);
  const [showModal, setShowModal] = useState(false);
  const [editing, setEditing] = useState(null);
  const [feedback, setFeedback] = useState('');
  const [feedbackType, setFeedbackType] = useState('ok');
  const [form, setForm] = useState({
    provider_code: 'aadhaar_ekyc',
    provider_name: 'Aadhaar eKYC',
    provider_type: 'kyc',
    base_url: '',
    auth_type: 'api_key',
    status: 'inactive',
    priority: '0',
    is_default: false,
    supports_webhook: false,
    webhook_path: '',
    config_json_text: '{}',
    secrets: [{ key: '', value: '', maskedPreview: '' }],
  });

  const moduleRows = useMemo(
    () => rows.filter((row) => (row.provider_type || '').toLowerCase() === activeModule),
    [rows, activeModule]
  );
  const kycCount = rows.filter((r) => r.provider_type === 'kyc').length;
  const paymentCount = rows.filter((r) => r.provider_type === 'payments').length;

  const loadRows = async () => {
    setLoading(true);
    const result = await adminAPI.listApiMasters();
    setLoading(false);
    if (!result.success) {
      setFeedbackType('err');
      setFeedback(result.message || 'Could not load API masters');
      return;
    }
    setRows(parseList(result));
  };

  useEffect(() => {
    loadRows();
  }, []);

  const resetForm = (module = activeModule) => {
    if (module === 'kyc') {
      setForm({
        provider_code: 'aadhaar_ekyc',
        provider_name: 'Aadhaar eKYC',
        provider_type: 'kyc',
        base_url: '',
        auth_type: 'api_key',
        status: 'inactive',
        priority: '0',
        is_default: false,
        supports_webhook: false,
        webhook_path: '',
        config_json_text: '{}',
        secrets: [{ key: '', value: '', maskedPreview: '' }],
      });
      return;
    }
    setForm({
      provider_code: 'razorpay',
      provider_name: 'Razorpay',
      provider_type: 'payments',
      base_url: 'https://api.razorpay.com',
      auth_type: 'api_key',
      status: 'inactive',
      priority: '0',
      is_default: false,
      supports_webhook: false,
      webhook_path: '',
      config_json_text: '{}',
      secrets: [
        { key: 'key_id', value: '', maskedPreview: '' },
        { key: 'key_secret', value: '', maskedPreview: '' },
      ],
    });
  };

  const openCreate = () => {
    setEditing(null);
    resetForm(activeModule);
    setShowModal(true);
  };

  const openEdit = (row) => {
    setEditing(row);
    const masked =
      row.secrets_masked && typeof row.secrets_masked === 'object' && !Array.isArray(row.secrets_masked)
        ? row.secrets_masked
        : {};
    const maskedKeys = Object.keys(masked);
    let secretRows;
    if (maskedKeys.length > 0) {
      secretRows = maskedKeys.map((k) => ({
        key: k,
        value: '',
        maskedPreview: masked[k] || '••••',
      }));
    } else if ((row.provider_type || '').toLowerCase() === 'payments') {
      secretRows = [
        { key: 'key_id', value: '', maskedPreview: '' },
        { key: 'key_secret', value: '', maskedPreview: '' },
      ];
    } else {
      secretRows = [{ key: '', value: '', maskedPreview: '' }];
    }
    setForm({
      provider_code: row.provider_code || '',
      provider_name: row.provider_name || '',
      provider_type: row.provider_type || activeModule,
      base_url: row.base_url || '',
      auth_type: row.auth_type || 'api_key',
      status: row.status || 'inactive',
      priority: String(row.priority ?? 0),
      is_default: Boolean(row.is_default),
      supports_webhook: Boolean(row.supports_webhook),
      webhook_path: row.webhook_path || '',
      config_json_text: JSON.stringify(row.config_json || {}, null, 2),
      secrets: secretRows,
    });
    setShowModal(true);
  };

  /** Only non-empty values; on edit, omit blank values so existing secrets are not wiped. */
  const buildSecretsPayload = () => {
    const out = {};
    for (const entry of form.secrets) {
      const key = String(entry.key || '').trim();
      if (!key) continue;
      const val = String(entry.value ?? '').trim();
      if (val === '') continue;
      out[key] = val;
    }
    return out;
  };

  const saveForm = async (e) => {
    e.preventDefault();
    if (!form.provider_code || !form.provider_name) {
      alert('Provider code and provider name are required');
      return;
    }
    let configJson = {};
    try {
      configJson = form.config_json_text ? JSON.parse(form.config_json_text) : {};
    } catch {
      alert('config_json must be valid JSON');
      return;
    }

    const payload = {
      provider_code: form.provider_code.trim(),
      provider_name: form.provider_name.trim(),
      provider_type: activeModule,
      base_url: form.base_url.trim(),
      auth_type: form.auth_type,
      status: form.status,
      priority: Number(form.priority || 0),
      is_default: form.is_default,
      supports_webhook: form.supports_webhook,
      webhook_path: form.webhook_path.trim(),
      config_json: configJson,
    };
    const secretsPayload = buildSecretsPayload();
    if (Object.keys(secretsPayload).length > 0) payload.secrets = secretsPayload;

    setLoading(true);
    const result = editing
      ? await adminAPI.updateApiMaster(editing.id, payload)
      : await adminAPI.createApiMaster(payload);
    setLoading(false);
    if (!result.success) {
      setFeedbackType('err');
      setFeedback(result.message || 'Save failed');
      return;
    }
    setShowModal(false);
    setEditing(null);
    setFeedbackType('ok');
    setFeedback(editing ? 'API config updated' : 'API config created');
    await loadRows();
  };

  const deleteRow = async (id) => {
    if (!window.confirm('Delete this API config?')) return;
    setLoading(true);
    const result = await adminAPI.deleteApiMaster(id);
    setLoading(false);
    if (!result.success) {
      setFeedbackType('err');
      setFeedback(result.message || 'Delete failed');
      return;
    }
    setFeedbackType('ok');
    setFeedback('API config deleted');
    await loadRows();
  };

  const testConnection = async (id) => {
    setLoading(true);
    const result = await adminAPI.testApiMasterConnection(id);
    setLoading(false);
    setFeedbackType(result.success ? 'ok' : 'err');
    const code = result.data?.status_code ? ` (HTTP ${result.data.status_code})` : '';
    let msg = `${result.message || 'Test completed'}${code}`;
    if (result.success && result.data?.credentials_from_env_fallback) {
      msg +=
        ' — Warning: Test used RAZORPAY_* from server .env, not from saved API Master secrets. Fix key_id/key_secret here (see yellow note) or empty .env to match how you want pay-in to run.';
    }
    setFeedback(msg);
  };

  const toggleStatus = async (row) => {
    const nextStatus = row.status === 'active' ? 'inactive' : 'active';
    setLoading(true);
    const result = await adminAPI.updateApiMaster(row.id, { status: nextStatus });
    setLoading(false);
    if (!result.success) {
      setFeedbackType('err');
      setFeedback(result.message || 'Could not update status');
      return;
    }
    setFeedbackType('ok');
    setFeedback(`Status changed to ${nextStatus}`);
    await loadRows();
  };

  const updateSecret = (index, patch) => {
    setForm((prev) => {
      const secrets = [...prev.secrets];
      secrets[index] = { ...secrets[index], ...patch };
      return { ...prev, secrets };
    });
  };

  const onKycServiceChange = (value) => {
    const selected = kycServiceOptions.find((s) => s.code === value);
    setForm((prev) => ({
      ...prev,
      provider_code: value,
      provider_name: selected?.name || prev.provider_name,
    }));
  };

  return (
    <div className="max-w-7xl mx-auto space-y-6 px-4 sm:px-0">
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-2xl sm:text-3xl font-bold text-gray-900">API Master Management</h1>
          <p className="mt-1 sm:mt-2 text-sm sm:text-base text-gray-600">
            Two enterprise modules: KYC APIs (Aadhaar, PAN) and Payment Gateway APIs.
          </p>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <button
          type="button"
          onClick={() => setActiveModule('kyc')}
          className={`text-left p-4 rounded-xl border ${
            activeModule === 'kyc' ? 'border-blue-500 bg-blue-50' : 'border-gray-200 bg-white'
          }`}
        >
          <p className="font-semibold text-gray-900">KYC APIs</p>
          <p className="text-sm text-gray-600">Aadhaar + PAN integrations</p>
          <p className="text-xs text-blue-700 mt-1">{kycCount} configured</p>
        </button>
        <button
          type="button"
          onClick={() => setActiveModule('payments')}
          className={`text-left p-4 rounded-xl border ${
            activeModule === 'payments' ? 'border-blue-500 bg-blue-50' : 'border-gray-200 bg-white'
          }`}
        >
          <p className="font-semibold text-gray-900">Payment Gateways</p>
          <p className="text-sm text-gray-600">Razorpay / PayU / others</p>
          <p className="text-xs text-blue-700 mt-1">{paymentCount} configured</p>
        </button>
      </div>

      <div className="flex justify-end">
        <Button onClick={openCreate} variant="primary" icon={FaPlus} iconPosition="left">
          {activeModule === 'kyc' ? 'Add KYC API' : 'Add Payment Gateway API'}
        </Button>
      </div>

      {feedback && (
        <div
          className={`p-3 rounded-lg border ${
            feedbackType === 'ok' ? 'bg-green-50 border-green-200 text-green-700' : 'bg-red-50 border-red-200 text-red-700'
          }`}
        >
          {feedback}
        </div>
      )}

      <Card padding="lg">
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead>
              <tr className="border-b border-gray-200">
                <th className="text-left py-3 px-4 font-semibold text-gray-700">Provider</th>
                <th className="text-left py-3 px-4 font-semibold text-gray-700">Auth</th>
                <th className="text-left py-3 px-4 font-semibold text-gray-700">Status</th>
                <th className="text-left py-3 px-4 font-semibold text-gray-700">Default</th>
                <th className="text-left py-3 px-4 font-semibold text-gray-700">Priority</th>
                <th className="text-right py-3 px-4 font-semibold text-gray-700">Actions</th>
              </tr>
            </thead>
            <tbody>
              {moduleRows.length === 0 ? (
                <tr>
                  <td colSpan="6" className="text-center py-8 text-gray-500">
                    {loading ? 'Loading...' : `No ${activeModule === 'kyc' ? 'KYC APIs' : 'payment APIs'} configured yet.`}
                  </td>
                </tr>
              ) : (
                moduleRows.map((row) => (
                  <tr key={row.id} className="border-b border-gray-100 hover:bg-gray-50">
                    <td className="py-4 px-4">
                      <div className="font-semibold text-gray-900">{row.provider_name}</div>
                      <div className="text-xs text-gray-500">{row.provider_code}</div>
                    </td>
                    <td className="py-4 px-4">{row.auth_type}</td>
                    <td className="py-4 px-4">
                      <span
                        className={`px-2 py-1 text-xs rounded-full ${
                          row.status === 'active' ? 'bg-green-100 text-green-700' : 'bg-gray-100 text-gray-700'
                        }`}
                      >
                        {row.status}
                      </span>
                    </td>
                    <td className="py-4 px-4">{row.is_default ? 'Yes' : 'No'}</td>
                    <td className="py-4 px-4">{row.priority}</td>
                    <td className="py-4 px-4">
                      <div className="flex items-center justify-end gap-2">
                        <button
                          onClick={() => testConnection(row.id)}
                          className="p-2 rounded text-emerald-700 hover:bg-emerald-50"
                          title="Test Connection"
                        >
                          <FaPlug size={16} />
                        </button>
                        <button
                          onClick={() => toggleStatus(row)}
                          className="p-2 rounded text-amber-700 hover:bg-amber-50"
                          title="Activate/Deactivate"
                        >
                          <FaPowerOff size={16} />
                        </button>
                        <button
                          onClick={() => openEdit(row)}
                          className="p-2 rounded text-blue-700 hover:bg-blue-50"
                          title="Edit"
                        >
                          <FaPenToSquare size={16} />
                        </button>
                        <button
                          onClick={() => deleteRow(row.id)}
                          className="p-2 rounded text-red-700 hover:bg-red-50"
                          title="Delete"
                        >
                          <FaTrash size={16} />
                        </button>
                      </div>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </Card>

      {showModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black bg-opacity-50 overflow-y-auto">
          <Card className="max-w-4xl w-full border-2 border-blue-200 my-auto" padding="lg" shadow="xl">
            <div className="flex items-center justify-between mb-6">
              <h2 className="text-xl sm:text-2xl font-bold text-gray-900">
                {editing ? `Edit ${activeModule === 'kyc' ? 'KYC API' : 'Payment API'}` : `Add ${activeModule === 'kyc' ? 'KYC API' : 'Payment API'}`}
              </h2>
              <button
                onClick={() => {
                  setShowModal(false);
                  setEditing(null);
                }}
                className="text-gray-400 hover:text-gray-600 transition-colors"
              >
                <FaXmark size={24} />
              </button>
            </div>

            <form onSubmit={saveForm} className="space-y-4">
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {activeModule === 'kyc' ? (
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-2">KYC Service</label>
                    <select
                      value={form.provider_code}
                      onChange={(e) => onKycServiceChange(e.target.value)}
                      disabled={Boolean(editing)}
                      className="w-full px-4 py-3 border border-gray-300 rounded-lg"
                    >
                      {kycServiceOptions.map((s) => (
                        <option key={s.code} value={s.code}>
                          {s.name}
                        </option>
                      ))}
                    </select>
                    <p className="text-xs text-gray-500 mt-1">Initial phase allows only Aadhaar and PAN APIs.</p>
                  </div>
                ) : (
                  <Input
                    label="Provider Code *"
                    value={form.provider_code}
                    onChange={(e) => setForm((p) => ({ ...p, provider_code: e.target.value }))}
                    required
                  />
                )}
                <Input
                  label="Provider Name *"
                  value={form.provider_name}
                  onChange={(e) => setForm((p) => ({ ...p, provider_name: e.target.value }))}
                  required
                />
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">Auth Type</label>
                  <select
                    value={form.auth_type}
                    onChange={(e) => setForm((p) => ({ ...p, auth_type: e.target.value }))}
                    className="w-full px-4 py-3 border border-gray-300 rounded-lg"
                  >
                    {authTypes.map((t) => (
                      <option key={t} value={t}>
                        {t}
                      </option>
                    ))}
                  </select>
                </div>
                <Input
                  label="Base URL"
                  value={form.base_url}
                  onChange={(e) => setForm((p) => ({ ...p, base_url: e.target.value }))}
                  placeholder="https://api.provider.com"
                />
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">Status</label>
                  <select
                    value={form.status}
                    onChange={(e) => setForm((p) => ({ ...p, status: e.target.value }))}
                    className="w-full px-4 py-3 border border-gray-300 rounded-lg"
                  >
                    {statusOptions.map((s) => (
                      <option key={s} value={s}>
                        {s}
                      </option>
                    ))}
                  </select>
                </div>
                <Input
                  type="number"
                  min="0"
                  step="1"
                  label="Priority"
                  value={form.priority}
                  onChange={(e) => setForm((p) => ({ ...p, priority: e.target.value }))}
                />
                <Input
                  label="Webhook Path"
                  value={form.webhook_path}
                  onChange={(e) => setForm((p) => ({ ...p, webhook_path: e.target.value }))}
                  placeholder="/v1/callback"
                />
              </div>

              <div className="flex flex-wrap gap-5">
                <label className="inline-flex items-center gap-2 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={form.is_default}
                    onChange={(e) => setForm((p) => ({ ...p, is_default: e.target.checked }))}
                  />
                  <span className="text-sm text-gray-700">Default for this module</span>
                </label>
                <label className="inline-flex items-center gap-2 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={form.supports_webhook}
                    onChange={(e) => setForm((p) => ({ ...p, supports_webhook: e.target.checked }))}
                  />
                  <span className="text-sm text-gray-700">Supports webhook</span>
                </label>
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Config JSON (non-secret settings)
                </label>
                <textarea
                  value={form.config_json_text}
                  onChange={(e) => setForm((p) => ({ ...p, config_json_text: e.target.value }))}
                  className="w-full min-h-[120px] px-4 py-3 border border-gray-300 rounded-lg"
                />
              </div>

              <div className="border border-gray-200 rounded-xl p-4">
                <div className="flex items-center justify-between mb-3">
                  <h3 className="text-sm font-semibold text-gray-800">Secrets (encrypted at rest)</h3>
                  <Button
                    type="button"
                    variant="outline"
                    size="sm"
                    onClick={() =>
                      setForm((p) => ({
                        ...p,
                        secrets: [...p.secrets, { key: '', value: '', maskedPreview: '' }],
                      }))
                    }
                  >
                    Add Secret Key
                  </Button>
                </div>
                <div className="space-y-3">
                  {activeModule === 'payments' && (
                    <p className="text-xs text-amber-800 bg-amber-50 border border-amber-100 rounded-lg px-3 py-2 mb-2">
                      <strong>Razorpay:</strong> In the <strong>Key</strong> column type the literal names{' '}
                      <code className="bg-amber-100/80 px-1 rounded">key_id</code> and{' '}
                      <code className="bg-amber-100/80 px-1 rounded">key_secret</code> — not your{' '}
                      <code className="bg-amber-100/80 px-1 rounded">rzp_test_…</code> string. Put the Key ID and
                      secret in the <strong>Value</strong> column. Load Money reads live credentials from API Master
                      (and your payment gateway link / default Razorpay entry); .env is optional.
                    </p>
                  )}
                  {form.secrets.map((entry, idx) => (
                    <div key={idx} className="space-y-1">
                      <div className="grid grid-cols-1 md:grid-cols-2 gap-3 items-end">
                        <Input
                          label="Key"
                          value={entry.key}
                          onChange={(e) => updateSecret(idx, { key: e.target.value })}
                          placeholder={activeModule === 'payments' ? 'key_id' : 'api_key'}
                        />
                        <div className="flex gap-2">
                          <Input
                            label="Value"
                            type="password"
                            value={entry.value}
                            onChange={(e) => updateSecret(idx, { value: e.target.value })}
                            placeholder={entry.maskedPreview ? 'Leave blank to keep stored' : '••••••'}
                          />
                          {form.secrets.length > 1 && (
                            <Button
                              type="button"
                              variant="outline"
                              className="h-11 self-end"
                              onClick={() =>
                                setForm((p) => ({ ...p, secrets: p.secrets.filter((_, i) => i !== idx) }))
                              }
                            >
                              Remove
                            </Button>
                          )}
                        </div>
                      </div>
                      {entry.maskedPreview ? (
                        <p className="text-xs text-gray-600 md:pl-1">
                          Stored (masked):{' '}
                          <span className="font-mono bg-gray-100 px-1.5 py-0.5 rounded">{entry.maskedPreview}</span>
                        </p>
                      ) : null}
                    </div>
                  ))}
                </div>
                {editing && (
                  <p className="text-xs text-gray-500 mt-2">
                    Plain secret values are never shown after save (only masked). Use the Key column to see what is
                    stored; type a new Value only to replace that entry.
                  </p>
                )}
              </div>

              <div className="flex gap-3 pt-2">
                <Button
                  type="button"
                  onClick={() => {
                    setShowModal(false);
                    setEditing(null);
                  }}
                  variant="outline"
                  fullWidth
                >
                  Cancel
                </Button>
                <Button type="submit" variant="primary" fullWidth loading={loading}>
                  {editing ? 'Update Configuration' : 'Create Configuration'}
                </Button>
              </div>
            </form>
          </Card>
        </div>
      )}
    </div>
  );
};

export default APIMasterManagement;
