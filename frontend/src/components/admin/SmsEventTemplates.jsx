import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import { adminAPI } from '../../services/api';
import {
  FaArrowLeft,
  FaArrowRight,
  FaCircleCheck,
  FaCircleXmark,
  FaClock,
  FaFloppyDisk,
  FaLink,
  FaPaperPlane,
  FaRotate,
  FaChevronDown,
} from 'react-icons/fa6';

function placeholderOptions(t, preview, mapDraft) {
  const opts = new Set();
  const detected =
    (preview?.detected_vars && preview.detected_vars.length
      ? preview.detected_vars
      : t.msg91_detected_vars) || [];
  detected.forEach((v) => v && opts.add(String(v)));
  Object.values(mapDraft || {}).forEach((v) => v && opts.add(String(v)));
  // Fallback only when template not synced yet
  if (!opts.size) {
    ['var1', 'var2', 'var3', 'var4', 'var5', 'var6', 'var7', 'var8'].forEach((v) => opts.add(v));
  }
  return [...opts];
}

const MODULE_LABELS = {
  auth: 'OTP',
  payin: 'Pay-in',
  payout: 'Payout',
  bbps: 'Bill pay',
  onboarding: 'Registration',
  complaints: 'Complaints',
  other: 'Other',
};

function readiness(t) {
  const hasId = !!(t.template_id || '').trim();
  const health = t.mapping_health || {};
  const mapped = t.variable_map && Object.keys(t.variable_map).length > 0;
  const healthy = health.is_healthy || (mapped && !(health.unmapped_required || []).length);
  if (t.is_enabled && hasId && healthy) {
    return { key: 'ready', label: 'Live', tone: 'emerald' };
  }
  if (t.is_enabled && hasId) {
    return { key: 'partial', label: 'On · re-sync map', tone: 'amber' };
  }
  if (hasId && t.msg91_synced_at) {
    return { key: 'configured', label: 'Synced', tone: 'sky' };
  }
  if (hasId) {
    return { key: 'configured', label: 'Configured', tone: 'sky' };
  }
  return { key: 'empty', label: 'Not set up', tone: 'slate' };
}

const toneClasses = {
  emerald: 'bg-emerald-50 dark:bg-emerald-950/40 text-emerald-800 dark:text-emerald-300 ring-emerald-200 dark:ring-emerald-800',
  amber: 'bg-amber-50 dark:bg-amber-950/40 text-amber-900 dark:text-amber-300 ring-amber-200 dark:ring-amber-800',
  sky: 'bg-sky-50 dark:bg-sky-950/40 text-sky-900 dark:text-sky-300 ring-sky-200 dark:ring-sky-800',
  slate: 'bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-400 ring-slate-200 dark:ring-slate-700',
};

const SmsEventTemplates = () => {
  const [templates, setTemplates] = useState([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [activeModule, setActiveModule] = useState('all');
  const [openKey, setOpenKey] = useState('');
  const [draftIds, setDraftIds] = useState({});
  const [draftMaps, setDraftMaps] = useState({});
  const [rowTestPhone, setRowTestPhone] = useState({});
  const [fetchPreview, setFetchPreview] = useState({});
  const [msg, setMsg] = useState({ type: '', text: '' });

  const setBanner = (type, text) => setMsg({ type, text });

  const loadTemplates = useCallback(async () => {
    setLoading(true);
    const res = await adminAPI.listSmsTemplates();
    if (res.success && res.data?.templates) {
      const rows = res.data.templates;
      setTemplates(rows);
      const maps = {};
      const ids = {};
      rows.forEach((t) => {
        maps[t.event_key] = { ...(t.variable_map || {}) };
        ids[t.event_key] = t.template_id || '';
      });
      setDraftMaps(maps);
      setDraftIds(ids);
    } else {
      setBanner('error', res.message || 'Failed to load event templates');
    }
    setLoading(false);
  }, []);

  useEffect(() => {
    loadTemplates();
  }, [loadTemplates]);

  const modules = useMemo(() => {
    const order = ['auth', 'onboarding', 'payin', 'payout', 'bbps', 'complaints'];
    const present = new Set(templates.map((t) => t.module || 'other'));
    const extras = [...present].filter((m) => !order.includes(m));
    return ['all', ...order.filter((m) => present.has(m)), ...extras];
  }, [templates]);

  const filtered = useMemo(() => {
    if (activeModule === 'all') return templates;
    return templates.filter((t) => (t.module || 'other') === activeModule);
  }, [templates, activeModule]);

  const stats = useMemo(() => {
    const live = templates.filter((t) => readiness(t).key === 'ready').length;
    const enabled = templates.filter((t) => t.is_enabled).length;
    return { total: templates.length, live, enabled };
  }, [templates]);

  const updateTemplate = async (eventKey, patch) => {
    setSaving(true);
    const res = await adminAPI.updateSmsTemplate(eventKey, patch);
    if (res.success) {
      setBanner('success', res.message || 'Saved');
      await loadTemplates();
    } else {
      setBanner('error', res.message || 'Failed to update');
    }
    setSaving(false);
  };

  const saveTemplateId = async (eventKey) => {
    const v = (draftIds[eventKey] || '').trim();
    const current = templates.find((t) => t.event_key === eventKey);
    if (v === (current?.template_id || '')) return;
    await updateTemplate(eventKey, { template_id: v });
  };

  const saveVariableMap = async (eventKey) => {
    setSaving(true);
    const res = await adminAPI.updateSmsTemplate(eventKey, {
      variable_map: draftMaps[eventKey] || {},
    });
    if (res.success) {
      setBanner('success', 'Variable mapping saved');
      await loadTemplates();
    } else {
      setBanner('error', res.message || 'Failed to save mapping');
    }
    setSaving(false);
  };

  const fetchMsg91 = async (t) => {
    const tid = (draftIds[t.event_key] || t.template_id || '').trim();
    if (!tid) {
      setBanner('error', 'Paste the MSG91 template ID first.');
      return;
    }
    if (tid !== (t.template_id || '')) {
      await updateTemplate(t.event_key, { template_id: tid });
    }
    setSaving(true);
    setBanner('info', 'Fetching MSG91 template and auto-mapping variables…');
    const res = await adminAPI.fetchSmsTemplateMsg91(t.event_key, { template_id: tid });
    if (res.success) {
      setFetchPreview((p) => ({ ...p, [t.event_key]: res.data?.primary || null }));
      setOpenKey(t.event_key);
      const savedMap = res.data?.variable_map || res.data?.suggested_variable_map || {};
      setDraftMaps((m) => ({ ...m, [t.event_key]: { ...savedMap } }));
      await loadTemplates();
      const detected = res.data?.primary?.detected_vars || [];
      const unmapped = res.data?.unmapped_required || [];
      if (unmapped.length) {
        setBanner(
          'error',
          `Synced, but required fields still unmapped: ${unmapped.join(', ')}. Adjust manually and Save.`
        );
      } else {
        setBanner(
          'success',
          res.message ||
            (detected.length
              ? `Auto-mapped from placeholders: ${detected.join(', ')}`
              : 'Template synced')
        );
      }
    } else {
      setBanner('error', res.message || 'MSG91 fetch failed');
    }
    setSaving(false);
  };

  const testTemplateRow = async (eventKey) => {
    const phone = (rowTestPhone[eventKey] || '').trim();
    if (!phone) {
      setBanner('error', 'Enter a 10-digit mobile number to test.');
      return;
    }
    setSaving(true);
    setBanner('info', 'Sending test SMS…');
    const res = await adminAPI.testSmsTemplate(eventKey, { phone });
    if (res.success) {
      setBanner('success', res.message || 'Test SMS sent');
    } else {
      setBanner('error', res.message || 'Test failed');
    }
    setSaving(false);
  };

  const toggleOpen = (key) => {
    setOpenKey((prev) => (prev === key ? '' : key));
  };

  return (
    <div className="min-h-[calc(100vh-6rem)] bg-gradient-to-b from-slate-50 dark:from-slate-900 via-white dark:via-slate-900 to-slate-50/80 dark:to-slate-900/80 -mx-4 sm:-mx-6 lg:-mx-8 px-4 sm:px-6 lg:px-8 py-6">
      <div className="max-w-5xl mx-auto space-y-6">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <Link
            to="/admin/sms-settings"
            className="inline-flex items-center gap-2 text-sm font-medium text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-slate-100"
          >
            <span className="flex h-8 w-8 items-center justify-center rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900 shadow-sm">
              <FaArrowLeft className="h-3.5 w-3.5" />
            </span>
            SMS profiles
          </Link>
          <Link
            to="/admin/sms-settings/logs"
            className="text-sm font-semibold text-indigo-700 dark:text-indigo-300 hover:text-indigo-900 dark:hover:text-indigo-200"
          >
            Delivery logs →
          </Link>
        </div>

        <div className="rounded-2xl border border-slate-200/80 dark:border-slate-700/80 bg-white dark:bg-slate-900 p-6 shadow-sm">
          <div className="flex flex-col lg:flex-row lg:items-end lg:justify-between gap-6">
            <div>
              <p className="text-xs font-semibold uppercase tracking-wider text-indigo-600 dark:text-indigo-400">MSG91 Flow</p>
              <h1 className="mt-1 text-2xl font-bold tracking-tight text-slate-900 dark:text-slate-100">Event templates</h1>
              <p className="mt-2 max-w-xl text-sm leading-relaxed text-slate-600 dark:text-slate-400">
                Paste a MSG91 template ID and fetch — placeholders are detected from the live template
                and mapped automatically. Re-fetch anytime the DLT template changes.
              </p>
            </div>
            <div className="flex gap-3">
              {[
                { label: 'Events', value: stats.total },
                { label: 'Enabled', value: stats.enabled },
                { label: 'Live', value: stats.live },
              ].map((s) => (
                <div
                  key={s.label}
                  className="min-w-[76px] rounded-xl bg-slate-50 dark:bg-slate-800/50 px-3 py-2 text-center ring-1 ring-slate-200/80 dark:ring-slate-700/80"
                >
                  <div className="text-lg font-bold tabular-nums text-slate-900 dark:text-slate-100">{s.value}</div>
                  <div className="text-[11px] font-medium uppercase tracking-wide text-slate-500 dark:text-slate-400">{s.label}</div>
                </div>
              ))}
            </div>
          </div>

          <ol className="mt-6 grid gap-3 sm:grid-cols-3">
            {[
              { n: '1', title: 'Paste template ID', desc: 'From MSG91 control panel' },
              { n: '2', title: 'Fetch & auto-map', desc: 'Detect ##…## and wire app → MSG91 keys' },
              { n: '3', title: 'Enable & test', desc: 'Send a trial SMS' },
            ].map((step) => (
              <li
                key={step.n}
                className="flex items-start gap-3 rounded-xl border border-slate-100 dark:border-slate-800 bg-slate-50/80 dark:bg-slate-800/50 px-3.5 py-3"
              >
                <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-indigo-600 text-xs font-bold text-white">
                  {step.n}
                </span>
                <div>
                  <p className="text-sm font-semibold text-slate-900 dark:text-slate-100">{step.title}</p>
                  <p className="text-xs text-slate-500 dark:text-slate-400">{step.desc}</p>
                </div>
              </li>
            ))}
          </ol>
        </div>

        {msg.text ? (
          <div
            role="status"
            className={`rounded-xl border px-4 py-3 text-sm ${
              msg.type === 'success'
                ? 'border-emerald-200 dark:border-emerald-800 bg-emerald-50 dark:bg-emerald-950/40 text-emerald-900 dark:text-emerald-300'
                : msg.type === 'error'
                  ? 'border-red-200 dark:border-red-800 bg-red-50 dark:bg-red-950/40 text-red-900 dark:text-red-300'
                  : 'border-sky-200 dark:border-sky-800 bg-sky-50 dark:bg-sky-950/40 text-sky-900 dark:text-sky-300'
            }`}
          >
            {msg.text}
          </div>
        ) : null}

        <div className="flex flex-wrap gap-2">
          {modules.map((m) => {
            const active = activeModule === m;
            const count =
              m === 'all' ? templates.length : templates.filter((t) => (t.module || 'other') === m).length;
            return (
              <button
                key={m}
                type="button"
                onClick={() => setActiveModule(m)}
                className={`inline-flex items-center gap-2 rounded-full px-3.5 py-1.5 text-sm font-medium transition ${
                  active
                    ? 'bg-slate-900 text-white shadow-sm'
                    : 'bg-white dark:bg-slate-900 text-slate-600 dark:text-slate-400 ring-1 ring-slate-200 dark:ring-slate-700 hover:bg-slate-50 dark:hover:bg-slate-800'
                }`}
              >
                {m === 'all' ? 'All events' : MODULE_LABELS[m] || m}
                <span
                  className={`rounded-full px-1.5 text-[11px] tabular-nums ${
                    active ? 'bg-white/20 dark:bg-slate-900/20 text-white' : 'bg-slate-100 dark:bg-slate-800 text-slate-500 dark:text-slate-400'
                  }`}
                >
                  {count}
                </span>
              </button>
            );
          })}
        </div>

        {loading ? (
          <div className="rounded-2xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900 py-16 text-center text-slate-500 dark:text-slate-400">
            Loading templates…
          </div>
        ) : filtered.length === 0 ? (
          <div className="rounded-2xl border border-dashed border-slate-300 dark:border-slate-600 bg-white dark:bg-slate-900 py-16 text-center text-slate-500 dark:text-slate-400">
            No events in this category.
          </div>
        ) : (
          <div className="space-y-3">
            {filtered.map((t) => {
              const status = readiness(t);
              const isOpen = openKey === t.event_key;
              const preview =
                fetchPreview[t.event_key] ||
                (t.msg91_template_body
                  ? {
                      template_name: t.msg91_template_name,
                      template_data: t.msg91_template_body,
                      sender_id: t.msg91_sender_id,
                      dlt_id: t.msg91_dlt_id,
                      detected_vars: t.msg91_detected_vars || [],
                    }
                  : null);
              const mapDraft = draftMaps[t.event_key] || {};
              const schema = t.variable_schema || [];
              const mappedCount = Object.values(mapDraft).filter(Boolean).length;
              const health = t.mapping_health || {};
              const sourceLabel =
                t.mapping_source === 'auto'
                  ? 'Auto (MSG91)'
                  : t.mapping_source === 'manual'
                    ? 'Manual override'
                    : t.mapping_source === 'default'
                      ? 'Catalog default'
                      : 'Not synced';

              return (
                <article
                  key={t.event_key}
                  className={`overflow-hidden rounded-2xl border bg-white dark:bg-slate-900 shadow-sm transition ${
                    isOpen ? 'border-indigo-200 dark:border-indigo-800 ring-1 ring-indigo-100 dark:ring-indigo-900' : 'border-slate-200 dark:border-slate-700'
                  }`}
                >
                  <div className="flex flex-col gap-4 p-5 sm:flex-row sm:items-center sm:justify-between">
                    <div className="min-w-0 flex-1">
                      <div className="flex flex-wrap items-center gap-2">
                        <h2 className="text-base font-semibold text-slate-900 dark:text-slate-100">{t.label}</h2>
                        <span
                          className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[11px] font-semibold ring-1 ${toneClasses[status.tone]}`}
                        >
                          {status.key === 'ready' ? (
                            <FaCircleCheck className="h-3 w-3" />
                          ) : status.key === 'empty' ? (
                            <FaCircleXmark className="h-3 w-3" />
                          ) : (
                            <FaClock className="h-3 w-3" />
                          )}
                          {status.label}
                        </span>
                      </div>
                      <p className="mt-1 text-sm text-slate-500 dark:text-slate-400 line-clamp-2">{t.description}</p>
                      <p className="mt-1 font-mono text-[11px] text-slate-400 dark:text-slate-500">{t.event_key}</p>
                    </div>

                    <div className="flex shrink-0 items-center gap-4">
                      <div className="flex items-center gap-2">
                        <span className="text-xs font-medium text-slate-600 dark:text-slate-400">Send SMS</span>
                        <button
                          type="button"
                          role="switch"
                          aria-checked={!!t.is_enabled}
                          disabled={saving}
                          onClick={() => updateTemplate(t.event_key, { is_enabled: !t.is_enabled })}
                          className={`relative h-7 w-12 rounded-full transition ${
                            t.is_enabled ? 'bg-emerald-500' : 'bg-slate-300 dark:bg-slate-600'
                          } disabled:opacity-50`}
                        >
                          <span
                            className={`absolute top-0.5 left-0.5 h-6 w-6 rounded-full bg-white dark:bg-slate-900 shadow transition ${
                              t.is_enabled ? 'translate-x-5' : ''
                            }`}
                          />
                        </button>
                      </div>
                      <button
                        type="button"
                        onClick={() => toggleOpen(t.event_key)}
                        className="inline-flex items-center gap-2 rounded-xl border border-slate-200 dark:border-slate-700 bg-slate-50 dark:bg-slate-800/50 px-3.5 py-2 text-sm font-semibold text-slate-800 dark:text-slate-200 hover:bg-white dark:hover:bg-slate-900"
                      >
                        {isOpen ? 'Close' : 'Configure'}
                        <FaChevronDown
                          className={`h-3 w-3 text-slate-500 dark:text-slate-400 transition ${isOpen ? 'rotate-180' : ''}`}
                        />
                      </button>
                    </div>
                  </div>

                  {isOpen ? (
                    <div className="border-t border-slate-100 dark:border-slate-800 bg-slate-50/60 dark:bg-slate-800/50 px-5 py-5 space-y-5">
                      <section className="rounded-xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900 p-4 space-y-3">
                        <div className="flex items-center gap-2">
                          <span className="flex h-6 w-6 items-center justify-center rounded-full bg-indigo-100 dark:bg-indigo-900/40 text-[11px] font-bold text-indigo-700 dark:text-indigo-300">
                            A
                          </span>
                          <h3 className="text-sm font-semibold text-slate-900 dark:text-slate-100">MSG91 template ID</h3>
                        </div>
                        <div className="flex flex-col gap-2 sm:flex-row sm:items-center">
                          <input
                            className="flex-1 rounded-xl border border-slate-200 dark:border-slate-700 px-3.5 py-2.5 font-mono text-sm outline-none focus:border-indigo-300 focus:ring-2 focus:ring-indigo-500/20"
                            placeholder="Paste template_id from MSG91"
                            value={draftIds[t.event_key] ?? ''}
                            disabled={saving}
                            onChange={(e) =>
                              setDraftIds((p) => ({ ...p, [t.event_key]: e.target.value }))
                            }
                            onBlur={() => saveTemplateId(t.event_key)}
                          />
                          <button
                            type="button"
                            disabled={saving}
                            onClick={() => fetchMsg91(t)}
                            className="inline-flex items-center justify-center gap-2 rounded-xl bg-indigo-600 px-4 py-2.5 text-sm font-semibold text-white hover:bg-indigo-700 disabled:opacity-50"
                          >
                            <FaRotate className="h-3.5 w-3.5" />
                            Fetch & auto-map
                          </button>
                        </div>
                        {preview ? (
                          <div className="rounded-xl border border-indigo-100 dark:border-indigo-900 bg-indigo-50/50 dark:bg-indigo-950/40 p-3 space-y-2">
                            <div className="flex flex-wrap gap-x-4 gap-y-1 text-xs text-indigo-950 dark:text-indigo-200">
                              <span className="font-semibold">{preview.template_name || 'Template'}</span>
                              <span>Sender: {preview.sender_id || '—'}</span>
                              <span>DLT: {preview.dlt_id || '—'}</span>
                              {t.msg91_synced_at ? (
                                <span className="text-indigo-700 dark:text-indigo-300">
                                  Synced {new Date(t.msg91_synced_at).toLocaleString()}
                                </span>
                              ) : null}
                            </div>
                            <p className="rounded-lg bg-white/80 dark:bg-slate-900/80 px-3 py-2 text-sm leading-relaxed text-slate-700 dark:text-slate-300 ring-1 ring-indigo-100 dark:ring-indigo-900">
                              {preview.template_data}
                            </p>
                            {(preview.detected_vars || []).length ? (
                              <p className="text-xs text-indigo-800 dark:text-indigo-300">
                                Placeholders found:{' '}
                                <span className="font-mono font-semibold">
                                  {(preview.detected_vars || []).join(', ')}
                                </span>
                              </p>
                            ) : null}
                          </div>
                        ) : null}
                      </section>

                      <section className="rounded-xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900 p-4 space-y-3">
                        <div className="flex flex-wrap items-center justify-between gap-2">
                          <div className="flex items-center gap-2">
                            <span className="flex h-6 w-6 items-center justify-center rounded-full bg-indigo-100 dark:bg-indigo-900/40 text-[11px] font-bold text-indigo-700 dark:text-indigo-300">
                              B
                            </span>
                            <h3 className="text-sm font-semibold text-slate-900 dark:text-slate-100">Map variables</h3>
                            <span className="text-xs text-slate-500 dark:text-slate-400">
                              {mappedCount}/{schema.length} mapped
                            </span>
                            <span className="rounded-full bg-slate-100 dark:bg-slate-800 px-2 py-0.5 text-[11px] font-medium text-slate-600 dark:text-slate-400">
                              {sourceLabel}
                            </span>
                          </div>
                          <p className="text-xs text-slate-500 dark:text-slate-400">
                            App value → MSG91 key (from ##placeholder##)
                          </p>
                        </div>

                        {(health.unmapped_required || []).length ? (
                          <p className="rounded-lg border border-amber-200 dark:border-amber-800 bg-amber-50 dark:bg-amber-950/40 px-3 py-2 text-xs text-amber-900 dark:text-amber-300">
                            Unmapped required: {(health.unmapped_required || []).join(', ')}. Click
                            Fetch &amp; auto-map or set manually.
                          </p>
                        ) : null}
                        {(health.orphan_targets || []).length ? (
                          <p className="rounded-lg border border-amber-200 dark:border-amber-800 bg-amber-50 dark:bg-amber-950/40 px-3 py-2 text-xs text-amber-900 dark:text-amber-300">
                            Mapped keys not in template: {(health.orphan_targets || []).join(', ')}.
                            Re-fetch to fix.
                          </p>
                        ) : null}

                        {schema.length === 0 ? (
                          <p className="text-sm text-slate-500 dark:text-slate-400">No variables for this event.</p>
                        ) : (
                          <div className="space-y-2">
                            {schema.map((v) => (
                              <div
                                key={v.name}
                                className="grid grid-cols-1 items-center gap-2 rounded-xl bg-slate-50 dark:bg-slate-800/50 px-3 py-2.5 sm:grid-cols-[1fr_auto_1fr]"
                              >
                                <div>
                                  <p className="text-sm font-semibold text-slate-800 dark:text-slate-200">
                                    {v.name}
                                    {v.required ? <span className="ml-1 text-red-500">*</span> : null}
                                  </p>
                                  {v.description ? (
                                    <p className="text-xs text-slate-500 dark:text-slate-400">{v.description}</p>
                                  ) : null}
                                </div>
                                <FaArrowRight className="hidden h-3.5 w-3.5 text-slate-400 dark:text-slate-500 sm:block justify-self-center" />
                                <select
                                  className="w-full rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900 px-3 py-2 text-sm font-mono outline-none focus:border-indigo-300 focus:ring-2 focus:ring-indigo-500/20"
                                  value={mapDraft[v.name] || ''}
                                  disabled={saving}
                                  onChange={(e) =>
                                    setDraftMaps((m) => ({
                                      ...m,
                                      [t.event_key]: {
                                        ...(m[t.event_key] || {}),
                                        [v.name]: e.target.value,
                                      },
                                    }))
                                  }
                                >
                                  <option value="">Choose placeholder…</option>
                                  {placeholderOptions(t, preview, mapDraft).map((opt) => (
                                    <option key={opt} value={opt}>
                                      {opt}
                                    </option>
                                  ))}
                                </select>
                              </div>
                            ))}
                          </div>
                        )}

                        <div className="flex flex-wrap gap-2">
                          <button
                            type="button"
                            disabled={saving}
                            onClick={() => fetchMsg91(t)}
                            className="inline-flex items-center gap-2 rounded-xl bg-indigo-600 px-4 py-2.5 text-sm font-semibold text-white hover:bg-indigo-700 disabled:opacity-50"
                          >
                            <FaRotate className="h-3.5 w-3.5" />
                            Re-sync from MSG91
                          </button>
                          <button
                            type="button"
                            disabled={saving}
                            onClick={() => saveVariableMap(t.event_key)}
                            className="inline-flex items-center gap-2 rounded-xl bg-slate-900 px-4 py-2.5 text-sm font-semibold text-white hover:bg-slate-800 disabled:opacity-50"
                          >
                            <FaFloppyDisk className="h-3.5 w-3.5" />
                            Save manual override
                          </button>
                        </div>
                        <p className="text-xs text-slate-500 dark:text-slate-400">
                          Prefer Re-sync after any MSG91 template edit. Manual save is only for rare
                          overrides.
                        </p>
                      </section>

                      <section className="rounded-xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900 p-4 space-y-3">
                        <div className="flex items-center gap-2">
                          <span className="flex h-6 w-6 items-center justify-center rounded-full bg-indigo-100 dark:bg-indigo-900/40 text-[11px] font-bold text-indigo-700 dark:text-indigo-300">
                            C
                          </span>
                          <h3 className="text-sm font-semibold text-slate-900 dark:text-slate-100">Send a test</h3>
                        </div>
                        <div className="flex flex-col gap-2 sm:flex-row">
                          <input
                            className="flex-1 rounded-xl border border-slate-200 dark:border-slate-700 px-3.5 py-2.5 text-sm outline-none focus:border-indigo-300 focus:ring-2 focus:ring-indigo-500/20"
                            placeholder="10-digit mobile number"
                            inputMode="numeric"
                            value={rowTestPhone[t.event_key] || ''}
                            onChange={(e) =>
                              setRowTestPhone((p) => ({
                                ...p,
                                [t.event_key]: e.target.value.replace(/\D/g, '').slice(0, 10),
                              }))
                            }
                          />
                          <button
                            type="button"
                            disabled={saving || !(draftIds[t.event_key] || t.template_id)}
                            onClick={() => testTemplateRow(t.event_key)}
                            className="inline-flex items-center justify-center gap-2 rounded-xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900 px-4 py-2.5 text-sm font-semibold text-slate-800 dark:text-slate-200 hover:bg-slate-50 dark:hover:bg-slate-800 disabled:opacity-50"
                          >
                            <FaPaperPlane className="h-3.5 w-3.5 text-indigo-600 dark:text-indigo-400" />
                            Send test SMS
                          </button>
                        </div>
                        <p className="flex items-start gap-2 text-xs text-slate-500 dark:text-slate-400">
                          <FaLink className="mt-0.5 h-3 w-3 shrink-0" />
                          Uses sample values and your variable map. Requires an active MSG91 profile.
                        </p>
                      </section>
                    </div>
                  ) : (
                    <div className="border-t border-slate-100 dark:border-slate-800 px-5 py-3 flex flex-wrap gap-x-4 gap-y-1 text-xs text-slate-500 dark:text-slate-400">
                      <span>
                        Template:{' '}
                        <span className="font-mono text-slate-700 dark:text-slate-300">
                          {(t.template_id || '').trim() || '—'}
                        </span>
                      </span>
                      <span>
                        Mapping:{' '}
                        {t.variable_map && Object.keys(t.variable_map).length
                          ? Object.entries(t.variable_map)
                              .map(([k, v]) => `${k}→${v}`)
                              .join(', ')
                          : 'Not mapped'}
                      </span>
                    </div>
                  )}
                </article>
              );
            })}
          </div>
        )}

        <p className="pb-8 text-center text-xs text-slate-400 dark:text-slate-500">
          Only the active SMS profile is used for live sends. Disable any event to silence that SMS without
          changing code.
        </p>
      </div>
    </div>
  );
};

export default SmsEventTemplates;
