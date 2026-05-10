import React, { useState, useEffect } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { bbpsAPI } from '../../services/api';
import BharatConnectBranding from './BharatConnectBranding';

const fmtVal = (v) => {
  const s = v != null && String(v).trim() !== '' ? String(v) : '';
  return s || '—';
};

/**
 * Map BillAvenue txn row (shape varies) into display fields for the Query Transaction card.
 */
const normalizeTxnRow = (r) => ({
  billerName: r.billerName || r.biller_name || r.billerId || r.biller_id,
  billNumber: r.billNumber || r.bill_number || r.billNo || r.consumerNumber || r.customerRefNumber,
  dueDate: r.dueDate || r.due_date,
  registeredMobile: r.registeredMobile || r.regMobileNo || r.mobileNo || r.mobileNumber,
  ccf: r.customerConvenienceFee || r.ccf || r.convFee,
  billAmount: r.billAmount || r.bill_amount || r.amount,
  txnReferenceId: r.txnReferenceId || r.txnRefId || r.transactionRefId,
  mobileNumber: r.mobileNumber || r.mobileNo || r.customerMobile,
  billDate: r.billDate || r.bill_date,
  paymentMode: r.paymentMode || r.payMode || r.payment_method,
  txnDate: r.txnDate || r.txn_date || r.transactionDate,
  txnStatus: r.txnStatus || r.txn_status || r.status,
  totalAmount: r.totalAmount || r.total_amount || r.amountPaid || r.billAmount,
});

const TransactionDetailCard = ({ row, onRaiseComplaint }) => {
  const n = normalizeTxnRow(row);
  const paid = String(n.txnStatus || '').toUpperCase().includes('PAID');
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
      <div className="p-5 grid md:grid-cols-2 gap-x-8 gap-y-4 text-sm">
        <Field label="Name of Biller" value={n.billerName} />
        <Field label="Mobile Number" value={n.mobileNumber} />
        <Field label="Bill Number" value={n.billNumber} />
        <Field label="Bill Date" value={n.billDate} />
        <Field label="Due Date" value={n.dueDate} />
        <Field label="B-Connect TXN ID" value={n.txnReferenceId} />
        <Field label="Registered Mobile Number" value={n.registeredMobile} />
        <Field label="Payment Mode" value={n.paymentMode} />
        <Field label="Customer Convenience Fee (CCF)" value={n.ccf} />
        <div>
          <div className="text-xs text-gray-500">Payment Status</div>
          <span
            className={`inline-flex mt-1 rounded-full px-3 py-0.5 text-xs font-semibold border ${
              paid ? 'bg-emerald-100 text-emerald-900 border-emerald-300' : 'bg-gray-100 text-gray-800 border-gray-300'
            }`}
          >
            {fmtVal(n.txnStatus)}
          </span>
        </div>
        <Field label="Bill Amount" value={n.billAmount} />
        <Field label="Total Amount" value={n.totalAmount} />
        <Field label="Transaction Date & Time" value={n.txnDate} />
      </div>
      {onRaiseComplaint && n.txnReferenceId && (
        <div className="px-5 pb-5 flex justify-end">
          <button
            type="button"
            className="bg-blue-600 hover:bg-blue-700 text-white rounded-lg px-5 py-2 text-sm font-medium"
            onClick={() => onRaiseComplaint(String(n.txnReferenceId).trim())}
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
  const [fromDate, setFromDate] = useState('');
  const [toDate, setToDate] = useState('');
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

  const selectedRow = selectedIdx >= 0 && selectedIdx < rows.length ? rows[selectedIdx] : null;

  const goRaiseComplaint = (txnRef) => {
    navigate('/bill-payments/complaints/register', { state: { txnRefId: txnRef } });
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

          <div className="grid md:grid-cols-12 gap-4 items-end">
            <div className="md:col-span-4">
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
            <div className="md:col-span-3">
              <label className="block text-xs text-gray-500 mb-1">Select From Date</label>
              <input
                type="date"
                className="border rounded-lg px-3 py-2 w-full"
                value={fromDate}
                onChange={(e) => setFromDate(e.target.value)}
              />
            </div>
            <div className="md:col-span-3">
              <label className="block text-xs text-gray-500 mb-1">Select To Date</label>
              <input
                type="date"
                className="border rounded-lg px-3 py-2 w-full"
                value={toDate}
                onChange={(e) => setToDate(e.target.value)}
              />
            </div>
            <div className="md:col-span-2 flex justify-end">
              <button
                className="bg-blue-600 text-white rounded-lg px-4 py-2 w-full md:w-auto disabled:opacity-50"
                disabled={loading || !trackingValue}
                onClick={onSearch}
              >
                {loading ? 'Fetching…' : 'Fetch Transaction'}
              </button>
            </div>
          </div>
        </div>
      ) : (
        <>
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
        </>
      )}

      {error && <div className="mt-3 text-sm text-red-700 bg-red-50 border border-red-200 rounded p-2">{error}</div>}

      {complaintsMode && rows.length > 0 && (
        <div className="mt-6">
          <p className="text-sm font-medium text-gray-700 mb-2">Matching transactions — select one for details</p>
          <div className="border rounded-lg divide-y max-h-52 overflow-auto">
            {rows.map((r, idx) => {
              const ref = String(r.txnReferenceId || r.txnRefId || '').trim() || `#${idx}`;
              const sel = idx === selectedIdx;
              return (
                <button
                  key={`${ref}-${idx}`}
                  type="button"
                  className={`w-full text-left px-3 py-2 text-sm hover:bg-violet-50 ${sel ? 'bg-violet-100' : ''}`}
                  onClick={() => setSelectedIdx(idx)}
                >
                  <span className="font-medium">{ref}</span>
                  <span className="text-gray-600 text-xs block">
                    {(r.billerName || r.billerId || '-') + ' · ' + (r.txnDate || '-')}
                  </span>
                </button>
              );
            })}
          </div>
        </div>
      )}

      {!complaintsMode && (
        <div className="mt-4 space-y-2">
          {rows.map((r, idx) => (
            <div key={`${r.txnReferenceId || idx}`} className="border rounded p-3 text-sm">
              <div>
                <b>B-Connect Txn ID:</b> {r.txnReferenceId || '-'}
              </div>
              <div>
                <b>Agent ID:</b> {r.agentId || '-'}
              </div>
              <div>
                <b>Biller:</b> {r.billerName || r.billerId || '-'}
              </div>
              <div>
                <b>Txn Date:</b> {r.txnDate || '-'}
              </div>
              <div>
                <b>Status:</b> {r.txnStatus || '-'}
              </div>
            </div>
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
