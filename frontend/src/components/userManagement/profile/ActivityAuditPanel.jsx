import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import { FaDownload, FaRotate } from 'react-icons/fa6';
import { adminAPI, authAPI } from '../../../services/api';
import Button from '../../common/Button';
import Card from '../../common/Card';
import ReportDateRange from '../../common/ReportDateRange';
import { formatUserId } from '../../../utils/formatters';
import {
  formatAuditDateTime,
  formatAuditEventLabel,
  toYmdIst,
} from '../../../utils/auditDisplay';

const CATEGORIES = [
  { id: 'all', label: 'All' },
  { id: 'auth', label: 'Auth' },
  { id: 'money', label: 'Money' },
  { id: 'account', label: 'Account' },
  { id: 'admin', label: 'Admin' },
];

const PRESETS = [
  { id: 'today', label: 'Today' },
  { id: '7d', label: '7 days' },
  { id: '30d', label: '30 days' },
  { id: 'custom', label: 'Custom' },
];

const presetRange = (preset) => {
  const end = new Date();
  const start = new Date();
  if (preset === 'today') {
    const ymd = toYmdIst(end);
    return { date_from: ymd, date_to: ymd };
  }
  if (preset === '7d') {
    start.setDate(start.getDate() - 6);
    return { date_from: toYmdIst(start), date_to: toYmdIst(end) };
  }
  if (preset === '30d') {
    start.setDate(start.getDate() - 29);
    return { date_from: toYmdIst(start), date_to: toYmdIst(end) };
  }
  return { date_from: '', date_to: '' };
};

/**
 * @param {{
 *   mode?: 'admin'|'self',
 *   userId?: number|string,
 *   title?: string,
 *   defaultCategory?: 'all'|'auth'|'money'|'admin'|'account',
 *   showDeviceColumns?: boolean,
 * }} props
 */
const ActivityAuditPanel = ({
  mode = 'admin',
  userId,
  title = 'Activity',
  defaultCategory = 'all',
  showDeviceColumns = true,
}) => {
  // Enterprise RBAC: only explicit admin mode may query cross-user logs.
  const effectiveMode = mode === 'admin' ? 'admin' : 'self';

  const [preset, setPreset] = useState('30d');
  const [category, setCategory] = useState(defaultCategory);
  const [eventType, setEventType] = useState('');
  const [dateFrom, setDateFrom] = useState(() => presetRange('30d').date_from);
  const [dateTo, setDateTo] = useState(() => presetRange('30d').date_to);
  const [appliedDateFrom, setAppliedDateFrom] = useState(() => presetRange('30d').date_from);
  const [appliedDateTo, setAppliedDateTo] = useState(() => presetRange('30d').date_to);
  const [page, setPage] = useState(1);
  const [rows, setRows] = useState([]);
  const [pagination, setPagination] = useState({ page: 1, page_size: 25, total: 0, total_pages: 1 });
  const [loading, setLoading] = useState(true);
  const [exporting, setExporting] = useState(false);
  const [error, setError] = useState('');

  const queryParams = useMemo(() => {
    const params = {
      category: category === 'all' ? undefined : category,
      event_type: eventType || undefined,
      date_from: appliedDateFrom || undefined,
      date_to: appliedDateTo || undefined,
      page,
      page_size: 25,
    };
    if (effectiveMode === 'admin' && userId != null) {
      params.user_id = userId;
    }
    return params;
  }, [category, eventType, appliedDateFrom, appliedDateTo, page, effectiveMode, userId]);

  const load = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      // Non-admin path always uses /auth/my-activity/ (server forces own user_id).
      const res =
        effectiveMode === 'self'
          ? await authAPI.getMyActivity(queryParams)
          : await adminAPI.getSessionSecurityAuditLogs(queryParams);
      if (res.success) {
        setRows(res.data?.results || []);
        setPagination(res.data?.pagination || { page: 1, page_size: 25, total: 0, total_pages: 1 });
      } else {
        setError(res.message || 'Failed to load activity');
        setRows([]);
      }
    } catch (err) {
      console.error(err);
      setError('Failed to load activity');
      setRows([]);
    } finally {
      setLoading(false);
    }
  }, [effectiveMode, queryParams]);

  useEffect(() => {
    load();
  }, [load]);

  const applyPreset = (id) => {
    setPreset(id);
    if (id === 'custom') return;
    const range = presetRange(id);
    setDateFrom(range.date_from);
    setDateTo(range.date_to);
    setAppliedDateFrom(range.date_from);
    setAppliedDateTo(range.date_to);
    setPage(1);
  };

  const handleExport = async () => {
    setExporting(true);
    try {
      if (effectiveMode === 'self') {
        await authAPI.exportMyActivity(queryParams);
      } else {
        await adminAPI.exportSessionSecurityAuditLogs(queryParams);
      }
    } catch (err) {
      console.error(err);
      setError('Export failed');
    } finally {
      setExporting(false);
    }
  };

  return (
    <Card className="overflow-hidden border-slate-200/80 shadow-sm">
      <div className="flex flex-col gap-3 border-b border-slate-100 bg-slate-50/60 px-5 py-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h2 className="text-base font-semibold tracking-tight text-slate-900">{title}</h2>
          <p className="mt-0.5 text-sm text-slate-500">
            Auth, money, contacts, reports, and admin events. Times shown in IST with seconds.
            Precise location uses browser GPS when allowed; otherwise IP GeoIP.
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <Button type="button" variant="outline" size="sm" onClick={load} disabled={loading}>
            <span className="inline-flex items-center gap-1.5">
              <FaRotate size={12} />
              Refresh
            </span>
          </Button>
          <Button type="button" size="sm" onClick={handleExport} disabled={exporting || loading}>
            <span className="inline-flex items-center gap-1.5">
              <FaDownload size={12} />
              {exporting ? 'Exporting…' : 'Export Excel'}
            </span>
          </Button>
        </div>
      </div>

      <div className="space-y-4 border-b border-slate-100 px-5 py-4">
        <div className="flex flex-wrap gap-2">
          {PRESETS.map((p) => (
            <button
              key={p.id}
              type="button"
              onClick={() => applyPreset(p.id)}
              className={`rounded-lg px-3 py-1.5 text-xs font-semibold transition ${
                preset === p.id
                  ? 'bg-slate-900 text-white'
                  : 'bg-white text-slate-600 ring-1 ring-slate-200 hover:bg-slate-50'
              }`}
            >
              {p.label}
            </button>
          ))}
        </div>
        <div className="flex flex-wrap gap-2">
          {CATEGORIES.map((c) => (
            <button
              key={c.id}
              type="button"
              onClick={() => {
                setCategory(c.id);
                setPage(1);
              }}
              className={`rounded-full px-3 py-1 text-xs font-semibold transition ${
                category === c.id
                  ? 'bg-indigo-600 text-white'
                  : 'bg-indigo-50 text-indigo-800 ring-1 ring-indigo-100 hover:bg-indigo-100'
              }`}
            >
              {c.label}
            </button>
          ))}
        </div>
        <div className="grid gap-3 sm:grid-cols-3">
          <div className="min-w-0 sm:col-span-2">
            <ReportDateRange
              idPrefix="activity-audit"
              showApply
              applyLabel="Apply dates"
              dateFrom={dateFrom}
              dateTo={dateTo}
              fromLabel="From"
              toLabel="To"
              onChange={({ dateFrom: from, dateTo: to }) => {
                setPreset('custom');
                setDateFrom(from);
                setDateTo(to);
              }}
              onApply={({ dateFrom: from, dateTo: to }) => {
                setPreset('custom');
                setDateFrom(from);
                setDateTo(to);
                setAppliedDateFrom(from);
                setAppliedDateTo(to);
                setPage(1);
              }}
            />
          </div>
          <label className="block text-xs font-semibold text-slate-600">
            Event type
            <input
              type="text"
              value={eventType}
              onChange={(e) => {
                setEventType(e.target.value.trim());
                setPage(1);
              }}
              placeholder="e.g. login_success"
              className="mt-1 w-full rounded-lg border border-slate-200 px-3 py-2 text-sm text-slate-900 shadow-sm focus:border-indigo-400 focus:outline-none focus:ring-1 focus:ring-indigo-400"
            />
          </label>
        </div>
      </div>

      <div className="px-5 py-4">
        {error ? (
          <p className="mb-3 text-sm text-red-600">{error}</p>
        ) : null}
        {loading ? (
          <p className="py-10 text-center text-sm text-slate-500">Loading activity…</p>
        ) : rows.length === 0 ? (
          <p className="py-10 text-center text-sm text-slate-500">No events for this filter.</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="min-w-full text-left text-sm">
              <thead>
                <tr className="border-b border-slate-200 text-[11px] font-semibold uppercase tracking-wide text-slate-500">
                  <th className="px-2 py-2">When</th>
                  <th className="px-2 py-2">Event</th>
                  <th className="px-2 py-2">Category</th>
                  {effectiveMode === 'admin' && !userId ? <th className="px-2 py-2">User</th> : null}
                  <th className="px-2 py-2">IP</th>
                  <th className="px-2 py-2">Location</th>
                  {showDeviceColumns ? <th className="px-2 py-2">Device</th> : null}
                  <th className="px-2 py-2">Message</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {rows.map((row) => {
                  const resolution = row.location_resolution || '';
                  const precise =
                    row.precise_location_label ||
                    row.location_label ||
                    [row.location?.city, row.location?.region, row.location?.country]
                      .filter(Boolean)
                      .join(', ') ||
                    (row.ip_address ? 'Unknown' : 'N/A (server-side)');
                  const sourceBadge =
                    resolution === 'browser'
                      ? 'Browser GPS'
                      : resolution === 'ip_fallback'
                        ? 'IP GeoIP'
                        : row.location_source && !['none', 'server_side'].includes(row.location_source)
                          ? `GeoIP · ${row.location_source}`
                          : '';
                  return (
                  <tr key={row.id} className="align-top text-slate-700">
                    <td className="whitespace-nowrap px-2 py-2.5 text-xs text-slate-500">
                      {formatAuditDateTime(row.created_at)}
                    </td>
                    <td className="px-2 py-2.5">
                      <div className="font-medium text-slate-900">
                        {formatAuditEventLabel(row.event_type)}
                      </div>
                      <div className="mt-0.5 font-mono text-[10px] text-slate-400">{row.event_type}</div>
                    </td>
                    <td className="px-2 py-2.5">
                      <span className="rounded-md bg-slate-100 px-1.5 py-0.5 text-[11px] font-semibold uppercase text-slate-600">
                        {row.category || '—'}
                      </span>
                    </td>
                    {effectiveMode === 'admin' && !userId ? (
                      <td className="px-2 py-2.5 text-xs">
                        {row.user_id ? (
                          <Link
                            to={`/user-management/users/${row.user_id}`}
                            className="font-semibold text-indigo-600 hover:text-indigo-800"
                          >
                            {formatUserId(row.user) || row.user?.phone || row.user_id}
                          </Link>
                        ) : (
                          row.phone_attempted || '—'
                        )}
                      </td>
                    ) : null}
                    <td className="px-2 py-2.5 font-mono text-xs">
                      {row.ip_address || 'N/A'}
                    </td>
                    <td className="px-2 py-2.5 text-xs">
                      <div>{precise}</div>
                      {sourceBadge ? (
                        <div className="mt-0.5 text-[10px] font-medium uppercase tracking-wide text-slate-400">
                          {sourceBadge}
                        </div>
                      ) : null}
                      {row.location_label &&
                      resolution === 'browser' &&
                      row.precise_location_label !== row.location_label ? (
                        <div className="mt-0.5 text-[10px] text-slate-400">
                          IP: {row.location_label}
                        </div>
                      ) : null}
                      {row.network_capture === 'unavailable' ||
                      row.location_source === 'server_side' ? (
                        <div className="mt-0.5 text-[10px] font-medium uppercase tracking-wide text-slate-400">
                          No client request
                        </div>
                      ) : null}
                    </td>
                    {showDeviceColumns ? (
                      <td className="px-2 py-2.5 text-xs text-slate-600">
                        {row.device_summary ||
                          [
                            row.device?.browser_name,
                            row.device?.os,
                            row.device?.device_type,
                          ]
                            .filter(Boolean)
                            .join(' · ') ||
                          '—'}
                        {row.device?.screen ? (
                          <div className="mt-0.5 text-[10px] text-slate-400">{row.device.screen}</div>
                        ) : null}
                        {row.device?.timezone ? (
                          <div className="mt-0.5 text-[10px] text-slate-400">{row.device.timezone}</div>
                        ) : null}
                      </td>
                    ) : null}
                    <td className="max-w-xs px-2 py-2.5 text-xs text-slate-500">
                      {(row.message || '').slice(0, 120) || '—'}
                    </td>
                  </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}

        {pagination.total_pages > 1 ? (
          <div className="mt-4 flex items-center justify-between text-sm text-slate-600">
            <span>
              Page {pagination.page} of {pagination.total_pages} · {pagination.total} events
            </span>
            <div className="flex gap-2">
              <button
                type="button"
                disabled={page <= 1}
                onClick={() => setPage((p) => Math.max(1, p - 1))}
                className="rounded-lg border border-slate-200 px-3 py-1.5 text-xs font-semibold disabled:opacity-40"
              >
                Previous
              </button>
              <button
                type="button"
                disabled={page >= pagination.total_pages}
                onClick={() => setPage((p) => p + 1)}
                className="rounded-lg border border-slate-200 px-3 py-1.5 text-xs font-semibold disabled:opacity-40"
              >
                Next
              </button>
            </div>
          </div>
        ) : null}
      </div>
    </Card>
  );
};

export default ActivityAuditPanel;
