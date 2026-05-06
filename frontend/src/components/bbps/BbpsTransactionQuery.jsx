import React, { useState } from 'react';
import { bbpsAPI } from '../../services/api';
import BharatConnectBranding from './BharatConnectBranding';

const BbpsTransactionQuery = () => {
  const [trackingType, setTrackingType] = useState('TRANS_REF_ID');
  const [trackingValue, setTrackingValue] = useState('');
  const [fromDate, setFromDate] = useState('');
  const [toDate, setToDate] = useState('');
  const [rows, setRows] = useState([]);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const onSearch = async () => {
    setError('');
    setLoading(true);
    const payload = { tracking_type: trackingType, tracking_value: trackingValue, from_date: fromDate, to_date: toDate };
    const res = await bbpsAPI.transactionQuery(payload);
    setLoading(false);
    if (!res.success) {
      setRows([]);
      setError(res.message || 'Query failed');
      return;
    }
    setRows(Array.isArray(res.data?.transactions) ? res.data.transactions : []);
  };

  return (
    <div className="max-w-6xl mx-auto bg-white rounded-xl border border-gray-200 shadow-sm p-6">
      <BharatConnectBranding stage="stage2" title="Transaction Query" />
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
          placeholder={trackingType === 'TRANS_REF_ID' ? 'Enter B-Connect ID (CC...) or Service ID (PMBBPS...)' : 'Enter tracking value'}
        />
        <button className="bg-blue-600 text-white rounded px-3 py-2 disabled:opacity-50" disabled={loading || !trackingValue} onClick={onSearch}>
          {loading ? 'Searching...' : 'Search'}
        </button>
      </div>
      {trackingType === 'MOBILE_NO' && (
        <div className="grid md:grid-cols-2 gap-3 mt-3">
          <input type="date" className="border rounded px-3 py-2" value={fromDate} onChange={(e) => setFromDate(e.target.value)} />
          <input type="date" className="border rounded px-3 py-2" value={toDate} onChange={(e) => setToDate(e.target.value)} />
        </div>
      )}
      {error && <div className="mt-3 text-sm text-red-700 bg-red-50 border border-red-200 rounded p-2">{error}</div>}
      <div className="mt-4 space-y-2">
        {rows.map((r, idx) => (
          <div key={`${r.txnReferenceId || idx}`} className="border rounded p-3 text-sm">
            <div><b>B-Connect Txn ID:</b> {r.txnReferenceId || '-'}</div>
            <div><b>Agent ID:</b> {r.agentId || '-'}</div>
            <div><b>Biller:</b> {r.billerName || r.billerId || '-'}</div>
            <div><b>Txn Date:</b> {r.txnDate || '-'}</div>
            <div><b>Status:</b> {r.txnStatus || '-'}</div>
          </div>
        ))}
      </div>
    </div>
  );
};

export default BbpsTransactionQuery;
