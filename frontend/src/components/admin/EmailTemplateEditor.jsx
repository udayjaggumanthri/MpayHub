import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import { adminAPI } from '../../services/api';
import GmailHtmlEditor from './GmailHtmlEditor';
import {
  FaArrowLeft,
  FaFloppyDisk,
  FaPaperPlane,
  FaCircleInfo,
  FaEnvelope,
} from 'react-icons/fa6';

const moduleColors = {
  auth: 'bg-violet-100 dark:bg-violet-900/40 text-violet-800 dark:text-violet-300',
  onboarding: 'bg-sky-100 dark:bg-sky-900/40 text-sky-800 dark:text-sky-300',
  kyc: 'bg-emerald-100 dark:bg-emerald-900/40 text-emerald-800 dark:text-emerald-300',
  payin: 'bg-amber-100 dark:bg-amber-900/40 text-amber-800 dark:text-amber-300',
  payout: 'bg-orange-100 dark:bg-orange-900/40 text-orange-800 dark:text-orange-300',
  bbps: 'bg-indigo-100 dark:bg-indigo-900/40 text-indigo-800 dark:text-indigo-300',
  complaints: 'bg-rose-100 dark:bg-rose-900/40 text-rose-800 dark:text-rose-300',
};

const EmailTemplateEditor = () => {
  const params = useParams();
  const eventKey = decodeURIComponent((params['*'] || '').replace(/\/$/, ''));
  const navigate = useNavigate();
  const subjectRef = useRef(null);

  const [template, setTemplate] = useState(null);
  const [smtpActive, setSmtpActive] = useState(true);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [testEmail, setTestEmail] = useState('');
  const [msg, setMsg] = useState({ type: '', text: '' });

  const setBanner = (type, text) => setMsg({ type, text });

  const load = useCallback(async () => {
    if (!eventKey) {
      setLoading(false);
      return;
    }
    setLoading(true);
    const [tplRes, smtpRes] = await Promise.all([
      adminAPI.getEmailTemplate(eventKey),
      adminAPI.listSmtpConfigs(),
    ]);
    if (tplRes.success && tplRes.data?.template) {
      setTemplate(tplRes.data.template);
    } else {
      setBanner('error', tplRes.message || 'Failed to load template');
    }
    if (smtpRes.success && Array.isArray(smtpRes.data?.configs)) {
      setSmtpActive(smtpRes.data.configs.some((c) => c.is_active && c.enabled));
    }
    setLoading(false);
  }, [eventKey]);

  useEffect(() => {
    load();
  }, [load]);

  const variableFields = useMemo(() => {
    const schema = template?.variable_schema || [];
    return schema.map((v) => (typeof v === 'string' ? { name: v, required: false } : v));
  }, [template]);

  const insertVariable = (name, target = 'body') => {
    const token = `{{${name}}}`;
    if (target === 'subject' && subjectRef.current) {
      const el = subjectRef.current;
      const start = el.selectionStart ?? el.value.length;
      const end = el.selectionEnd ?? start;
      const next = el.value.slice(0, start) + token + el.value.slice(end);
      setTemplate((p) => ({ ...p, subject_template: next }));
      return;
    }
    setTemplate((p) => ({
      ...p,
      body_html_template: `${p.body_html_template || ''}${token}`,
    }));
  };

  const save = async () => {
    if (!template) return;
    setSaving(true);
    const res = await adminAPI.updateEmailTemplate(eventKey, {
      is_enabled: template.is_enabled,
      subject_template: template.subject_template,
      body_html_template: template.body_html_template,
      body_plain_template: template.body_plain_template,
      sample_variables: template.sample_variables,
    });
    if (res.success) {
      setBanner('success', 'Template saved successfully');
      if (res.data?.template) setTemplate((prev) => ({ ...prev, ...res.data.template }));
    } else {
      setBanner('error', res.message || 'Save failed');
    }
    setSaving(false);
  };

  const sendTest = async () => {
    const to_email = testEmail.trim();
    if (!to_email) {
      setBanner('error', 'Enter a recipient email for the test.');
      return;
    }
    if (!smtpActive) {
      setBanner('error', 'No active SMTP profile. Configure SMTP in settings first.');
      return;
    }
    setSaving(true);
    setBanner('info', 'Sending test email…');
    const res = await adminAPI.testEmailTemplate(eventKey, {
      to_email,
      variables: template?.sample_variables || {},
    });
    if (res.success) {
      setBanner('success', res.message || `Test email sent to ${to_email}`);
    } else {
      const detail = res.data?.skip_reason || res.errors?.length
        ? [res.message, res.data?.skip_reason].filter(Boolean).join(' — ')
        : res.message;
      setBanner('error', detail || 'Test failed');
    }
    setSaving(false);
  };

  if (!eventKey) {
    return (
      <div className="max-w-3xl mx-auto p-8 text-center text-gray-500 dark:text-slate-400">
        Invalid template link.{' '}
        <Link to="/admin/email-notifications" className="text-blue-600 dark:text-blue-400 underline">
          Back to list
        </Link>
      </div>
    );
  }

  if (loading) {
    return (
      <div className="max-w-5xl mx-auto animate-pulse space-y-4 p-6">
        <div className="h-8 bg-gray-200 dark:bg-slate-700 rounded w-1/3" />
        <div className="h-64 bg-gray-100 dark:bg-slate-800 rounded-xl" />
      </div>
    );
  }

  if (!template) {
    return (
      <div className="max-w-3xl mx-auto space-y-4 p-6">
        <Link
          to="/admin/email-notifications"
          className="inline-flex items-center gap-2 text-sm text-gray-600 dark:text-slate-400 hover:text-gray-900 dark:hover:text-slate-100"
        >
          <FaArrowLeft /> Back
        </Link>
        <div className="rounded-xl border border-red-200 dark:border-red-800 bg-red-50 dark:bg-red-950/40 px-4 py-3 text-red-800 dark:text-red-300 text-sm">
          {msg.text || 'Template not found.'}
        </div>
      </div>
    );
  }

  const modClass = moduleColors[template.module] || 'bg-gray-100 dark:bg-slate-800 text-gray-700 dark:text-slate-300';

  return (
    <div className="max-w-6xl mx-auto pb-12">
      {/* Gmail-style top bar */}
      <div className="sticky top-0 z-20 -mx-4 px-4 py-3 mb-6 bg-white/95 dark:bg-slate-900/95 backdrop-blur border-b border-gray-200 dark:border-slate-700 shadow-sm">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="flex items-center gap-3 min-w-0">
            <Link
              to="/admin/email-notifications"
              className="flex-shrink-0 p-2 rounded-full hover:bg-gray-100 dark:hover:bg-slate-700 text-gray-600 dark:text-slate-400"
              title="Back"
            >
              <FaArrowLeft className="w-4 h-4" />
            </Link>
            <div className="min-w-0">
              <div className="flex items-center gap-2 flex-wrap">
                <h1 className="text-lg font-semibold text-gray-900 dark:text-slate-100 truncate">{template.label}</h1>
                <span className={`text-[10px] font-semibold uppercase tracking-wider px-2 py-0.5 rounded-full ${modClass}`}>
                  {template.module}
                </span>
              </div>
              <p className="text-xs text-gray-500 dark:text-slate-400 font-mono truncate">{eventKey}</p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <label className="flex items-center gap-2 text-sm text-gray-700 dark:text-slate-300 mr-2 cursor-pointer">
              <input
                type="checkbox"
                className="rounded border-gray-300 dark:border-slate-600 text-blue-600 dark:text-blue-400 focus:ring-blue-500"
                checked={!!template.is_enabled}
                onChange={(e) => setTemplate((p) => ({ ...p, is_enabled: e.target.checked }))}
              />
              <span className="hidden sm:inline">Live sending</span>
            </label>
            <button
              type="button"
              disabled={saving}
              onClick={() => navigate('/admin/email-notifications')}
              className="px-3 py-2 text-sm rounded-lg border border-gray-300 dark:border-slate-600 hover:bg-gray-50 dark:hover:bg-slate-800"
            >
              Discard
            </button>
            <button
              type="button"
              disabled={saving}
              onClick={save}
              className="inline-flex items-center gap-2 px-4 py-2 text-sm font-medium rounded-lg bg-blue-600 text-white hover:bg-blue-700 disabled:opacity-50"
            >
              <FaFloppyDisk className="w-3.5 h-3.5" />
              Save
            </button>
          </div>
        </div>
      </div>

      {!smtpActive && (
        <div className="mb-4 flex items-start gap-2 text-sm border rounded-xl px-4 py-3 bg-amber-50 dark:bg-amber-950/40 border-amber-200 dark:border-amber-800 text-amber-900 dark:text-amber-300">
          <FaCircleInfo className="w-4 h-4 mt-0.5 flex-shrink-0" />
          <span>
            No active SMTP profile.{' '}
            <Link to="/admin/smtp-settings" className="font-medium underline">
              Configure SMTP
            </Link>{' '}
            to send tests or live emails.
          </span>
        </div>
      )}

      {msg.text && (
        <div
          className={`mb-4 text-sm border rounded-xl px-4 py-3 ${
            msg.type === 'success'
              ? 'bg-green-50 dark:bg-green-950/40 border-green-200 dark:border-green-800 text-green-800 dark:text-green-300'
              : msg.type === 'error'
                ? 'bg-red-50 dark:bg-red-950/40 border-red-200 dark:border-red-800 text-red-800 dark:text-red-300'
                : 'bg-blue-50 dark:bg-blue-950/40 border-blue-200 dark:border-blue-800 text-blue-800 dark:text-blue-300'
          }`}
        >
          {msg.text}
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-[1fr_280px] gap-6">
        {/* Compose column — Gmail layout */}
        <div className="rounded-2xl border border-gray-200 dark:border-slate-700 bg-white dark:bg-slate-900 shadow-sm overflow-hidden">
          <div className="px-4 py-3 border-b border-gray-100 dark:border-slate-800 bg-gradient-to-r from-gray-50 dark:from-slate-900 to-white dark:to-slate-900">
            <p className="text-xs font-medium text-gray-500 dark:text-slate-400 uppercase tracking-wide">Compose</p>
          </div>

          <div className="px-4 py-3 border-b border-gray-100 dark:border-slate-800 flex items-center gap-3">
            <span className="text-sm font-medium text-gray-500 dark:text-slate-400 w-14 flex-shrink-0">Subject</span>
            <input
              ref={subjectRef}
              type="text"
              className="flex-1 border-0 border-b border-transparent focus:border-blue-400 focus:ring-0 text-[15px] py-1.5 px-0 bg-transparent outline-none"
              placeholder="Email subject — use {{variables}}"
              value={template.subject_template || ''}
              onChange={(e) => setTemplate((p) => ({ ...p, subject_template: e.target.value }))}
            />
          </div>

          <div className="p-4">
            <GmailHtmlEditor
              value={template.body_html_template || ''}
              onChange={(html) => setTemplate((p) => ({ ...p, body_html_template: html }))}
              minHeight={360}
            />
          </div>

          <details className="border-t border-gray-100 dark:border-slate-800 group">
            <summary className="px-4 py-2.5 text-sm text-gray-600 dark:text-slate-400 cursor-pointer hover:bg-gray-50 dark:hover:bg-slate-800 select-none">
              Plain-text fallback (optional)
            </summary>
            <div className="px-4 pb-4">
              <textarea
                className="w-full border border-gray-200 dark:border-slate-700 rounded-lg px-3 py-2 text-sm font-mono min-h-[100px] focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                placeholder="Auto-generated from HTML if left empty"
                value={template.body_plain_template || ''}
                onChange={(e) => setTemplate((p) => ({ ...p, body_plain_template: e.target.value }))}
              />
            </div>
          </details>
        </div>

        {/* Sidebar */}
        <div className="space-y-4">
          {template.description && (
            <div className="rounded-xl border border-gray-200 dark:border-slate-700 bg-white dark:bg-slate-900 p-4 shadow-sm">
              <p className="text-xs font-semibold text-gray-500 dark:text-slate-400 uppercase mb-2">About this event</p>
              <p className="text-sm text-gray-600 dark:text-slate-400 leading-relaxed">{template.description}</p>
            </div>
          )}

          <div className="rounded-xl border border-gray-200 dark:border-slate-700 bg-white dark:bg-slate-900 p-4 shadow-sm">
            <p className="text-xs font-semibold text-gray-500 dark:text-slate-400 uppercase mb-3">Insert variables</p>
            <div className="flex flex-wrap gap-1.5">
              {variableFields.map((field) => (
                <button
                  key={field.name}
                  type="button"
                  onClick={() => insertVariable(field.name)}
                  className="text-xs font-mono px-2 py-1 rounded-md bg-blue-50 dark:bg-blue-950/40 text-blue-800 dark:text-blue-300 hover:bg-blue-100 dark:hover:bg-blue-900/60 border border-blue-100 dark:border-blue-900"
                  title={field.description || field.name}
                >
                  {`{{${field.name}}}`}
                  {field.required ? ' *' : ''}
                </button>
              ))}
            </div>
            <p className="text-[11px] text-gray-400 dark:text-slate-500 mt-2">* required when sending</p>
          </div>

          <div className="rounded-xl border border-gray-200 dark:border-slate-700 bg-white dark:bg-slate-900 p-4 shadow-sm">
            <p className="text-xs font-semibold text-gray-500 dark:text-slate-400 uppercase mb-3 flex items-center gap-1.5">
              <FaPaperPlane className="w-3 h-3" /> Send test
            </p>
            <input
              type="email"
              className="w-full border border-gray-300 dark:border-slate-600 rounded-lg px-3 py-2 text-sm mb-2 focus:ring-2 focus:ring-blue-500"
              placeholder="you@company.com"
              value={testEmail}
              onChange={(e) => setTestEmail(e.target.value)}
            />
            <button
              type="button"
              disabled={saving || !smtpActive}
              onClick={sendTest}
              className="w-full inline-flex items-center justify-center gap-2 px-3 py-2 rounded-lg bg-gray-900 text-white text-sm hover:bg-gray-800 disabled:opacity-50"
            >
              <FaEnvelope className="w-3.5 h-3.5" />
              Send test email
            </button>
            <p className="text-[11px] text-gray-400 dark:text-slate-500 mt-2">
              Uses sample data from the catalog. Works even if live sending is off.
            </p>
          </div>
        </div>
      </div>
    </div>
  );
};

export default EmailTemplateEditor;
