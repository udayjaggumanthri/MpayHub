import React, { useEffect, useState } from 'react';
import { bbpsAPI } from '../../services/api';
import BharatConnectBranding from './BharatConnectBranding';

const DISPOSITIONS = [
  'Transaction Successful, Amount Debited but services not received',
  'Transaction Successful, Amount Debited but Service Disconnected or Service Stopped',
  'Transaction Successful, Amount Debited but Late Payment Surcharge Charges add in next bill',
  'Erroneously paid in wrong account',
  'Duplicate Payment',
  'Erroneously paid the wrong amount',
  'Payment information not received from Biller or Delay in receiving payment information from the Biller',
  'Bill Paid but Amount not adjusted or still showing due amount',
];

const toneClass = (tone) => {
  if (tone === 'success') return 'border-emerald-200 bg-emerald-50 text-emerald-900';
  if (tone === 'warning') return 'border-amber-300 bg-amber-50 text-amber-950';
  if (tone === 'error') return 'border-red-200 bg-red-50 text-red-900';
  return 'border-slate-200 bg-slate-50 text-slate-800';
};

const statusBadgeClass = (status) => {
  const s = String(status || '').toUpperCase();
  if (s === 'MANUAL_ESCALATION_REQUIRED') return 'bg-amber-100 text-amber-900 border-amber-300';
  if (s === 'ASSIGNED' || s === 'OPEN') return 'bg-blue-100 text-blue-900 border-blue-300';
  if (s === 'RESOLVED' || s === 'CLOSED') return 'bg-emerald-100 text-emerald-900 border-emerald-300';
  return 'bg-gray-100 text-gray-800 border-gray-300';
};

const statusLabel = (status) => {
  const s = String(status || '').toUpperCase();
  if (s === 'MANUAL_ESCALATION_REQUIRED') return 'Needs manual escalation';
  if (s === 'ASSIGNED' || s === 'OPEN') return 'In progress';
  if (s === 'RESOLVED') return 'Resolved';
  if (s === 'CLOSED') return 'Closed';
  if (s === 'REJECTED') return 'Rejected';
  return s ? s.replaceAll('_', ' ').toLowerCase().replace(/\b\w/g, (c) => c.toUpperCase()) : 'Unknown';
};

const toUserMessage = (msg) => {
  const raw = String(msg || '').trim();
  if (!raw) return '';
  if (/manual escalation/i.test(raw) || /cms@billavenue\.com/i.test(raw)) {
    return 'Your complaint is saved. The provider needs manual escalation for this case. Please contact support to proceed.';
  }
  return raw;
};

const BbpsComplaintManager = () => {
  const [txnRefId, setTxnRefId] = useState('');
  const [desc, setDesc] = useState('');
  const [disposition, setDisposition] = useState(DISPOSITIONS[0]);
  const [complaintId, setComplaintId] = useState('');
  const [message, setMessage] = useState('');
  const [messageTone, setMessageTone] = useState('neutral'); // 'success' | 'warning' | 'error' | 'neutral'
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

  const registerComplaint = async () => {
    setMessage('');
    setMessageTone('neutral');
    setTracking(null);
    setTrackMeta(null);
    const tx = String(txnRefId || '').trim();
    const summary = String(desc || '').trim();
    if (!tx) {
      setMessage('B-Connect Transaction ID is required.');
      return;
    }
    if (!summary) {
      setMessage('Complaint description is required.');
      return;
    }
    if (!/^CC/i.test(tx) && !/^PMBBPS/i.test(tx)) {
      setMessage('Use B-Connect Transaction ID (CC...) or internal service ID (PMBBPS...).');
      return;
    }
    const res = await bbpsAPI.registerComplaint({
      txn_ref_id: tx,
      complaint_desc: summary,
      complaint_disposition: disposition,
    });
    if (res.success) {
      const manual = Boolean(res.data?.manual_escalation_required);
      const id = res.data?.complaint_id || '';
      setMessageTone(manual ? 'warning' : 'success');
      const suffix = id ? ` Reference: ${id}.` : '';
      setMessage(`${toUserMessage(res.message || (manual ? 'Manual escalation required.' : 'Complaint registered.'))}${suffix}`);
      setComplaintId(id || complaintId);
      loadHistory(1);
    } else {
      const msg = toUserMessage(res.message || 'Failed to register complaint');
      const isDup = /duplicate complaint/i.test(msg);
      setMessageTone(isDup ? 'warning' : 'error');
      const details = Array.isArray(res.errors)
        ? res.errors.flatMap((e) => (Array.isArray(e) ? e : [e])).filter(Boolean).join(' ')
        : '';
      setMessage([msg, details].filter(Boolean).join(' '));
      if (isDup) {
        const m = msg.match(/Complaint ID\s+([A-Za-z0-9\-]+)/i);
        if (m && m[1]) {
          setComplaintId(m[1]);
        }
      }
    }
  };

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
    <div className="max-w-6xl mx-auto bg-white rounded-xl border border-gray-200 shadow-sm p-6">
      <BharatConnectBranding stage="stage2" title="Complaint Management" />
      <div className="grid md:grid-cols-2 gap-3">
        <input className="border rounded px-3 py-2" value={txnRefId} onChange={(e) => setTxnRefId(e.target.value)} placeholder="B-Connect Transaction ID (CC...)" />
        <select className="border rounded px-3 py-2" value={disposition} onChange={(e) => setDisposition(e.target.value)}>
          {DISPOSITIONS.map((d) => <option key={d} value={d}>{d}</option>)}
        </select>
        <textarea className="border rounded px-3 py-2 md:col-span-2" value={desc} onChange={(e) => setDesc(e.target.value)} placeholder="Complaint description" rows={3} />
      </div>
      <p className="mt-2 text-xs text-gray-500">
        Use B-Connect Transaction ID from receipt (CC...) or your internal transaction/service ID (PMBBPS...).
      </p>
      <button className="mt-3 bg-blue-600 text-white rounded px-4 py-2" onClick={registerComplaint}>Register Complaint</button>

      <div className="mt-6 grid md:grid-cols-3 gap-3">
        <input className="border rounded px-3 py-2 md:col-span-2" value={complaintId} onChange={(e) => setComplaintId(e.target.value)} placeholder="Complaint ID" />
        <button className="bg-slate-700 text-white rounded px-4 py-2" onClick={trackComplaint}>Track Complaint</button>
      </div>

      {message && (
        <div className={`mt-3 text-sm rounded border p-3 ${toneClass(messageTone)}`}>
          {message}
        </div>
      )}
      {tracking && (
        <div className="mt-3 space-y-2">
          {trackMeta?.manual_escalation_required && (
            <p className="text-sm text-amber-900 bg-amber-50 border border-amber-200 rounded p-2">
              This case needs manual escalation from our support side. Keep your complaint reference safe and contact support for next steps.
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

      <div className="mt-8 border-t pt-5">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <h3 className="text-lg font-semibold text-gray-900">Previously Submitted Complaints</h3>
          <button
            className="text-sm border rounded px-3 py-1.5 hover:bg-gray-50"
            onClick={() => loadHistory(historyMeta.page || 1)}
            disabled={historyLoading}
          >
            {historyLoading ? 'Refreshing...' : 'Reload'}
          </button>
        </div>
        <div className="mt-3 grid md:grid-cols-3 gap-3">
          <input
            className="border rounded px-3 py-2"
            value={historyQuery}
            onChange={(e) => setHistoryQuery(e.target.value)}
            placeholder="Search complaint id / txn ref / service id"
          />
          <select className="border rounded px-3 py-2" value={historyStatus} onChange={(e) => setHistoryStatus(e.target.value)}>
            <option value="">All statuses</option>
            {Object.keys(historyMeta.status_counts || {}).map((s) => (
              <option key={s} value={s}>{statusLabel(s)} ({historyMeta.status_counts[s]})</option>
            ))}
          </select>
          <button className="bg-slate-700 text-white rounded px-4 py-2" onClick={() => loadHistory(1)}>Apply Filters</button>
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
    </div>
  );
};

export default BbpsComplaintManager;
