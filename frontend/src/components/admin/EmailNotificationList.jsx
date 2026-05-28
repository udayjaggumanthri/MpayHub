import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { adminAPI } from '../../services/api';
import {
  FaArrowLeft,
  FaEnvelope,
  FaPen,
  FaPaperPlane,
  FaCircleCheck,
  FaCircleXmark,
  FaServer,
} from 'react-icons/fa6';

const MODULE_META = {
  auth: { label: 'Authentication', accent: 'border-violet-500 bg-violet-50' },
  onboarding: { label: 'Onboarding', accent: 'border-sky-500 bg-sky-50' },
  kyc: { label: 'KYC', accent: 'border-emerald-500 bg-emerald-50' },
  payin: { label: 'Pay-in', accent: 'border-amber-500 bg-amber-50' },
  payout: { label: 'Payout', accent: 'border-orange-500 bg-orange-50' },
  bbps: { label: 'BBPS', accent: 'border-indigo-500 bg-indigo-50' },
  complaints: { label: 'Complaints', accent: 'border-rose-500 bg-rose-50' },
};

const formatDate = (iso) => {
  if (!iso) return '—';
  try {
    return new Date(iso).toLocaleString(undefined, {
      dateStyle: 'medium',
      timeStyle: 'short',
    });
  } catch {
    return iso;
  }
};

const EmailNotificationList = () => {
  const navigate = useNavigate();
  const [templates, setTemplates] = useState([]);
  const [smtpActive, setSmtpActive] = useState(true);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [filter, setFilter] = useState('all');
  const [testModal, setTestModal] = useState(null);
  const [testEmail, setTestEmail] = useState('');
  const [msg, setMsg] = useState({ type: '', text: '' });

  const setBanner = (type, text) => setMsg({ type, text });

  const loadTemplates = useCallback(async () => {
    setLoading(true);
    const [tplRes, smtpRes] = await Promise.all([
      adminAPI.listEmailTemplates(),
      adminAPI.listSmtpConfigs(),
    ]);
    if (tplRes.success && tplRes.data?.templates) {
      setTemplates(tplRes.data.templates);
    } else {
      setBanner('error', tplRes.message || 'Failed to load email templates');
    }
    if (smtpRes.success && Array.isArray(smtpRes.data?.configs)) {
      setSmtpActive(smtpRes.data.configs.some((c) => c.is_active && c.enabled));
    }
    setLoading(false);
  }, []);

  useEffect(() => {
    loadTemplates();
  }, [loadTemplates]);

  const stats = useMemo(() => {
    const enabled = templates.filter((t) => t.is_enabled).length;
    return { total: templates.length, enabled };
  }, [templates]);

  const templatesByModule = useMemo(() => {
    const groups = {};
    templates.forEach((t) => {
      if (filter === 'enabled' && !t.is_enabled) return;
      if (filter === 'disabled' && t.is_enabled) return;
      const mod = t.module || 'other';
      if (!groups[mod]) groups[mod] = [];
      groups[mod].push(t);
    });
    return groups;
  }, [templates, filter]);

  const updateTemplate = async (eventKey, patch) => {
    setSaving(true);
    const res = await adminAPI.updateEmailTemplate(eventKey, patch);
    if (res.success) {
      await loadTemplates();
    } else {
      setBanner('error', res.message || 'Failed to update');
    }
    setSaving(false);
  };

  const openTest = (t) => {
    setTestModal(t);
    setTestEmail('');
    setMsg({ type: '', text: '' });
  };

  const runTest = async () => {
    if (!testModal) return;
    const to_email = testEmail.trim();
    if (!to_email) {
      setBanner('error', 'Enter a recipient email.');
      return;
    }
    if (!smtpActive) {
      setBanner('error', 'Configure an active SMTP profile first.');
      return;
    }
    setSaving(true);
    setBanner('info', 'Sending test email…');
    const res = await adminAPI.testEmailTemplate(testModal.event_key, {
      to_email,
      variables: testModal.sample_variables || {},
    });
    if (res.success) {
      setBanner('success', res.message || `Test sent to ${to_email}`);
      setTestModal(null);
    } else {
      setBanner('error', res.message || 'Test failed');
    }
    setSaving(false);
  };

  const editPath = (eventKey) =>
    `/admin/email-notifications/edit/${encodeURIComponent(eventKey)}`;

  return (
    <div className="max-w-6xl mx-auto space-y-6 pb-10">
      {/* Header */}
      <div className="flex flex-col gap-4">
        <Link
          to="/admin/smtp-settings"
          className="inline-flex items-center gap-2 text-sm text-gray-500 hover:text-gray-800 w-fit"
        >
          <FaArrowLeft className="w-3.5 h-3.5" />
          SMTP profiles
        </Link>

        <div className="flex flex-col lg:flex-row lg:items-end lg:justify-between gap-4">
          <div>
            <div className="flex items-center gap-3">
              <div className="p-2.5 rounded-xl bg-blue-600 text-white shadow-lg shadow-blue-600/25">
                <FaEnvelope className="w-6 h-6" />
              </div>
              <div>
                <h1 className="text-2xl font-bold text-gray-900 tracking-tight">Email notifications</h1>
                <p className="text-sm text-gray-500 mt-0.5">
                  Enterprise templates for transactional email across mPayHub
                </p>
              </div>
            </div>
          </div>

          <div className="flex flex-wrap gap-2">
            <div className="px-4 py-2 rounded-xl bg-white border border-gray-200 shadow-sm text-center min-w-[88px]">
              <p className="text-2xl font-bold text-gray-900">{stats.total}</p>
              <p className="text-[10px] uppercase tracking-wide text-gray-500">Events</p>
            </div>
            <div className="px-4 py-2 rounded-xl bg-white border border-green-200 shadow-sm text-center min-w-[88px]">
              <p className="text-2xl font-bold text-green-700">{stats.enabled}</p>
              <p className="text-[10px] uppercase tracking-wide text-gray-500">Live</p>
            </div>
            <div
              className={`px-4 py-2 rounded-xl border shadow-sm flex items-center gap-2 ${
                smtpActive ? 'bg-green-50 border-green-200' : 'bg-amber-50 border-amber-200'
              }`}
            >
              <FaServer className={`w-4 h-4 ${smtpActive ? 'text-green-600' : 'text-amber-600'}`} />
              <div>
                <p className="text-xs font-semibold text-gray-800">
                  {smtpActive ? 'SMTP ready' : 'SMTP not active'}
                </p>
                {!smtpActive && (
                  <Link to="/admin/smtp-settings" className="text-[10px] text-amber-800 underline">
                    Configure
                  </Link>
                )}
              </div>
            </div>
          </div>
        </div>
      </div>

      {msg.text && (
        <div
          className={`text-sm border rounded-xl px-4 py-3 flex items-start gap-2 ${
            msg.type === 'success'
              ? 'bg-green-50 border-green-200 text-green-800'
              : msg.type === 'error'
                ? 'bg-red-50 border-red-200 text-red-800'
                : 'bg-blue-50 border-blue-200 text-blue-800'
          }`}
        >
          {msg.type === 'success' ? (
            <FaCircleCheck className="w-4 h-4 mt-0.5 flex-shrink-0" />
          ) : msg.type === 'error' ? (
            <FaCircleXmark className="w-4 h-4 mt-0.5 flex-shrink-0" />
          ) : null}
          <span>{msg.text}</span>
        </div>
      )}

      {/* Filters */}
      <div className="flex flex-wrap gap-2">
        {[
          { id: 'all', label: 'All events' },
          { id: 'enabled', label: 'Live only' },
          { id: 'disabled', label: 'Draft only' },
        ].map((f) => (
          <button
            key={f.id}
            type="button"
            onClick={() => setFilter(f.id)}
            className={`px-3 py-1.5 rounded-full text-sm font-medium transition-colors ${
              filter === f.id
                ? 'bg-gray-900 text-white'
                : 'bg-white border border-gray-200 text-gray-600 hover:bg-gray-50'
            }`}
          >
            {f.label}
          </button>
        ))}
      </div>

      {loading ? (
        <div className="grid gap-4">
          {[1, 2, 3].map((i) => (
            <div key={i} className="h-32 bg-gray-100 rounded-2xl animate-pulse" />
          ))}
        </div>
      ) : (
        <div className="space-y-8">
          {Object.entries(templatesByModule).map(([module, rows]) => {
            const meta = MODULE_META[module] || {
              label: module,
              accent: 'border-gray-400 bg-gray-50',
            };
            return (
              <section key={module}>
                <div className={`border-l-4 pl-3 mb-4 ${meta.accent.split(' ')[0]}`}>
                  <h2 className="text-sm font-bold text-gray-800 uppercase tracking-wide">
                    {meta.label}
                  </h2>
                  <p className="text-xs text-gray-500">{rows.length} template{rows.length !== 1 ? 's' : ''}</p>
                </div>
                <div className="grid gap-3">
                  {rows.map((t) => (
                    <article
                      key={t.event_key}
                      className="group rounded-2xl border border-gray-200 bg-white p-4 sm:p-5 shadow-sm hover:shadow-md hover:border-gray-300 transition-all"
                    >
                      <div className="flex flex-col sm:flex-row sm:items-center gap-4">
                        <div className="flex-1 min-w-0">
                          <div className="flex items-center gap-2 flex-wrap">
                            <h3 className="font-semibold text-gray-900">{t.label}</h3>
                            <span
                              className={`inline-flex items-center gap-1 text-[10px] font-bold uppercase px-2 py-0.5 rounded-full ${
                                t.is_enabled
                                  ? 'bg-green-100 text-green-800'
                                  : 'bg-gray-100 text-gray-600'
                              }`}
                            >
                              {t.is_enabled ? (
                                <>
                                  <FaCircleCheck className="w-2.5 h-2.5" /> Live
                                </>
                              ) : (
                                'Draft'
                              )}
                            </span>
                          </div>
                          <p className="text-xs font-mono text-gray-400 mt-0.5">{t.event_key}</p>
                          {t.description && (
                            <p className="text-sm text-gray-600 mt-2 line-clamp-2">{t.description}</p>
                          )}
                          <p className="text-xs text-gray-400 mt-2">Updated {formatDate(t.updated_at)}</p>
                        </div>

                        <div className="flex items-center gap-3 flex-shrink-0">
                          <label className="relative inline-flex items-center cursor-pointer" title="Enable live sending">
                            <input
                              type="checkbox"
                              className="sr-only peer"
                              checked={!!t.is_enabled}
                              disabled={saving}
                              onChange={(e) =>
                                updateTemplate(t.event_key, { is_enabled: e.target.checked })
                              }
                            />
                            <div className="w-11 h-6 bg-gray-200 peer-focus:outline-none peer-focus:ring-2 peer-focus:ring-blue-300 rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-blue-600" />
                          </label>

                          <button
                            type="button"
                            onClick={() => navigate(editPath(t.event_key))}
                            className="inline-flex items-center gap-1.5 px-3 py-2 rounded-lg border border-gray-200 text-sm font-medium text-gray-700 hover:bg-gray-50"
                          >
                            <FaPen className="w-3.5 h-3.5" />
                            Edit
                          </button>
                          <button
                            type="button"
                            disabled={saving || !smtpActive}
                            onClick={() => openTest(t)}
                            className="inline-flex items-center gap-1.5 px-3 py-2 rounded-lg bg-gray-900 text-white text-sm font-medium hover:bg-gray-800 disabled:opacity-40"
                          >
                            <FaPaperPlane className="w-3.5 h-3.5" />
                            Test
                          </button>
                        </div>
                      </div>
                    </article>
                  ))}
                </div>
              </section>
            );
          })}
          {Object.keys(templatesByModule).length === 0 && (
            <p className="text-center text-gray-500 py-12">No templates match this filter.</p>
          )}
        </div>
      )}

      {/* Test modal */}
      {testModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/40">
          <div
            className="bg-white rounded-2xl shadow-2xl max-w-md w-full p-6"
            role="dialog"
            aria-labelledby="test-modal-title"
          >
            <h3 id="test-modal-title" className="text-lg font-semibold text-gray-900">
              Send test email
            </h3>
            <p className="text-sm text-gray-500 mt-1">{testModal.label}</p>
            <p className="text-xs font-mono text-gray-400 mt-0.5">{testModal.event_key}</p>
            <input
              type="email"
              autoFocus
              className="mt-4 w-full border border-gray-300 rounded-lg px-3 py-2.5 text-sm focus:ring-2 focus:ring-blue-500"
              placeholder="Recipient email"
              value={testEmail}
              onChange={(e) => setTestEmail(e.target.value)}
            />
            <p className="text-xs text-gray-400 mt-2">
              Sends with catalog sample data. Works even when the event is in draft mode.
            </p>
            <div className="flex gap-2 mt-5">
              <button
                type="button"
                className="flex-1 py-2 rounded-lg border text-sm hover:bg-gray-50"
                onClick={() => setTestModal(null)}
              >
                Cancel
              </button>
              <button
                type="button"
                disabled={saving}
                className="flex-1 py-2 rounded-lg bg-blue-600 text-white text-sm font-medium hover:bg-blue-700 disabled:opacity-50"
                onClick={runTest}
              >
                Send
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default EmailNotificationList;
