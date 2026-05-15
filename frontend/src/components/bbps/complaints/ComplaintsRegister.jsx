import React, { useEffect, useState } from 'react';
import { Link, useLocation } from 'react-router-dom';
import { bbpsAPI } from '../../../services/api';
import BharatConnectBranding from '../BharatConnectBranding';
import { COMPLAINT_DISPOSITIONS, COMPLAINT_TYPES } from './complaintConstants';
import { toneClass, toUserMessage } from './complaintUiHelpers';

const METHOD_BCONNECT = 'BCONNECT';
const METHOD_MOBILE = 'MOBILE';

const ComplaintsRegister = () => {
  const location = useLocation();
  const [complaintType, setComplaintType] = useState('Transaction');
  const [method, setMethod] = useState(METHOD_BCONNECT);
  const [txnRefId, setTxnRefId] = useState('');
  const [mobile, setMobile] = useState('');
  const [fromDate, setFromDate] = useState('');
  const [toDate, setToDate] = useState('');
  const [desc, setDesc] = useState('');
  const [disposition, setDisposition] = useState(COMPLAINT_DISPOSITIONS[0]);
  const [lookupRows, setLookupRows] = useState([]);
  const [lookupLoading, setLookupLoading] = useState(false);
  const [lookupError, setLookupError] = useState('');
  const [selectedTxnRef, setSelectedTxnRef] = useState('');
  const [message, setMessage] = useState('');
  const [messageTone, setMessageTone] = useState('neutral');
  const [successPayload, setSuccessPayload] = useState(null);

  useEffect(() => {
    const pre = location.state?.txnRefId;
    if (pre) {
      setTxnRefId(String(pre));
      setMethod(METHOD_BCONNECT);
      setSelectedTxnRef('');
    }
  }, [location.state]);

  const effectiveTxnRef = method === METHOD_MOBILE ? selectedTxnRef : String(txnRefId || '').trim();

  const findTransactions = async () => {
    setLookupError('');
    setLookupRows([]);
    setSelectedTxnRef('');
    const m = String(mobile || '').replace(/\D/g, '');
    if (m.length < 10) {
      setLookupError('Enter a valid 10-digit mobile number.');
      return;
    }
    if (!fromDate || !toDate) {
      setLookupError('From date and To date are required for mobile search.');
      return;
    }
    if (fromDate > toDate) {
      setLookupError('From date cannot be after To date.');
      return;
    }
    setLookupLoading(true);
    const res = await bbpsAPI.transactionQuery({
      tracking_type: 'MOBILE_NO',
      tracking_value: m,
      from_date: fromDate,
      to_date: toDate,
    });
    setLookupLoading(false);
    if (!res.success) {
      setLookupError(res.message || 'Could not fetch transactions.');
      return;
    }
    const list = Array.isArray(res.data?.transactions) ? res.data.transactions : [];
    setLookupRows(list);
    if (list.length === 0) {
      setLookupError('No transactions found for this mobile number and date range.');
    }
  };

  const registerComplaint = async () => {
    setMessage('');
    setMessageTone('neutral');
    const summary = String(desc || '').trim();
    const tx = effectiveTxnRef;

    if (method === METHOD_BCONNECT) {
      if (!String(txnRefId || '').trim()) {
        setMessage('B-Connect Transaction ID is required.');
        setMessageTone('error');
        return;
      }
    }

    if (method === METHOD_MOBILE && !selectedTxnRef) {
      setMessage('Find your transaction using mobile search, then select a row before submitting.');
      setMessageTone('error');
      return;
    }

    if (!tx) {
      setMessage('B-Connect Transaction ID is required.');
      setMessageTone('error');
      return;
    }
    if (!disposition) {
      setMessage('Complaint disposition is required.');
      setMessageTone('error');
      return;
    }
    if (!summary) {
      setMessage('Complaint description is required.');
      setMessageTone('error');
      return;
    }
    const looksLikeBillPayRequestId = tx.length >= 20 && tx.length <= 55 && /^[A-Za-z0-9_-]+$/.test(tx);
    if (!/^CC/i.test(tx) && !/^PMBBPS/i.test(tx) && !looksLikeBillPayRequestId) {
      setMessage(
        'Use B-Connect Transaction ID (CC…), internal service ID (PMBBPS…), or the bill-pay Request ID from My Bills.'
      );
      setMessageTone('error');
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
      setSuccessPayload({
        complaint_id: id,
        status: manual ? 'MANUAL_ESCALATION_REQUIRED' : String(res.data?.status || 'ASSIGNED'),
        complaint_type: complaintType,
        disposition,
        manual_escalation_required: manual,
        created_at: new Date().toISOString(),
      });
      setMessageTone(manual ? 'warning' : 'success');
      setMessage(`${toUserMessage(res.message || (manual ? 'Manual escalation required.' : 'Complaint registered.'))}${id ? ` Reference: ${id}.` : ''}`);
      return;
    }

    const msg = toUserMessage(res.message || 'Failed to register complaint');
    const isDup = /duplicate complaint/i.test(msg);
    setMessageTone(isDup ? 'warning' : 'error');
    const details = Array.isArray(res.errors)
      ? res.errors.flatMap((e) => (Array.isArray(e) ? e : [e])).filter(Boolean).join(' ')
      : '';
    const baRid = res.data?.billavenue_request_id;
    const ridLine =
      baRid && typeof baRid === 'string'
        ? `BillAvenue request ID (for support): ${baRid}`
        : '';
    setMessage([msg, details, ridLine].filter(Boolean).join('\n\n'));
    setSuccessPayload(null);
  };

  const resetAfterSuccess = () => {
    setSuccessPayload(null);
    setMessage('');
    setDesc('');
    setTxnRefId('');
    setSelectedTxnRef('');
    setLookupRows([]);
  };

  if (successPayload) {
    const manual = successPayload.manual_escalation_required;
    return (
      <div className="max-w-2xl mx-auto bg-white rounded-xl border border-violet-100 shadow-sm p-8">
        <BharatConnectBranding stage="stage2" title="BHARAT CONNECT — RAISE COMPLAINT" />
        <h2 className="text-xl font-semibold text-emerald-700 mt-2">Complaint Registered Successfully</h2>
        <p className="text-sm text-gray-600 mt-1">Your complaint has been successfully registered.</p>

        <div className="mt-6 rounded-lg border border-sky-200 bg-sky-50/80 p-5 text-sm space-y-3">
          <div className="flex flex-wrap gap-2 justify-between">
            <span className="text-gray-500">Complaint ID</span>
            <span className="font-semibold text-gray-900">{successPayload.complaint_id || '—'}</span>
          </div>
          <div className="flex flex-wrap gap-2 justify-between items-center">
            <span className="text-gray-500">Status</span>
            <span
              className={`inline-flex border rounded-full px-3 py-0.5 text-xs font-medium ${
                manual ? 'bg-amber-100 text-amber-900 border-amber-300' : 'bg-amber-100 text-amber-900 border-amber-300'
              }`}
            >
              {manual ? 'Manual escalation' : 'Open'}
            </span>
          </div>
          <div className="flex flex-wrap gap-2 justify-between">
            <span className="text-gray-500">Type</span>
            <span className="font-medium">{successPayload.complaint_type}</span>
          </div>
          <div className="flex flex-wrap gap-2 justify-between">
            <span className="text-gray-500">Disposition</span>
            <span className="font-medium text-right max-w-[70%]">{successPayload.disposition}</span>
          </div>
          <div className="flex flex-wrap gap-2 justify-between">
            <span className="text-gray-500">Expected resolution</span>
            <span className="font-medium">{manual ? 'See manual escalation instructions' : '24–48 hours'}</span>
          </div>
          <div className="flex flex-wrap gap-2 justify-between">
            <span className="text-gray-500">Created</span>
            <span className="font-medium">
              {successPayload.created_at ? successPayload.created_at.slice(0, 10) : '—'}
            </span>
          </div>
        </div>

        {manual && (
          <p className="mt-4 text-sm text-amber-900 bg-amber-50 border border-amber-200 rounded-lg p-3">
            BillAvenue did not accept automated registration for this transaction. Use the reference ID above for support
            communication and follow email instructions if your operator requires escalation to cms@billavenue.com.
          </p>
        )}

        <p className="mt-4 text-sm text-gray-600">
          You can track status anytime from Complaint Tracking in this portal.
        </p>

        <div className="mt-8 flex flex-wrap gap-3">
          <button
            type="button"
            className="border border-gray-300 rounded-lg px-4 py-2 text-sm hover:bg-gray-50"
            onClick={resetAfterSuccess}
          >
            Submit another complaint
          </button>
          <Link to="/bill-payments/complaints/track" className="bg-blue-600 text-white rounded-lg px-4 py-2 text-sm">
            Track complaint
          </Link>
          <Link to="/bill-payments/complaints" className="text-blue-700 text-sm py-2 underline-offset-2 hover:underline">
            Back to Complaint Management
          </Link>
        </div>
      </div>
    );
  }

  return (
    <div className="max-w-3xl mx-auto bg-white rounded-xl border border-violet-100 shadow-sm p-6 md:p-8">
      <BharatConnectBranding stage="stage2" title="BHARAT CONNECT — RAISE COMPLAINT" />
      <Link
        to="/bill-payments/complaints"
        className="text-sm text-blue-700 hover:underline mb-6 inline-block"
      >
        ← Back to Complaint Management
      </Link>

      <div className="space-y-6">
        <div>
          <p className="text-sm font-medium text-gray-700 mb-2">Type Of Complaint</p>
          <div className="flex flex-wrap gap-4">
            {COMPLAINT_TYPES.map((t) => (
              <label key={t.value} className="inline-flex items-center gap-2 cursor-pointer">
                <input
                  type="radio"
                  name="ctype"
                  checked={complaintType === t.value}
                  onChange={() => setComplaintType(t.value)}
                />
                <span>{t.label}</span>
              </label>
            ))}
          </div>
        </div>

        <div>
          <p className="text-sm font-medium text-gray-700 mb-2">Transaction Method</p>
          <div className="flex flex-wrap gap-4">
            <label className="inline-flex items-center gap-2 cursor-pointer">
              <input
                type="radio"
                name="method"
                checked={method === METHOD_BCONNECT}
                onChange={() => {
                  setMethod(METHOD_BCONNECT);
                  setSelectedTxnRef('');
                  setLookupRows([]);
                }}
              />
              <span>B-Connect TXN ID</span>
            </label>
            <label className="inline-flex items-center gap-2 cursor-pointer">
              <input
                type="radio"
                name="method"
                checked={method === METHOD_MOBILE}
                onChange={() => {
                  setMethod(METHOD_MOBILE);
                  setTxnRefId('');
                }}
              />
              <span>Mobile Number</span>
            </label>
          </div>
        </div>

        {method === METHOD_BCONNECT && (
          <>
            <div>
              <label className="block text-sm text-gray-600 mb-1">
                B-Connect TXN ID <span className="text-red-600">*</span>
              </label>
              <input
                className="w-full border rounded-lg px-3 py-2"
                value={txnRefId}
                onChange={(e) => setTxnRefId(e.target.value)}
                placeholder="Enter B-Connect TXN ID"
              />
              <p className="mt-1 text-xs text-gray-500">
                Only the CC… reference is sent when you submit. Use Mobile Number below if you need to search by date
                range first.
              </p>
            </div>
          </>
        )}

        {method === METHOD_MOBILE && (
          <>
            <div>
              <label className="block text-sm text-gray-600 mb-1">
                Mobile Number <span className="text-red-600">*</span>
              </label>
              <input
                className="w-full border rounded-lg px-3 py-2"
                value={mobile}
                onChange={(e) => setMobile(e.target.value)}
                placeholder="Enter Mobile Number"
                inputMode="numeric"
                maxLength={15}
              />
            </div>
            <div className="grid sm:grid-cols-2 gap-4">
              <div>
                <label className="block text-sm text-gray-600 mb-1">
                  From Date <span className="text-red-600">*</span>
                </label>
                <input
                  type="date"
                  className="w-full border rounded-lg px-3 py-2"
                  value={fromDate}
                  onChange={(e) => setFromDate(e.target.value)}
                />
              </div>
              <div>
                <label className="block text-sm text-gray-600 mb-1">
                  To Date <span className="text-red-600">*</span>
                </label>
                <input
                  type="date"
                  className="w-full border rounded-lg px-3 py-2"
                  value={toDate}
                  onChange={(e) => setToDate(e.target.value)}
                />
              </div>
            </div>
            <div>
              <button
                type="button"
                className="bg-blue-600 text-white rounded-lg px-5 py-2 text-sm disabled:opacity-50"
                disabled={lookupLoading}
                onClick={findTransactions}
              >
                {lookupLoading ? 'Searching…' : 'Find transaction'}
              </button>
              {lookupError && <p className="mt-2 text-sm text-red-700">{lookupError}</p>}
            </div>

            {lookupRows.length > 0 && (
              <div className="border rounded-lg overflow-hidden">
                <p className="text-sm font-medium text-gray-700 px-3 py-2 bg-gray-50 border-b">
                  Select a transaction for your complaint
                </p>
                <div className="max-h-60 overflow-auto divide-y">
                  {lookupRows.map((r, idx) => {
                    const ref = String(r.txnReferenceId || r.txnRefId || '').trim();
                    const sel = ref && selectedTxnRef === ref;
                    return (
                      <button
                        key={`${ref}-${idx}`}
                        type="button"
                        className={`w-full text-left px-3 py-2 text-sm hover:bg-violet-50 ${sel ? 'bg-violet-100' : ''}`}
                        onClick={() => setSelectedTxnRef(ref)}
                      >
                        <div className="font-medium">{ref || 'Unknown ref'}</div>
                        <div className="text-gray-600 text-xs">
                          {(r.billerName || r.billerId || '-') + ' · ' + (r.txnDate || '-')}
                        </div>
                      </button>
                    );
                  })}
                </div>
                {selectedTxnRef && (
                  <p className="text-xs text-emerald-800 bg-emerald-50 px-3 py-2 border-t">
                    Selected B-Connect TXN ID: <strong>{selectedTxnRef}</strong>
                  </p>
                )}
              </div>
            )}
          </>
        )}

        <div>
          <label className="block text-sm text-gray-600 mb-1">
            Complaint Disposition <span className="text-red-600">*</span>
          </label>
          <select
            className="w-full border rounded-lg px-3 py-2"
            value={disposition}
            onChange={(e) => setDisposition(e.target.value)}
          >
            {COMPLAINT_DISPOSITIONS.map((d) => (
              <option key={d} value={d}>
                {d}
              </option>
            ))}
          </select>
        </div>

        <div>
          <label className="block text-sm text-gray-600 mb-1">
            Complaint Description <span className="text-red-600">*</span>
          </label>
          <textarea
            className="w-full border rounded-lg px-3 py-2"
            rows={4}
            value={desc}
            onChange={(e) => setDesc(e.target.value)}
            placeholder="Please describe your complaint in detail..."
          />
        </div>

        <p className="text-xs text-gray-500">
          Use B-Connect Transaction ID from receipt (CC…) or internal service ID (PMBBPS…). For mobile search, pick a
          date range that includes the payment day; direct B-Connect submission uses only the transaction reference and
          disposition.
        </p>

        {message && (
          <div className={`text-sm rounded border p-3 whitespace-pre-wrap ${toneClass(messageTone)}`}>{message}</div>
        )}

        <div className="flex justify-end pt-2">
          <button
            type="button"
            className="bg-blue-600 text-white rounded-lg px-8 py-2.5 font-medium shadow-sm hover:bg-blue-700"
            onClick={registerComplaint}
          >
            Submit Complaint
          </button>
        </div>
      </div>
    </div>
  );
};

export default ComplaintsRegister;
