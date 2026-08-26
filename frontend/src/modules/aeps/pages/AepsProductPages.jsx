import React, { useEffect, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import Card from '../../../components/common/Card';
import Button from '../../../components/common/Button';
import Input from '../../../components/common/Input';
import aepsAPI from '../services/aepsApi';
import { captureMantraFingerprint, getBrowserGeo } from '../services/mantraRd';

const maskAadhaarDisplay = (v) => {
  const d = String(v || '').replace(/\D/g, '');
  if (d.length < 4) return d;
  return `${'X'.repeat(Math.max(0, d.length - 4))}${d.slice(-4)}`;
};

const GateCard = ({ title, text, to }) => (
  <Card className="text-center" shadow="sm">
    <h2 className="text-lg font-bold text-slate-900">{title}</h2>
    <p className="mt-2 text-sm text-slate-600">{text}</p>
    {to ? (
      <Link to={to} className="mt-4 inline-block text-sm font-semibold text-blue-700">
        Continue →
      </Link>
    ) : null}
  </Card>
);

const ReceiptCard = ({ result, onStatusCheck, onAck, busy }) => {
  if (!result) return null;
  const txn = result.transaction || result;
  const statements = txn.mini_statement || txn.provider_meta?.data?.miniStatement || [];
  const rows = Array.isArray(statements) ? statements : [];

  return (
    <Card title="Receipt" shadow="sm" className="space-y-3">
      <div className="grid gap-3 sm:grid-cols-2">
        <Stat label="Status" value={txn.status || '—'} />
        <Stat label="Amount" value={txn.amount != null ? `₹${txn.amount}` : '—'} />
        <Stat label="RRN" value={txn.bank_rrn || '—'} mono />
        <Stat label="Txn id" value={txn.merchant_tran_id || '—'} mono />
        <Stat label="Response" value={txn.response_message || txn.response_code || '—'} />
        <Stat label="Product" value={txn.product || '—'} />
      </div>
      {rows.length ? (
        <div className="overflow-x-auto rounded-lg border border-slate-100">
          <table className="min-w-full text-left text-sm">
            <thead className="bg-slate-50 text-xs uppercase text-slate-500">
              <tr>
                <th className="px-3 py-2">Date</th>
                <th className="px-3 py-2">Narration</th>
                <th className="px-3 py-2">Amount</th>
                <th className="px-3 py-2">Type</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((r, i) => (
                <tr key={i} className="border-t border-slate-100">
                  <td className="px-3 py-2">{r.date || r.txnDate || '—'}</td>
                  <td className="px-3 py-2">{r.narration || r.remarks || '—'}</td>
                  <td className="px-3 py-2">{r.amount || r.txnAmount || '—'}</td>
                  <td className="px-3 py-2">{r.txnType || r.type || '—'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : null}
      {txn.merchant_tran_id ? (
        <div className="flex flex-wrap gap-2">
          <Button size="sm" variant="secondary" loading={busy} onClick={() => onStatusCheck(txn)}>
            Status check
          </Button>
          <Button size="sm" variant="secondary" loading={busy} onClick={() => onAck(txn)}>
            Acknowledge
          </Button>
        </div>
      ) : null}
    </Card>
  );
};

const Stat = ({ label, value, mono }) => (
  <div className="rounded-lg bg-slate-50 px-3 py-2 ring-1 ring-slate-100">
    <p className="text-[10px] font-semibold uppercase tracking-wide text-slate-500">{label}</p>
    <p className={`mt-0.5 break-all text-sm font-semibold text-slate-900 ${mono ? 'font-mono text-xs' : ''}`}>
      {value}
    </p>
  </div>
);

/**
 * Shared product form for CW / BE / MS / AP / CD (+ CD OTP mode).
 */
const AepsProductPage = ({
  product,
  title,
  description,
  submit,
  requireAmount,
  require2fa,
  allowCdOtp,
  aepsStatus: status,
  refreshStatus,
}) => {
  const [banks, setBanks] = useState([]);
  const [bankQuery, setBankQuery] = useState('');
  const [cdMode, setCdMode] = useState('bio'); // bio | otp
  const [otpStep, setOtpStep] = useState('idle'); // idle | sent | validated
  const [otpValue, setOtpValue] = useState('');
  const [pendingTranId, setPendingTranId] = useState('');
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

  const refreshBanks = async () => {
    const type = product === 'AP' ? 'aadhaar_pay' : 'aeps';
    const res = await aepsAPI.listBanks(type, true);
    if (res.success) setBanks(res.data?.results || []);
    else setMsg(res.message || 'Could not refresh banks');
  };

  const filteredBanks = useMemo(() => {
    const q = bankQuery.trim().toLowerCase();
    if (!q) return banks.slice(0, 100);
    return banks
      .filter(
        (b) =>
          String(b.bank_name || '').toLowerCase().includes(q) ||
          String(b.iin || '').includes(q)
      )
      .slice(0, 100);
  }, [banks, bankQuery]);

  const gate = useMemo(() => {
    if (!status?.entitled) return { block: true, title, text: 'AEPS access required.', to: '/aeps' };
    if (status?.merchant?.stage !== 'active')
      return { block: true, title, text: 'Complete onboarding and eKYC before trading.', to: '/aeps/setup' };
    if (!status?.merchant?.device_ready)
      return { block: true, title, text: 'Register your Mantra device before trading.', to: '/aeps/device' };
    if (require2fa && !status?.merchant?.twofa_ok_today)
      return {
        block: true,
        title,
        text: 'Complete today’s 2FA before this product.',
        to: '/aeps/2fa',
      };
    return { block: false };
  }, [status, require2fa, title]);

    const afterTxn = async (res, { otpMode = false } = {}) => {
    if (!res.success) {
      setMsg(res.message);
      return;
    }
    let data = res.data;
    setResult(data);
    const txn = data?.transaction || data;
    const mid = txn?.merchant_tran_id;
    const shouldPoll =
      Boolean(data?.needs_status_check) || ['pending', 'timeout', 'initiated'].includes(txn?.status);
    if (shouldPoll && mid) {
      const st = await aepsAPI.statusCheck(mid, { otp_mode: otpMode });
      if (st.success) {
        setResult(st.data);
        data = st.data;
      } else if (st.message) {
        setMsg(st.message);
      }
    }
    const finalTxn = data?.transaction || data;
    if (finalTxn?.status === 'success' && mid) {
      const ack = await aepsAPI.acknowledge(mid, { otp_mode: otpMode });
      if (ack.success) setResult(ack.data);
      setMsg('Transaction successful.');
    } else {
      setMsg(finalTxn?.response_message || res.message || 'Transaction failed');
    }
  };

  const onSubmitBio = async (e) => {
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
      aadhaarNumber: form.aadhaarNumber.replace(/\s/g, ''),
      transactionAmount: requireAmount ? form.transactionAmount : 0,
      latitude: geo.latitude,
      longitude: geo.longitude,
      captureResponse: cap.captureResponse,
      indicatorforUID: 0,
    };
    const res = await submit(body);
    await afterTxn(res, { otpMode: false });
    setBusy(false);
  };

  const cdOtpGenerate = async () => {
    setBusy(true);
    setMsg('');
    const geo = await getBrowserGeo();
    if (geo.status !== 'granted') {
      setMsg('Location is required.');
      setBusy(false);
      return;
    }
    const res = await aepsAPI.cashDepositOtpGenerate({
      ...form,
      aadhaarNumber: form.aadhaarNumber.replace(/\s/g, ''),
      transactionAmount: form.transactionAmount,
      latitude: geo.latitude,
      longitude: geo.longitude,
      indicatorforUID: 0,
    });
    if (res.success) {
      const mid = res.data?.transaction?.merchant_tran_id || res.data?.merchant_tran_id;
      setPendingTranId(mid || '');
      setOtpStep('sent');
      setMsg('OTP sent to customer mobile.');
      setResult(res.data);
    } else {
      setMsg(res.message);
    }
    setBusy(false);
  };

  const cdOtpValidate = async () => {
    setBusy(true);
    const res = await aepsAPI.cashDepositOtpValidate({
      merchant_tran_id: pendingTranId,
      otp: otpValue,
    });
    if (res.success) {
      setOtpStep('validated');
      setMsg('OTP validated. Submit deposit next.');
      setResult(res.data);
    } else {
      setMsg(res.message);
    }
    setBusy(false);
  };

  const cdOtpSubmit = async () => {
    setBusy(true);
    const geo = await getBrowserGeo();
    const res = await aepsAPI.cashDepositOtpSubmit({
      merchant_tran_id: pendingTranId,
      latitude: geo.latitude,
      longitude: geo.longitude,
    });
    await afterTxn(res, { otpMode: true });
    if (res.success) {
      setOtpStep('idle');
      setOtpValue('');
    }
    setBusy(false);
  };

  const onStatusCheck = async (txn) => {
    setBusy(true);
    const st = await aepsAPI.statusCheck(txn.merchant_tran_id, {
      otp_mode: cdMode === 'otp' || txn.product === 'CD_OTP',
    });
    if (st.success) setResult(st.data);
    else setMsg(st.message);
    setBusy(false);
  };

  const onAck = async (txn) => {
    setBusy(true);
    const ack = await aepsAPI.acknowledge(txn.merchant_tran_id, {
      otp_mode: cdMode === 'otp' || txn.product === 'CD_OTP',
    });
    if (ack.success) setResult(ack.data);
    else setMsg(ack.message);
    setBusy(false);
  };

  if (gate.block) {
    return <GateCard title={gate.title} text={gate.text} to={gate.to} />;
  }

  return (
    <div className="space-y-5">
      <header>
        <h2 className="text-xl font-bold text-slate-900">{title}</h2>
        <p className="text-sm text-slate-500">{description}</p>
      </header>

      {allowCdOtp ? (
        <div className="flex gap-2">
          <button
            type="button"
            onClick={() => setCdMode('bio')}
            className={`rounded-lg px-3 py-1.5 text-xs font-semibold ring-1 ${
              cdMode === 'bio' ? 'bg-blue-600 text-white ring-blue-600' : 'bg-white text-slate-700 ring-slate-200'
            }`}
          >
            Biometric
          </button>
          <button
            type="button"
            onClick={() => setCdMode('otp')}
            className={`rounded-lg px-3 py-1.5 text-xs font-semibold ring-1 ${
              cdMode === 'otp' ? 'bg-blue-600 text-white ring-blue-600' : 'bg-white text-slate-700 ring-slate-200'
            }`}
          >
            OTP deposit
          </button>
        </div>
      ) : null}

      <Card shadow="sm">
        <form onSubmit={cdMode === 'otp' && allowCdOtp ? (e) => e.preventDefault() : onSubmitBio} className="space-y-4">
          <Input
            label="Customer Aadhaar"
            value={form.aadhaarNumber}
            onChange={(e) =>
              setForm({ ...form, aadhaarNumber: e.target.value.replace(/\D/g, '').slice(0, 12) })
            }
            required
            inputMode="numeric"
            helperText={
              form.aadhaarNumber
                ? `Full 12 digits are sent to the bank. History stores ${maskAadhaarDisplay(form.aadhaarNumber)}.`
                : undefined
            }
          />
          <Input
            label="Mobile"
            value={form.mobileNumber}
            onChange={(e) =>
              setForm({ ...form, mobileNumber: e.target.value.replace(/\D/g, '').slice(0, 10) })
            }
            required
            inputMode="numeric"
          />
          <label className="block">
            <span className="mb-1.5 flex items-center justify-between text-sm font-medium text-gray-700">
              <span>Bank (IIN)</span>
              <button
                type="button"
                className="text-xs font-semibold text-blue-700 hover:underline"
                onClick={refreshBanks}
              >
                Refresh banks
              </button>
            </span>
            <input
              className="mb-2 w-full rounded-lg border border-gray-300 px-3 py-2 text-sm"
              placeholder="Search bank name or IIN"
              value={bankQuery}
              onChange={(e) => setBankQuery(e.target.value)}
            />
            <select
              className="w-full rounded-lg border border-gray-300 px-3 py-2.5 text-sm"
              value={form.nationalBankIdentificationNumber}
              onChange={(e) => setForm({ ...form, nationalBankIdentificationNumber: e.target.value })}
              required
              disabled={!banks.length}
            >
              <option value="">{banks.length ? 'Select bank' : 'No banks loaded — tap Refresh'}</option>
              {filteredBanks.map((b) => (
                <option key={b.iin} value={b.iin}>
                  {b.bank_name} ({b.iin})
                </option>
              ))}
            </select>
          </label>
          {requireAmount ? (
            <Input
              label="Amount (max ₹10,000)"
              type="number"
              value={form.transactionAmount}
              onChange={(e) => setForm({ ...form, transactionAmount: e.target.value })}
              required
              min={1}
              max={10000}
            />
          ) : null}

          {allowCdOtp && cdMode === 'otp' ? (
            <div className="space-y-3 rounded-lg border border-slate-100 bg-slate-50 p-3">
              {otpStep === 'idle' || otpStep === 'sent' ? (
                <Button type="button" loading={busy} onClick={cdOtpGenerate} disabled={!form.nationalBankIdentificationNumber}>
                  Generate OTP
                </Button>
              ) : null}
              {otpStep === 'sent' || otpStep === 'validated' ? (
                <div className="flex flex-wrap items-end gap-2">
                  <Input
                    label="Customer OTP"
                    value={otpValue}
                    onChange={(e) => setOtpValue(e.target.value.replace(/\D/g, '').slice(0, 8))}
                    className="max-w-[160px]"
                  />
                  {otpStep === 'sent' ? (
                    <Button type="button" loading={busy} onClick={cdOtpValidate} disabled={!otpValue}>
                      Validate OTP
                    </Button>
                  ) : null}
                  {otpStep === 'validated' ? (
                    <Button type="button" loading={busy} onClick={cdOtpSubmit}>
                      Submit deposit
                    </Button>
                  ) : null}
                </div>
              ) : null}
            </div>
          ) : (
            <Button type="submit" loading={busy}>
              Capture & submit
            </Button>
          )}
        </form>
      </Card>

      {msg ? <p className="text-sm text-slate-700">{msg}</p> : null}
      <ReceiptCard result={result} onStatusCheck={onStatusCheck} onAck={onAck} busy={busy} />
    </div>
  );
};

export const AepsWithdraw = (props) => (
  <AepsProductPage
    {...props}
    product="CW"
    title="Cash withdrawal"
    description="Customer withdraws cash via Aadhaar + fingerprint."
    submit={aepsAPI.cashWithdrawal}
    requireAmount
    require2fa
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
    require2fa
  />
);

export const AepsDeposit = (props) => (
  <AepsProductPage
    {...props}
    product="CD"
    title="Cash deposit"
    description="Deposit cash via biometric or customer OTP (per Fingpay Cash Deposit)."
    submit={aepsAPI.cashDeposit}
    requireAmount
    require2fa
    allowCdOtp
  />
);

export default AepsProductPage;
