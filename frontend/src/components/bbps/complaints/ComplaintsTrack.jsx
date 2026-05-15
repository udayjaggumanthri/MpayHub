import React, { useState } from 'react';
import { Link } from 'react-router-dom';
import { bbpsAPI } from '../../../services/api';
import BharatConnectBranding from '../BharatConnectBranding';
import { COMPLAINT_TYPES } from './complaintConstants';
import { statusLabel, toUserMessage, toneClass } from './complaintUiHelpers';

const ComplaintsTrack = () => {
  const [complaintId, setComplaintId] = useState('');
  const [complaintType, setComplaintType] = useState('Transaction');
  const [message, setMessage] = useState('');
  const [messageTone, setMessageTone] = useState('neutral');
  const [tracking, setTracking] = useState(null);
  const [trackMeta, setTrackMeta] = useState(null);

  const trackComplaint = async () => {
    setTracking(null);
    setTrackMeta(null);
    const id = String(complaintId || '').trim();
    if (!id) {
      setMessageTone('error');
      setMessage('Complaint ID is required.');
      return;
    }
    const res = await bbpsAPI.trackComplaint({ complaint_id: id });
    if (res.success) {
      setTracking(res.data?.response || {});
      setTrackMeta({
        manual_escalation_required: Boolean(res.data?.manual_escalation_required),
        provider_track_eligible: Boolean(res.data?.provider_track_eligible),
      });
      setMessageTone(res.data?.manual_escalation_required ? 'warning' : 'success');
      setMessage(toUserMessage(res.message || 'Complaint status fetched.'));
    } else {
      setMessageTone('error');
      const hint = res.data?.hint ? `\n\n${res.data.hint}` : '';
      setMessage(toUserMessage(res.message || 'Failed to track complaint') + hint);
    }
  };

  return (
    <div className="max-w-3xl mx-auto bg-white rounded-xl border border-violet-100 shadow-sm p-6 md:p-8">
      <BharatConnectBranding stage="stage2" title="TRACK COMPLAINT" />
      <Link to="/bill-payments/complaints" className="text-sm text-blue-700 hover:underline mb-6 inline-block">
        ← Back to Complaint Management
      </Link>

      <div className="grid gap-4 max-w-xl">
        <div>
          <label className="block text-xs uppercase tracking-wide text-gray-500 mb-1">Complaint ID</label>
          <input
            className="w-full border rounded-lg px-3 py-2"
            value={complaintId}
            onChange={(e) => setComplaintId(e.target.value)}
            placeholder="Complaint ID"
          />
        </div>
        <div>
          <label className="block text-xs uppercase tracking-wide text-gray-500 mb-1">Type of Complaint</label>
          <select
            className="w-full border rounded-lg px-3 py-2 bg-white"
            value={complaintType}
            onChange={(e) => setComplaintType(e.target.value)}
          >
            {COMPLAINT_TYPES.map((t) => (
              <option key={t.value} value={t.value}>
                {t.label}
              </option>
            ))}
            <option value="Service" disabled>
              Service (coming soon)
            </option>
          </select>
          <p className="text-xs text-gray-500 mt-1">Tracking uses your complaint ID; type is for your records.</p>
        </div>
        <div className="flex justify-end pt-2">
          <button
            type="button"
            className="bg-blue-600 text-white rounded-lg px-8 py-2.5 font-medium shadow-sm hover:bg-blue-700"
            onClick={trackComplaint}
          >
            Track
          </button>
        </div>
      </div>

      {message && (
        <div className={`mt-6 text-sm rounded border p-3 ${toneClass(messageTone)}`}>{message}</div>
      )}

      {tracking && (
        <div className="mt-6 space-y-2">
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
                <dl className="text-sm grid grid-cols-1 sm:grid-cols-2 gap-x-4 gap-y-1 border rounded-lg p-4 bg-gray-50/80">
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
    </div>
  );
};

export default ComplaintsTrack;
