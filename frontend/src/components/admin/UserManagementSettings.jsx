import React, { useCallback, useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { FaArrowLeft, FaFloppyDisk, FaMagnifyingGlass, FaTrash, FaUserPlus } from 'react-icons/fa6';
import { adminAPI } from '../../services/api';
import Button from '../common/Button';
import Card from '../common/Card';
import { formatUserId } from '../../utils/formatters';

const defaultForm = () => ({
  ip_location_enforcement_enabled: true,
  audit_logging_enabled: true,
  single_session_enforcement_enabled: true,
  idle_timeout_minutes: 5,
});

const UserManagementSettings = () => {
  const [form, setForm] = useState(defaultForm);
  const [meta, setMeta] = useState({ updated_at: null, updated_by: null, idle_min: 1, idle_max: 60 });
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');

  const [exceptions, setExceptions] = useState([]);
  const [searchQ, setSearchQ] = useState('');
  const [searchResults, setSearchResults] = useState([]);
  const [searching, setSearching] = useState(false);

  const [auditRows, setAuditRows] = useState([]);
  const [auditLoading, setAuditLoading] = useState(false);

  const loadExceptions = useCallback(async () => {
    const res = await adminAPI.getConcurrentSessionExceptions();
    if (res.success) {
      setExceptions(res.data?.users || []);
    }
  }, []);

  const loadAudit = useCallback(async () => {
    setAuditLoading(true);
    const res = await adminAPI.getSessionSecurityAuditLogs({ page: 1, page_size: 15 });
    if (res.success) {
      setAuditRows(res.data?.results || []);
    }
    setAuditLoading(false);
  }, []);

  const load = useCallback(async () => {
    setLoading(true);
    setError('');
    const res = await adminAPI.getSessionSecuritySettings();
    if (res.success && res.data?.settings) {
      const s = res.data.settings;
      setForm({
        ip_location_enforcement_enabled: !!s.ip_location_enforcement_enabled,
        audit_logging_enabled: !!s.audit_logging_enabled,
        single_session_enforcement_enabled: !!s.single_session_enforcement_enabled,
        idle_timeout_minutes: Number(s.idle_timeout_minutes) || 5,
      });
      setMeta({
        updated_at: s.updated_at,
        updated_by: s.updated_by,
        idle_min: s.idle_timeout_min || 1,
        idle_max: s.idle_timeout_max || 60,
      });
    } else {
      setError(res.message || 'Could not load session security settings');
    }
    await Promise.all([loadExceptions(), loadAudit()]);
    setLoading(false);
  }, [loadAudit, loadExceptions]);

  useEffect(() => {
    load();
  }, [load]);

  const setField = (key, value) => {
    setForm((prev) => ({ ...prev, [key]: value }));
    setSuccess('');
  };

  const handleSave = async () => {
    setSaving(true);
    setError('');
    setSuccess('');
    const res = await adminAPI.updateSessionSecuritySettings(form);
    if (res.success && res.data?.settings) {
      const s = res.data.settings;
      setForm({
        ip_location_enforcement_enabled: !!s.ip_location_enforcement_enabled,
        audit_logging_enabled: !!s.audit_logging_enabled,
        single_session_enforcement_enabled: !!s.single_session_enforcement_enabled,
        idle_timeout_minutes: Number(s.idle_timeout_minutes) || 5,
      });
      setMeta({
        updated_at: s.updated_at,
        updated_by: s.updated_by,
        idle_min: s.idle_timeout_min || 1,
        idle_max: s.idle_timeout_max || 60,
      });
      setSuccess('Settings saved.');
    } else {
      setError(res.message || 'Failed to save settings');
    }
    setSaving(false);
  };

  const runSearch = async () => {
    const q = searchQ.trim();
    if (q.length < 2) {
      setSearchResults([]);
      return;
    }
    setSearching(true);
    const res = await adminAPI.searchUsersForSessionException(q);
    if (res.success) {
      setSearchResults(res.data?.users || []);
    }
    setSearching(false);
  };

  const addException = async (userId) => {
    const res = await adminAPI.setConcurrentSessionException({
      user_id: userId,
      allow_concurrent_sessions: true,
    });
    if (res.success) {
      setSearchQ('');
      setSearchResults([]);
      await loadExceptions();
    } else {
      setError(res.message || 'Could not add exception');
    }
  };

  const removeException = async (userId) => {
    const res = await adminAPI.setConcurrentSessionException({
      user_id: userId,
      allow_concurrent_sessions: false,
    });
    if (res.success) {
      await loadExceptions();
    } else {
      setError(res.message || 'Could not remove exception');
    }
  };

  if (loading) {
    return (
      <div className="flex min-h-[40vh] items-center justify-center text-sm text-slate-500">
        Loading session security settings…
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-4xl space-y-6">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <Link
            to="/user-management/users"
            className="inline-flex items-center gap-2 text-sm font-medium text-indigo-600 hover:text-indigo-800"
          >
            <FaArrowLeft size={12} />
            Back to users
          </Link>
          <h1 className="mt-2 text-2xl font-bold tracking-tight text-slate-900">
            User management settings
          </h1>
          <p className="mt-1 text-sm text-slate-600">
            IP/location login enforcement, single-session policy, idle timeout, and audit logging.
          </p>
        </div>
        <Button onClick={handleSave} disabled={saving} className="inline-flex items-center gap-2">
          <FaFloppyDisk size={14} />
          {saving ? 'Saving…' : 'Save settings'}
        </Button>
      </div>

      {error ? (
        <div className="rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800">
          {error}
        </div>
      ) : null}
      {success ? (
        <div className="rounded-xl border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-800">
          {success}
        </div>
      ) : null}

      <Card>
        <div className="border-b border-slate-100 px-6 py-4">
          <h2 className="text-lg font-semibold text-slate-900">Security controls</h2>
        </div>
        <div className="space-y-6 p-6">
          <label className="flex items-start gap-3">
            <input
              type="checkbox"
              className="mt-1 h-4 w-4 rounded border-slate-300 text-indigo-600 focus:ring-indigo-500"
              checked={form.ip_location_enforcement_enabled}
              onChange={(e) => setField('ip_location_enforcement_enabled', e.target.checked)}
            />
            <span>
              <span className="block text-sm font-semibold text-slate-900">
                Require IP &amp; location on login
              </span>
              <span className="mt-0.5 block text-sm text-slate-600">
                Login and token refresh fail if client IP or geolocation cannot be captured.
              </span>
            </span>
          </label>

          <label className="flex items-start gap-3">
            <input
              type="checkbox"
              className="mt-1 h-4 w-4 rounded border-slate-300 text-indigo-600 focus:ring-indigo-500"
              checked={form.audit_logging_enabled}
              onChange={(e) => setField('audit_logging_enabled', e.target.checked)}
            />
            <span>
              <span className="block text-sm font-semibold text-slate-900">Audit logging</span>
              <span className="mt-0.5 block text-sm text-slate-600">
                Record login attempts, session replacements, logout, and idle timeouts per user.
              </span>
            </span>
          </label>

          <label className="flex items-start gap-3">
            <input
              type="checkbox"
              className="mt-1 h-4 w-4 rounded border-slate-300 text-indigo-600 focus:ring-indigo-500"
              checked={form.single_session_enforcement_enabled}
              onChange={(e) => setField('single_session_enforcement_enabled', e.target.checked)}
            />
            <span>
              <span className="block text-sm font-semibold text-slate-900">
                Single active session
              </span>
              <span className="mt-0.5 block text-sm text-slate-600">
                A new login terminates previous sessions (unless the user is on the exception list).
              </span>
            </span>
          </label>

          <div>
            <label className="block text-sm font-semibold text-slate-900" htmlFor="idle-timeout">
              Idle session timeout (minutes)
            </label>
            <p className="mt-0.5 text-sm text-slate-600">
              Automatically expire sessions after this many minutes without activity (
              {meta.idle_min}–{meta.idle_max}).
            </p>
            <input
              id="idle-timeout"
              type="number"
              min={meta.idle_min}
              max={meta.idle_max}
              value={form.idle_timeout_minutes}
              onChange={(e) => setField('idle_timeout_minutes', Number(e.target.value))}
              className="mt-2 w-32 rounded-lg border border-slate-300 px-3 py-2 text-sm shadow-sm focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500"
            />
          </div>

          {meta.updated_at ? (
            <p className="text-xs text-slate-500">
              Last updated {new Date(meta.updated_at).toLocaleString()}
              {meta.updated_by?.full_name || meta.updated_by?.display_code
                ? ` by ${meta.updated_by.full_name || meta.updated_by.display_code}`
                : ''}
            </p>
          ) : null}
        </div>
      </Card>

      <Card>
        <div className="border-b border-slate-100 px-6 py-4">
          <h2 className="text-lg font-semibold text-slate-900">
            Multi-session exception users
          </h2>
          <p className="mt-1 text-sm text-slate-600">
            These users may stay signed in on multiple devices at once.
          </p>
        </div>
        <div className="space-y-4 p-6">
          <div className="flex flex-col gap-2 sm:flex-row">
            <div className="relative flex-1">
              <FaMagnifyingGlass className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" size={13} />
              <input
                type="search"
                value={searchQ}
                onChange={(e) => setSearchQ(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter') {
                    e.preventDefault();
                    runSearch();
                  }
                }}
                placeholder="Search by phone, code, or name"
                className="w-full rounded-lg border border-slate-300 py-2 pl-9 pr-3 text-sm shadow-sm focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500"
              />
            </div>
            <Button type="button" variant="outline" onClick={runSearch} disabled={searching}>
              {searching ? 'Searching…' : 'Search'}
            </Button>
          </div>

          {searchResults.length > 0 ? (
            <ul className="divide-y divide-slate-100 rounded-xl border border-slate-200">
              {searchResults.map((u) => (
                <li key={u.id} className="flex items-center justify-between gap-3 px-4 py-3 text-sm">
                  <div>
                    <p className="font-medium text-slate-900">
                      {u.full_name || formatUserId(u) || u.phone}
                    </p>
                    <p className="text-xs text-slate-500">
                      {formatUserId(u)} · {u.phone} · {u.role}
                    </p>
                  </div>
                  <button
                    type="button"
                    onClick={() => addException(u.id)}
                    disabled={u.allow_concurrent_sessions}
                    className="inline-flex items-center gap-1.5 rounded-lg bg-indigo-50 px-3 py-1.5 text-xs font-semibold text-indigo-700 hover:bg-indigo-100 disabled:opacity-50"
                  >
                    <FaUserPlus size={12} />
                    {u.allow_concurrent_sessions ? 'Already allowed' : 'Allow'}
                  </button>
                </li>
              ))}
            </ul>
          ) : null}

          {exceptions.length === 0 ? (
            <p className="text-sm text-slate-500">No exception users configured.</p>
          ) : (
            <ul className="divide-y divide-slate-100 rounded-xl border border-slate-200">
              {exceptions.map((u) => (
                <li key={u.id} className="flex items-center justify-between gap-3 px-4 py-3 text-sm">
                  <div>
                    <p className="font-medium text-slate-900">
                      {u.full_name || formatUserId(u) || u.phone}
                    </p>
                    <p className="text-xs text-slate-500">
                      {formatUserId(u)} · {u.phone} · {u.role}
                    </p>
                  </div>
                  <button
                    type="button"
                    onClick={() => removeException(u.id)}
                    className="inline-flex items-center gap-1.5 rounded-lg bg-red-50 px-3 py-1.5 text-xs font-semibold text-red-700 hover:bg-red-100"
                  >
                    <FaTrash size={11} />
                    Remove
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>
      </Card>

      <Card>
        <div className="flex items-center justify-between border-b border-slate-100 px-6 py-4">
          <div>
            <h2 className="text-lg font-semibold text-slate-900">Recent audit events</h2>
            <p className="mt-1 text-sm text-slate-600">Latest login and session events across users.</p>
          </div>
          <Button type="button" variant="outline" size="sm" onClick={loadAudit} disabled={auditLoading}>
            Refresh
          </Button>
        </div>
        <div className="p-6">
          {auditLoading ? (
            <p className="text-sm text-slate-500">Loading…</p>
          ) : auditRows.length === 0 ? (
            <p className="text-sm text-slate-500">No audit events yet.</p>
          ) : (
            <div className="overflow-x-auto">
              <table className="min-w-full text-left text-sm">
                <thead>
                  <tr className="border-b border-slate-200 text-xs uppercase tracking-wide text-slate-500">
                    <th className="px-2 py-2 font-semibold">When</th>
                    <th className="px-2 py-2 font-semibold">Event</th>
                    <th className="px-2 py-2 font-semibold">User</th>
                    <th className="px-2 py-2 font-semibold">IP</th>
                    <th className="px-2 py-2 font-semibold">Location</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {auditRows.map((row) => (
                    <tr key={row.id} className="text-slate-700">
                      <td className="whitespace-nowrap px-2 py-2 text-xs">
                        {row.created_at ? new Date(row.created_at).toLocaleString() : '—'}
                      </td>
                      <td className="px-2 py-2 font-medium">{row.event_type}</td>
                      <td className="px-2 py-2">
                        {row.user
                          ? formatUserId(row.user) || row.user.phone
                          : row.phone_attempted || '—'}
                      </td>
                      <td className="px-2 py-2 font-mono text-xs">{row.ip_address || '—'}</td>
                      <td className="px-2 py-2 text-xs">
                        {[row.location?.city, row.location?.region, row.location?.country]
                          .filter(Boolean)
                          .join(', ') || '—'}
                        {row.user_id ? (
                          <>
                            {' · '}
                            <Link
                              to={`/user-management/users/${row.user_id}`}
                              className="font-semibold text-indigo-600 hover:text-indigo-800"
                            >
                              View profile
                            </Link>
                          </>
                        ) : null}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </Card>
    </div>
  );
};

export default UserManagementSettings;
