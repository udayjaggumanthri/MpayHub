import React, { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { bbpsAPI } from '../../../services/api';
import BharatConnectBranding from '../BharatConnectBranding';
import { statusBadgeClass, statusLabel, toneClass, toUserMessage } from './complaintUiHelpers';

const ComplaintHistoryPanel = () => {
  const [complaintId, setComplaintId] = useState('');
  const [message, setMessage] = useState('');
  const [messageTone, setMessageTone] = useState('neutral');
  const [tracking, setTracking] = useState(null);
  const [trackMeta, setTrackMeta] = useState(null);
  const [history, setHistory] = useState([]);
  const [historyMeta, setHistoryMeta] = useState({ total: 0, page: 1, page_size: 10, has_next: false, status_counts: {} });
  const [historyLoading, setHistoryLoading] = useState(false);
  const [historyStatus, setHistoryStatus] = useState('');
  const [historyQuery, setHistoryQuery] = useState('');
  const [refreshingId, setRefreshingId] = useState('');

  const loadHistory = async (page = 1) => {
    setHistoryLoading(true);
    const res = await bbpsAPI.getComplaintHistory({
      page,
      page_size: 10,
      status: historyStatus || undefined,
      q: historyQuery || undefined,
    });
    if (res.success) {
      const data = res.data || {};
      setHistory(Array.isArray(data.complaints) ? data.complaints : []);
      setHistoryMeta({
        total: Number(data.total || 0),
        page: Number(data.page || page),
        page_size: Number(data.page_size || 10),
        has_next: Boolean(data.has_next),
        status_counts: data.status_counts || {},
      });
    } else {
      setMessageTone('error');
      setMessage(res.message || 'Failed to load complaint history');
    }
    setHistoryLoading(false);
  };

  useEffect(() => {
    loadHistory(1);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const trackComplaint = async () => {
    setTracking(null);
    setTrackMeta(null);
    const res = await bbpsAPI.trackComplaint({ complaint_id: complaintId });
    if (res.success) {
      setTracking(res.data?.response || {});
      setTrackMeta({
        manual_escalation_required: Boolean(res.data?.manual_escalation_required),
        provider_track_eligible: Boolean(res.data?.provider_track_eligible),
      });
      setMessageTone(res.data?.manual_escalation_required ? 'warning' : 'success');
      setMessage(toUserMessage(res.message || 'Complaint status fetched.'));
      loadHistory(historyMeta.page || 1);
    } else {
      setMessageTone('error');
      setMessage(toUserMessage(res.message || 'Failed to track complaint'));
    }
  };

  const refreshOneComplaint = async (id) => {
    setRefreshingId(id);
    const res = await bbpsAPI.refreshComplaintStatus({ complaint_id: id });
    if (res.success) {
      setMessageTone(res.data?.manual_escalation_required ? 'warning' : 'success');
      setMessage(toUserMessage(res.message || 'Complaint status refreshed.'));
      if (String(complaintId || '').trim() === String(id || '').trim()) {
        setTracking(res.data?.response || null);
        setTrackMeta({
          manual_escalation_required: Boolean(res.data?.manual_escalation_required),
          provider_track_eligible: Boolean(res.data?.provider_track_eligible),
        });
      }
      loadHistory(historyMeta.page || 1);
    } else {
      setMessageTone('error');
      setMessage(toUserMessage(res.message || 'Failed to refresh complaint status'));
    }
    setRefreshingId('');
  };

  return (
    <div className="max-w-6xl mx-auto bg-white rounded-xl border border-violet-100 shadow-sm p-6">
      <BharatConnectBranding stage="stage2" title="Complaint History" />
      <Link to="/bill-payments/complaints" className="text-sm text-blue-700 hover:underline mb-4 inline-block">
        ← Back to Complaint Management
      </Link>

      <div className="grid md:grid-cols-3 gap-3 mb-6 border-b pb-6">
        <input
          className="border rounded px-3 py-2 md:col-span-2"
          value={complaintId}
          onChange={(e) => setComplaintId(e.target.value)}
          placeholder="Complaint ID"
        />
        <button className="bg-slate-700 text-white rounded px-4 py-2" onClick={trackComplaint}>
          Track Complaint
        </button>
      </div>

      {message && (
        <div className={`mb-4 text-sm rounded border p-3 ${toneClass(messageTone)}`}>{message}</div>
      )}
      {tracking && (
        <div className="mb-6 space-y-2">
          {trackMeta?.manual_escalation_required && (
            <p className="text-sm text-amber-900 bg-amber-50 border border-amber-200 rounded p-2">
              This case needs manual escalation from our support side. Keep your complaint reference safe and contact
              support for next steps.
            </p>
          )}
          {(() => {
            const tr = tracking.complaintTrackingResp || tracking;
            if (tr && typeof tr === 'object') {
              return (
                <dl className="text-sm grid grid-cols-1 sm:grid-cols-2 gap-x-4 gap-y-1 border rounded p-3 bg-white">
                  {tr.complaintId != null && (
                    <>
                      <dt className="text-gray-500">Complaint ID</dt>
                      <dd className="font-medium">{String(tr.complaintId)}</dd>
                    </>
                  )}
                  {tr.complaintStatus != null && (
                    <>
                      <dt className="text-gray-500">Status</dt>
                      <dd className="font-medium">{statusLabel(tr.complaintStatus)}</dd>
                    </>
                  )}
                  {(tr.complaintRemarks != null || tr.remarks != null) && (
                    <>
                      <dt className="text-gray-500">Update</dt>
                      <dd className="sm:col-span-2">{String(tr.complaintRemarks ?? tr.remarks ?? '')}</dd>
                    </>
                  )}
                </dl>
              );
            }
            return null;
          })()}
        </div>
      )}

      <div className="flex flex-wrap items-center justify-between gap-3 mb-4">
        <h3 className="text-lg font-semibold text-gray-900">Previously Submitted Complaints</h3>
        <button
          className="text-sm border rounded px-3 py-1.5 hover:bg-gray-50"
          onClick={() => loadHistory(historyMeta.page || 1)}
          disabled={historyLoading}
        >
          {historyLoading ? 'Refreshing...' : 'Reload'}
        </button>
      </div>
      <div className="grid md:grid-cols-3 gap-3">
        <input
          className="border rounded px-3 py-2"
          value={historyQuery}
          onChange={(e) => setHistoryQuery(e.target.value)}
          placeholder="Search complaint id / txn ref / service id"
        />
        <select className="border rounded px-3 py-2" value={historyStatus} onChange={(e) => setHistoryStatus(e.target.value)}>
          <option value="">All statuses</option>
          {Object.keys(historyMeta.status_counts || {}).map((s) => (
            <option key={s} value={s}>
              {statusLabel(s)} ({historyMeta.status_counts[s]})
            </option>
          ))}
        </select>
        <button className="bg-slate-700 text-white rounded px-4 py-2" onClick={() => loadHistory(1)}>
          Apply Filters
        </button>
      </div>

      <div className="mt-4 overflow-auto border rounded">
        <table className="min-w-full text-sm">
          <thead className="bg-gray-50">
            <tr className="text-left text-gray-600">
              <th className="px-3 py-2">Complaint ID</th>
              <th className="px-3 py-2">Txn Ref</th>
              <th className="px-3 py-2">Status</th>
              <th className="px-3 py-2">Issue Type</th>
              <th className="px-3 py-2">Updated</th>
              <th className="px-3 py-2">Action</th>
            </tr>
          </thead>
          <tbody>
            {history.length === 0 && (
              <tr>
                <td className="px-3 py-4 text-gray-500" colSpan={6}>
                  {historyLoading ? 'Loading complaint history...' : 'No complaints found.'}
                </td>
              </tr>
            )}
            {history.map((row) => (
              <tr key={row.id} className="border-t">
                <td className="px-3 py-2 font-medium">{row.complaint_id || '-'}</td>
                <td className="px-3 py-2">{row.txn_ref_id || '-'}</td>
                <td className="px-3 py-2">
                  <span className={`inline-flex border rounded px-2 py-0.5 text-xs font-medium ${statusBadgeClass(row.complaint_status)}`}>
                    {statusLabel(row.complaint_status)}
                  </span>
                </td>
                <td className="px-3 py-2 max-w-sm truncate" title={row.complaint_disposition || ''}>
                  {row.complaint_disposition || '-'}
                </td>
                <td className="px-3 py-2">{row.updated_at ? new Date(row.updated_at).toLocaleString() : '-'}</td>
                <td className="px-3 py-2">
                  <div className="flex flex-wrap gap-2">
                    <button
                      className="text-xs border rounded px-2 py-1 hover:bg-gray-50"
                      type="button"
                      onClick={() => {
                        setComplaintId(row.complaint_id || '');
                        setTracking(null);
                        setTrackMeta(null);
                      }}
                    >
                      Use in tracker
                    </button>
                    <button
                      className="text-xs bg-blue-600 text-white rounded px-2 py-1 disabled:opacity-60"
                      type="button"
                      disabled={refreshingId === row.complaint_id}
                      onClick={() => refreshOneComplaint(row.complaint_id)}
                    >
                      {refreshingId === row.complaint_id ? 'Refreshing...' : 'Refresh status'}
                    </button>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div className="mt-3 flex items-center justify-between text-xs text-gray-600">
        <span>Total complaints: {historyMeta.total}</span>
        <div className="flex gap-2">
          <button
            className="border rounded px-2 py-1 disabled:opacity-40"
            disabled={historyMeta.page <= 1 || historyLoading}
            onClick={() => loadHistory(Math.max(1, (historyMeta.page || 1) - 1))}
          >
            Previous
          </button>
          <button
            className="border rounded px-2 py-1 disabled:opacity-40"
            disabled={!historyMeta.has_next || historyLoading}
            onClick={() => loadHistory((historyMeta.page || 1) + 1)}
          >
            Next
          </button>
        </div>
      </div>
    </div>
  );
};

export default ComplaintHistoryPanel;
