import React, { useCallback, useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { adminAPI } from '../../services/api';
import { FaArrowLeft } from 'react-icons/fa6';

const SmsDeliveryLogs = () => {
  const [logs, setLogs] = useState([]);
  const [loading, setLoading] = useState(true);
  const [status, setStatus] = useState('');
  const [eventKey, setEventKey] = useState('');
  const [msg, setMsg] = useState('');

  const load = useCallback(async () => {
    setLoading(true);
    setMsg('');
    const params = { limit: 100 };
    if (status) params.status = status;
    if (eventKey.trim()) params.event_key = eventKey.trim();
    const res = await adminAPI.listSmsDeliveryLogs(params);
    if (res.success && res.data?.logs) {
      setLogs(res.data.logs);
    } else {
      setMsg(res.message || 'Failed to load SMS logs');
      setLogs([]);
    }
    setLoading(false);
  }, [status, eventKey]);

  useEffect(() => {
    load();
  }, [load]);

  return (
    <div className="space-y-6 max-w-6xl mx-auto">
      <Link
        to="/admin/sms-settings"
        className="inline-flex items-center gap-1.5 text-sm text-gray-600 hover:text-gray-900"
      >
        <FaArrowLeft className="w-3.5 h-3.5" /> Back to SMS profiles
      </Link>

      <div>
        <h1 className="text-2xl font-semibold text-gray-900">SMS delivery logs</h1>
        <p className="text-sm text-gray-500 mt-1">
          Local audit of MSG91 Flow sends and skips (profile off, event disabled, invalid context).
        </p>
      </div>

      <div className="flex flex-wrap gap-3 items-end bg-white border rounded-xl p-4">
        <label className="text-sm">
          <span className="block text-xs text-gray-500 mb-1">Status</span>
          <select
            className="border rounded px-3 py-2 text-sm"
            value={status}
            onChange={(e) => setStatus(e.target.value)}
          >
            <option value="">All</option>
            <option value="sent">Sent</option>
            <option value="failed">Failed</option>
            <option value="skipped">Skipped</option>
          </select>
        </label>
        <label className="text-sm flex-1 min-w-[180px]">
          <span className="block text-xs text-gray-500 mb-1">Event key</span>
          <input
            className="w-full border rounded px-3 py-2 text-sm"
            value={eventKey}
            onChange={(e) => setEventKey(e.target.value)}
            placeholder="e.g. payin.success"
          />
        </label>
        <button
          type="button"
          onClick={load}
          className="px-4 py-2 text-sm rounded bg-slate-900 text-white hover:bg-slate-800"
        >
          Refresh
        </button>
        <Link
          to="/admin/sms-settings/templates"
          className="px-4 py-2 text-sm rounded border hover:bg-gray-50"
        >
          Templates
        </Link>
      </div>

      {msg ? (
        <div className="text-sm border border-red-200 bg-red-50 text-red-800 rounded-lg px-4 py-3">
          {msg}
        </div>
      ) : null}

      <div className="bg-white rounded-xl border overflow-x-auto">
        {loading ? (
          <div className="p-12 text-center text-gray-500">Loading…</div>
        ) : logs.length === 0 ? (
          <div className="p-12 text-center text-gray-500">No logs found.</div>
        ) : (
          <table className="min-w-full text-sm">
            <thead className="bg-gray-50 text-left">
              <tr>
                <th className="px-3 py-2 border-b">When</th>
                <th className="px-3 py-2 border-b">Event</th>
                <th className="px-3 py-2 border-b">Phone</th>
                <th className="px-3 py-2 border-b">Status</th>
                <th className="px-3 py-2 border-b">Template</th>
                <th className="px-3 py-2 border-b">Provider / error</th>
              </tr>
            </thead>
            <tbody>
              {logs.map((row) => (
                <tr key={row.id} className="border-b border-gray-100 align-top">
                  <td className="px-3 py-2 whitespace-nowrap text-xs text-gray-600">
                    {row.created_at ? new Date(row.created_at).toLocaleString() : '—'}
                  </td>
                  <td className="px-3 py-2 font-mono text-xs">{row.event_key}</td>
                  <td className="px-3 py-2 font-mono text-xs">{row.phone_masked || '—'}</td>
                  <td className="px-3 py-2">
                    <span
                      className={`inline-flex px-2 py-0.5 rounded text-xs font-semibold ${
                        row.status === 'sent'
                          ? 'bg-emerald-50 text-emerald-800'
                          : row.status === 'failed'
                            ? 'bg-red-50 text-red-800'
                            : 'bg-amber-50 text-amber-800'
                      }`}
                    >
                      {row.status}
                      {row.skip_reason ? ` · ${row.skip_reason}` : ''}
                    </span>
                  </td>
                  <td className="px-3 py-2 font-mono text-xs">{row.template_id || '—'}</td>
                  <td className="px-3 py-2 text-xs text-gray-700 max-w-xs break-words">
                    {row.provider_message_id || row.error_message || '—'}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
};

export default SmsDeliveryLogs;
