import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import { adminAPI } from '../../services/api';
import { FaArrowLeft } from 'react-icons/fa6';

const SmsEventTemplates = () => {
  const [templates, setTemplates] = useState([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [rowTestPhone, setRowTestPhone] = useState({});
  const [msg, setMsg] = useState({ type: '', text: '' });

  const setBanner = (type, text) => setMsg({ type, text });

  const loadTemplates = useCallback(async () => {
    setLoading(true);
    const res = await adminAPI.listSmsTemplates();
    if (res.success && res.data?.templates) {
      setTemplates(res.data.templates);
    } else {
      setBanner('error', res.message || 'Failed to load event templates');
    }
    setLoading(false);
  }, []);

  useEffect(() => {
    loadTemplates();
  }, [loadTemplates]);

  const templatesByModule = useMemo(() => {
    const groups = {};
    templates.forEach((t) => {
      const mod = t.module || 'other';
      if (!groups[mod]) groups[mod] = [];
      groups[mod].push(t);
    });
    return groups;
  }, [templates]);

  const updateTemplate = async (eventKey, patch) => {
    setSaving(true);
    const res = await adminAPI.updateSmsTemplate(eventKey, patch);
    if (res.success) {
      setBanner('success', `Updated ${eventKey}`);
      await loadTemplates();
    } else {
      setBanner('error', res.message || 'Failed to update template');
    }
    setSaving(false);
  };

  const testTemplateRow = async (eventKey) => {
    const phone = (rowTestPhone[eventKey] || '').trim();
    if (!phone) {
      setBanner('error', 'Enter a 10-digit phone for row test.');
      return;
    }
    setSaving(true);
    setBanner('info', 'Sending test SMS via active profile...');
    const res = await adminAPI.testSmsTemplate(eventKey, { phone });
    if (res.success) {
      setBanner('success', res.message || `Test sent for ${eventKey}`);
    } else {
      setBanner('error', res.message || 'Template test failed');
    }
    setSaving(false);
  };

  return (
    <div className="space-y-6 max-w-5xl mx-auto">
      <Link
        to="/admin/sms-settings"
        className="inline-flex items-center gap-1.5 text-sm text-gray-600 hover:text-gray-900"
      >
        <FaArrowLeft className="w-3.5 h-3.5" /> Back to SMS profiles
      </Link>

      <div>
        <h1 className="text-2xl font-semibold text-gray-900">Event templates</h1>
        <p className="text-sm text-gray-500 mt-1">
          Map DLT template IDs per notification event. Uses the <strong>active</strong> SMS profile for
          delivery. Events default to off until enabled.
        </p>
      </div>

      {msg.text && (
        <div
          className={`text-sm border rounded-lg px-4 py-3 ${
            msg.type === 'success'
              ? 'bg-green-50 border-green-200 text-green-800'
              : msg.type === 'error'
                ? 'bg-red-50 border-red-200 text-red-800'
                : 'bg-blue-50 border-blue-200 text-blue-800'
          }`}
        >
          {msg.text}
        </div>
      )}

      {loading ? (
        <div className="bg-white rounded-xl border p-12 text-center text-gray-500">Loading...</div>
      ) : (
        <div className="bg-white rounded-xl border border-gray-200 p-6 shadow-sm space-y-6">
          {Object.entries(templatesByModule).map(([module, rows]) => (
            <div key={module} className="space-y-3">
              <h3 className="text-sm font-semibold text-gray-700 uppercase tracking-wide">{module}</h3>
              <div className="overflow-x-auto">
                <table className="min-w-full text-sm border border-gray-200 rounded-lg">
                  <thead className="bg-gray-50 text-left">
                    <tr>
                      <th className="px-3 py-2 border-b">Event</th>
                      <th className="px-3 py-2 border-b">On</th>
                      <th className="px-3 py-2 border-b">Template ID</th>
                      <th className="px-3 py-2 border-b">Variables</th>
                      <th className="px-3 py-2 border-b">Test</th>
                    </tr>
                  </thead>
                  <tbody>
                    {rows.map((t) => (
                      <tr key={t.event_key} className="border-b border-gray-100">
                        <td className="px-3 py-2 align-top">
                          <div className="font-medium text-gray-900">{t.label}</div>
                          <div className="text-xs text-gray-500">{t.event_key}</div>
                          {t.description && (
                            <div className="text-xs text-gray-400 mt-0.5">{t.description}</div>
                          )}
                        </td>
                        <td className="px-3 py-2 align-top">
                          <input
                            type="checkbox"
                            checked={!!t.is_enabled}
                            disabled={saving}
                            onChange={(e) =>
                              updateTemplate(t.event_key, { is_enabled: e.target.checked })
                            }
                          />
                        </td>
                        <td className="px-3 py-2 align-top">
                          <input
                            className="w-44 border border-gray-300 rounded px-2 py-1 text-xs"
                            defaultValue={t.template_id || ''}
                            disabled={saving}
                            onBlur={(e) => {
                              const v = e.target.value.trim();
                              if (v !== (t.template_id || '')) {
                                updateTemplate(t.event_key, { template_id: v });
                              }
                            }}
                          />
                        </td>
                        <td className="px-3 py-2 align-top text-xs text-gray-600 max-w-xs">
                          {(t.variable_schema || []).map((v) => v.name).join(', ')}
                        </td>
                        <td className="px-3 py-2 align-top">
                          <div className="flex gap-1">
                            <input
                              className="w-24 border border-gray-300 rounded px-2 py-1 text-xs"
                              placeholder="phone"
                              value={rowTestPhone[t.event_key] || ''}
                              onChange={(e) =>
                                setRowTestPhone((p) => ({ ...p, [t.event_key]: e.target.value }))
                              }
                            />
                            <button
                              type="button"
                              disabled={saving || !t.template_id}
                              onClick={() => testTemplateRow(t.event_key)}
                              className="text-xs px-2 py-1 rounded border hover:bg-gray-50 disabled:opacity-50"
                            >
                              Test
                            </button>
                          </div>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};

export default SmsEventTemplates;
