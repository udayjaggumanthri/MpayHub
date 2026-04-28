import React, { useState } from 'react';
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

const BbpsComplaintManager = () => {
  const [txnRefId, setTxnRefId] = useState('');
  const [desc, setDesc] = useState('');
  const [disposition, setDisposition] = useState(DISPOSITIONS[0]);
  const [complaintId, setComplaintId] = useState('');
  const [message, setMessage] = useState('');
  const [tracking, setTracking] = useState(null);

  const registerComplaint = async () => {
    setMessage('');
    const res = await bbpsAPI.registerComplaint({
      txn_ref_id: txnRefId,
      complaint_desc: desc,
      complaint_disposition: disposition,
    });
    if (res.success) {
      setMessage(`Complaint registered. Complaint ID: ${res.data?.complaint_id || '-'}`);
      setComplaintId(res.data?.complaint_id || complaintId);
    } else {
      setMessage(res.message || 'Failed to register complaint');
    }
  };

  const trackComplaint = async () => {
    setTracking(null);
    const res = await bbpsAPI.trackComplaint({ complaint_id: complaintId });
    if (res.success) {
      setTracking(res.data?.response || {});
      setMessage('Complaint status fetched.');
    } else {
      setMessage(res.message || 'Failed to track complaint');
    }
  };

  return (
    <div className="max-w-6xl mx-auto bg-white rounded-xl border border-gray-200 shadow-sm p-6">
      <BharatConnectBranding stage="stage2" title="Complaint Management" />
      <div className="grid md:grid-cols-2 gap-3">
        <input className="border rounded px-3 py-2" value={txnRefId} onChange={(e) => setTxnRefId(e.target.value)} placeholder="B-Connect Transaction ID" />
        <select className="border rounded px-3 py-2" value={disposition} onChange={(e) => setDisposition(e.target.value)}>
          {DISPOSITIONS.map((d) => <option key={d} value={d}>{d}</option>)}
        </select>
        <textarea className="border rounded px-3 py-2 md:col-span-2" value={desc} onChange={(e) => setDesc(e.target.value)} placeholder="Complaint description" rows={3} />
      </div>
      <button className="mt-3 bg-blue-600 text-white rounded px-4 py-2" onClick={registerComplaint}>Register Complaint</button>

      <div className="mt-6 grid md:grid-cols-3 gap-3">
        <input className="border rounded px-3 py-2 md:col-span-2" value={complaintId} onChange={(e) => setComplaintId(e.target.value)} placeholder="Complaint ID" />
        <button className="bg-slate-700 text-white rounded px-4 py-2" onClick={trackComplaint}>Track Complaint</button>
      </div>

      {message && <div className="mt-3 text-sm rounded border border-slate-200 bg-slate-50 p-2">{message}</div>}
      {tracking && (
        <pre className="mt-3 text-xs bg-gray-50 border rounded p-3 overflow-auto">{JSON.stringify(tracking, null, 2)}</pre>
      )}
    </div>
  );
};

export default BbpsComplaintManager;
