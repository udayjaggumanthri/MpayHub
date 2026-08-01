import React, { useEffect, useState } from 'react';
import aepsAPI from '../services/aepsApi';
import { captureMantraFingerprint, getBrowserGeo } from '../services/mantraRd';

/**
 * Shared product form for CW / BE / MS / AP / CD and daily 2FA gate.
 */
const AepsProductPage = ({
  product,
  title,
  description,
  submit,
  requireAmount,
  require2faHint,
  aepsStatus: status,
  refreshStatus,
}) => {
  const [banks, setBanks] = useState([]);
  const [form, setForm] = useState({
    aadhaarNumber: '',
    mobileNumber: '',
    nationalBankIdentificationNumber: '',
    transactionAmount: '',
  });
  const [result, setResult] = useState(null);
  const [msg, setMsg] = useState('');
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    aepsAPI.listBanks(product === 'AP' ? 'aadhaar_pay' : 'aeps').then((res) => {
      if (res.success) setBanks(res.data?.results || []);
    });
  }, [product]);

  const run2fa = async () => {
    setBusy(true);
    setMsg('');
    const geo = await getBrowserGeo();
    const cap = await captureMantraFingerprint();
    if (!cap.success) {
      setMsg(cap.message);
      setBusy(false);
      return;
    }
    const res = await aepsAPI.complete2fa({
      latitude: geo.latitude,
      longitude: geo.longitude,
      captureResponse: cap.captureResponse,
    });
    setMsg(res.success ? '2FA completed for today.' : res.message);
    await refreshStatus();
    setBusy(false);
  };

  const onSubmit = async (e) => {
    e.preventDefault();
    setBusy(true);
    setMsg('');
    setResult(null);
    const geo = await getBrowserGeo();
    if (geo.status !== 'granted') {
      setMsg('Location is required for AEPS transactions.');
      setBusy(false);
      return;
    }
    const cap = await captureMantraFingerprint();
    if (!cap.success) {
      setMsg(cap.message);
      setBusy(false);
      return;
    }
    const body = {
      ...form,
      transactionAmount: requireAmount ? form.transactionAmount : 0,
      latitude: geo.latitude,
      longitude: geo.longitude,
      captureResponse: cap.captureResponse,
      indicatorforUID: 0,
    };
    const res = await submit(body);
    if (!res.success) {
      setMsg(res.message);
      setBusy(false);
      return;
    }
    setResult(res.data?.transaction || res.data);
    if (res.data?.needs_status_check && res.data?.transaction?.merchant_tran_id) {
      const st = await aepsAPI.statusCheck(res.data.transaction.merchant_tran_id);
      if (st.success) setResult(st.data?.transaction || st.data);
    }
    setMsg(res.message || 'Done');
    setBusy(false);
  };

  if (!status?.entitled) {
    return <p className="rounded-2xl border bg-white p-6 text-slate-600">AEPS access required.</p>;
  }

  return (
    <div className="space-y-6">
      <header>
        <h2 className="text-xl font-bold text-slate-900">{title}</h2>
        <p className="text-sm text-slate-500">{description}</p>
      </header>

      {require2faHint && !status?.merchant?.twofa_ok_today ? (
        <div className="rounded-2xl border border-amber-200 bg-amber-50 p-5">
          <p className="text-sm font-medium text-amber-950">Daily 2FA required for this product.</p>
          <button
            type="button"
            disabled={busy}
            onClick={run2fa}
            className="mt-3 rounded-lg bg-amber-700 px-4 py-2 text-sm font-semibold text-white hover:bg-amber-800 disabled:opacity-50"
          >
            Complete 2FA with Mantra
          </button>
        </div>
      ) : null}

      <form onSubmit={onSubmit} className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm space-y-4">
        <Field label="Customer Aadhaar" value={form.aadhaarNumber} onChange={(v) => setForm({ ...form, aadhaarNumber: v })} />
        <Field label="Mobile" value={form.mobileNumber} onChange={(v) => setForm({ ...form, mobileNumber: v })} />
        <label className="block text-xs font-semibold uppercase tracking-wide text-slate-500">
          Bank (IIN)
          <select
            className="mt-1 w-full rounded-lg border border-slate-200 px-3 py-2 text-sm"
            value={form.nationalBankIdentificationNumber}
            onChange={(e) => setForm({ ...form, nationalBankIdentificationNumber: e.target.value })}
            required
          >
            <option value="">Select bank</option>
            {banks.map((b) => (
              <option key={b.iin} value={b.iin}>
                {b.bank_name} ({b.iin})
              </option>
            ))}
          </select>
        </label>
        {requireAmount ? (
          <Field
            label="Amount (max 10000)"
            value={form.transactionAmount}
            onChange={(v) => setForm({ ...form, transactionAmount: v })}
            type="number"
          />
        ) : null}
        <button
          type="submit"
          disabled={busy}
          className="rounded-lg bg-blue-600 px-5 py-2.5 text-sm font-semibold text-white hover:bg-blue-700 disabled:opacity-50"
        >
          {busy ? 'Processing…' : 'Capture & submit'}
        </button>
      </form>

      {msg ? <p className="text-sm text-slate-700">{msg}</p> : null}
      {result ? (
        <pre className="overflow-auto rounded-2xl bg-slate-900 p-4 text-xs text-slate-100">
          {JSON.stringify(result, null, 2)}
        </pre>
      ) : null}
    </div>
  );
};

const Field = ({ label, value, onChange, type = 'text' }) => (
  <label className="block text-xs font-semibold uppercase tracking-wide text-slate-500">
    {label}
    <input
      type={type}
      className="mt-1 w-full rounded-lg border border-slate-200 px-3 py-2 text-sm"
      value={value}
      onChange={(e) => onChange(e.target.value)}
      required
    />
  </label>
);

export const AepsWithdraw = (props) => (
  <AepsProductPage
    {...props}
    product="CW"
    title="Cash withdrawal"
    description="Customer withdraws cash via Aadhaar + fingerprint."
    submit={aepsAPI.cashWithdrawal}
    requireAmount
    require2faHint
  />
);

export const AepsBalance = (props) => (
  <AepsProductPage
    {...props}
    product="BE"
    title="Balance enquiry"
    description="Check linked bank balance with Aadhaar biometric."
    submit={aepsAPI.balanceEnquiry}
  />
);

export const AepsMiniStatement = (props) => (
  <AepsProductPage
    {...props}
    product="MS"
    title="Mini statement"
    description="Fetch mini statement via Aadhaar biometric."
    submit={aepsAPI.miniStatement}
  />
);

export const AepsAadhaarPay = (props) => (
  <AepsProductPage
    {...props}
    product="AP"
    title="Aadhaar Pay"
    description="Collect payment from customer Aadhaar."
    submit={aepsAPI.aadhaarPay}
    requireAmount
    require2faHint
  />
);

export const AepsDeposit = (props) => (
  <AepsProductPage
    {...props}
    product="CD"
    title="Cash deposit"
    description="Deposit cash to customer bank account via AEPS."
    submit={aepsAPI.cashDeposit}
    requireAmount
    require2faHint
  />
);

export default AepsProductPage;
