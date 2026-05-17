import React, { useState, useEffect } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { bbpsAPI } from '../../services/api';
import BharatConnectBranding from './BharatConnectBranding';
import {
  buildTransactionQueryFields,
  fmtVal,
  pickTxnReferenceId,
} from './bbpsTransactionQueryFields';

const TransactionDetailCard = ({ row, onRaiseComplaint }) => {
  const fields = buildTransactionQueryFields(row);
  const txnRef = pickTxnReferenceId(row);

  const Field = ({ label, value }) => (
    <div>
      <div className="text-xs text-gray-500">{label}</div>
      <div className="font-semibold text-gray-900 break-all">{fmtVal(value)}</div>
    </div>
  );

  return (
    <div className="mt-8 border border-indigo-100 rounded-xl bg-white shadow-sm overflow-hidden">
      <div className="bg-gradient-to-r from-indigo-50 to-white px-5 py-3 border-b border-indigo-100">
        <h3 className="text-lg font-semibold text-indigo-900">Query Transaction</h3>
        <p className="text-sm text-gray-600">
          You can verify the status of your online transaction using your mobile number or transaction reference.
        </p>
      </div>
      {fields.length === 0 ? (
        <p className="p-5 text-sm text-gray-600">No transaction details were returned for this record.</p>
      ) : (
        <div className="p-5 grid md:grid-cols-2 gap-x-8 gap-y-4 text-sm">
          {fields.map((f) =>
            f.isStatus ? (
              <div key={f.key}>
                <div className="text-xs text-gray-500">{f.label}</div>
                <span
                  className={`inline-flex mt-1 rounded-full px-3 py-0.5 text-xs font-semibold border ${
                    String(f.value).toUpperCase().includes('SUCCESS') ||
                    String(f.value).toUpperCase().includes('PAID')
                      ? 'bg-emerald-100 text-emerald-900 border-emerald-300'
                      : 'bg-gray-100 text-gray-800 border-gray-300'
                  }`}
                >
                  {f.value}
                </span>
              </div>
            ) : (
              <Field key={f.key} label={f.label} value={f.value} />
            )
          )}
        </div>
      )}
      {onRaiseComplaint && txnRef && (
        <div className="px-5 pb-5 flex justify-end">
          <button
            type="button"
            className="bg-blue-600 hover:bg-blue-700 text-white rounded-lg px-5 py-2 text-sm font-medium"
            onClick={() => onRaiseComplaint(txnRef)}
          >
            Raise complaint for this transaction
          </button>
        </div>
      )}
    </div>
  );
};

const BbpsTransactionQuery = ({ variant = 'standalone' }) => {
  const navigate = useNavigate();
  const complaintsMode = variant === 'complaints';

  const [trackingType, setTrackingType] = useState(complaintsMode ? 'MOBILE_NO' : 'TRANS_REF_ID');
  const [trackingValue, setTrackingValue] = useState('');
  const [rows, setRows] = useState([]);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const [selectedIdx, setSelectedIdx] = useState(-1);

  useEffect(() => {
    if (!complaintsMode) return;
    if (rows.length === 1) setSelectedIdx(0);
  }, [complaintsMode, rows]);

  const setSearchKind = (kind) => {
    setTrackingType(kind);
    setRows([]);
    setSelectedIdx(-1);
    setError('');
  };

  const onSearch = async () => {
    setError('');
    setLoading(true);
    setSelectedIdx(-1);
    const payload = { tracking_type: trackingType, tracking_value: trackingValue.trim() };
    const res = await bbpsAPI.transactionQuery(payload);
    setLoading(false);
    if (!res.success) {
      setRows([]);
      setError(res.message || 'Query failed');
      return;
    }
    setRows(Array.isArray(res.data?.transactions) ? res.data.transactions : []);
  };

  const selectedRow = selectedIdx >= 0 && selectedIdx < rows.length ? rows[selectedIdx] : null;

  const goRaiseComplaint = (txnRef) => {
    navigate('/bill-payments/complaints/register', { state: { txnRefId: txnRef } });
  };

  const listLabel = (r, idx) => {
    const ref = pickTxnReferenceId(r) || `#${idx + 1}`;
    const biller = String(r.billerName || r.biller_name || r.billerId || r.biller_id || r.biller || '').trim() || '—';
    const when = String(r.txnDate || r.txn_date || r.transactionDateTime || '').trim() || '—';
    return { ref, sub: `${biller} · ${when}` };
  };

  const outerClass = complaintsMode
    ? 'max-w-6xl mx-auto bg-white rounded-xl border border-violet-100 shadow-sm p-6 md:p-8'
    : 'max-w-6xl mx-auto bg-white rounded-xl border border-gray-200 shadow-sm p-6';

  const title = complaintsMode ? 'SEARCH TRANSACTION' : 'Transaction Query';

  return (
    <div className={outerClass}>
      <BharatConnectBranding stage="stage2" title={title} />
      {complaintsMode && (
        <Link to="/bill-payments/complaints" className="text-sm text-blue-700 hover:underline mb-4 inline-block">
          ← Back to Complaint Management
        </Link>
      )}

      {complaintsMode ? (
        <div className="space-y-6">
          <div>
            <p className="text-sm font-medium text-gray-700 mb-2">type:</p>
            <div className="flex flex-wrap gap-6">
              <label className="inline-flex items-center gap-2 cursor-pointer">
                <input
                  type="radio"
                  name="tq-kind"
                  checked={trackingType === 'MOBILE_NO'}
                  onChange={() => setSearchKind('MOBILE_NO')}
                />
                <span>Mobile Number</span>
              </label>
              <label className="inline-flex items-center gap-2 cursor-pointer">
                <input
                  type="radio"
                  name="tq-kind"
                  checked={trackingType === 'TRANS_REF_ID'}
                  onChange={() => setSearchKind('TRANS_REF_ID')}
                />
                <span>B-Connect TXN ID</span>
              </label>
            </div>
          </div>

          <div className="flex flex-col sm:flex-row gap-4 items-end">
            <div className="flex-1 w-full">
              <label className="block text-xs text-gray-500 mb-1">
                {trackingType === 'MOBILE_NO' ? 'Mobile Number' : 'B-Connect TXN ID'}
              </label>
              <input
                className="border rounded-lg px-3 py-2 w-full"
                value={trackingValue}
                onChange={(e) => setTrackingValue(e.target.value)}
                placeholder={trackingType === 'MOBILE_NO' ? 'Enter Mobile Number' : 'Enter B-Connect TXN ID'}
              />
            </div>
            <button
              className="bg-blue-600 text-white rounded-lg px-6 py-2 w-full sm:w-auto disabled:opacity-50 shrink-0"
              disabled={loading || !trackingValue.trim()}
              onClick={onSearch}
            >
              {loading ? 'Fetching…' : 'Fetch Transaction'}
            </button>
          </div>
        </div>
      ) : (
        <div className="grid md:grid-cols-4 gap-3">
          <select className="border rounded px-3 py-2" value={trackingType} onChange={(e) => setTrackingType(e.target.value)}>
            <option value="TRANS_REF_ID">B-Connect Transaction ID</option>
            <option value="MOBILE_NO">Mobile Number</option>
            <option value="REQUEST_ID">Request ID</option>
          </select>
          <input
            className="border rounded px-3 py-2 md:col-span-2"
            value={trackingValue}
            onChange={(e) => setTrackingValue(e.target.value)}
            placeholder={
              trackingType === 'TRANS_REF_ID'
                ? 'Enter B-Connect ID (CC...) or Service ID (PMBBPS...)'
                : 'Enter tracking value'
            }
          />
          <button
            className="bg-blue-600 text-white rounded px-3 py-2 disabled:opacity-50"
            disabled={loading || !trackingValue.trim()}
            onClick={onSearch}
          >
            {loading ? 'Searching...' : 'Search'}
          </button>
        </div>
      )}

      {error && <div className="mt-3 text-sm text-red-700 bg-red-50 border border-red-200 rounded p-2">{error}</div>}

      {complaintsMode && rows.length > 0 && (
        <div className="mt-6">
          <p className="text-sm font-medium text-gray-700 mb-2">Matching transactions — select one for details</p>
          <div className="border rounded-lg divide-y max-h-52 overflow-auto">
            {rows.map((r, idx) => {
              const { ref, sub } = listLabel(r, idx);
              const sel = idx === selectedIdx;
              return (
                <button
                  key={`${ref}-${idx}`}
                  type="button"
                  className={`w-full text-left px-3 py-2 text-sm hover:bg-violet-50 ${sel ? 'bg-violet-100' : ''}`}
                  onClick={() => setSelectedIdx(idx)}
                >
                  <span className="font-medium">{ref}</span>
                  <span className="text-gray-600 text-xs block">{sub}</span>
                </button>
              );
            })}
          </div>
        </div>
      )}

      {!complaintsMode && (
        <div className="mt-4 space-y-4">
          {rows.map((r, idx) => (
            <TransactionDetailCard key={`${pickTxnReferenceId(r) || idx}`} row={r} />
          ))}
        </div>
      )}

      {complaintsMode && selectedRow && (
        <TransactionDetailCard row={selectedRow} onRaiseComplaint={goRaiseComplaint} />
      )}
    </div>
  );
};

export default BbpsTransactionQuery;
