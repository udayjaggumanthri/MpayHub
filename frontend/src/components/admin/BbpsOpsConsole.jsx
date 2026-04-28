import React, { useState } from 'react';
import { bbpsAPI } from '../../services/api';

const BbpsOpsConsole = () => {
  const [planIds, setPlanIds] = useState('');
  const [depositForm, setDepositForm] = useState({ from_date: '', to_date: '', trans_type: '' });
  const [output, setOutput] = useState(null);

  const pullPlans = async () => {
    const ids = planIds.split(',').map((x) => x.trim()).filter(Boolean);
    setOutput(await bbpsAPI.pullPlans(ids));
  };

  const enquiry = async () => {
    setOutput(await bbpsAPI.depositEnquiry(depositForm));
  };

  return (
    <div className="max-w-4xl mx-auto space-y-6">
      <div className="bg-white rounded-xl border border-gray-200 p-6">
        <h1 className="text-xl font-semibold mb-3">BBPS Ops Console</h1>
        <input className="w-full border rounded px-3 py-2" placeholder="Plan pull biller IDs (comma-separated)" value={planIds} onChange={(e) => setPlanIds(e.target.value)} />
        <button type="button" className="mt-3 px-4 py-2 bg-indigo-600 text-white rounded" onClick={pullPlans}>Run Plan Pull</button>
      </div>

      <div className="bg-white rounded-xl border border-gray-200 p-6">
        <h2 className="text-lg font-semibold mb-3">Deposit Enquiry</h2>
        <div className="grid md:grid-cols-3 gap-3">
          <input className="border rounded px-3 py-2" placeholder="From date (YYYY-MM-DD)" value={depositForm.from_date} onChange={(e) => setDepositForm((p) => ({ ...p, from_date: e.target.value }))} />
          <input className="border rounded px-3 py-2" placeholder="To date (YYYY-MM-DD)" value={depositForm.to_date} onChange={(e) => setDepositForm((p) => ({ ...p, to_date: e.target.value }))} />
          <input className="border rounded px-3 py-2" placeholder="Trans type (optional)" value={depositForm.trans_type} onChange={(e) => setDepositForm((p) => ({ ...p, trans_type: e.target.value }))} />
        </div>
        <button type="button" className="mt-3 px-4 py-2 bg-blue-600 text-white rounded" onClick={enquiry}>Run Deposit Enquiry</button>
      </div>

      {output && <pre className="bg-gray-50 border rounded p-3 text-xs overflow-auto">{JSON.stringify(output, null, 2)}</pre>}
    </div>
  );
};

export default BbpsOpsConsole;
