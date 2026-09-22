import React, { useEffect, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import Card from '../../../components/common/Card';
import Button from '../../../components/common/Button';
import Input from '../../../components/common/Input';
import { useAuth } from '../../../context/AuthContext';
import aepsAPI from '../services/aepsApi';
import { captureMantraFingerprint, getBrowserGeo } from '../services/mantraRd';
import AepsTransactionReceiptView from '../receipts/AepsTransactionReceiptView';
import {
  aepsAckAllowed,
  aepsBalanceLabel,
  aepsNeedsStatusCheck,
  normalizeAepsTxn,
} from '../receipts/aepsReceiptFields';
import { isAepsOperatorRole, sanitizeAepsUserMessage } from '../utils/aepsUserCopy';

const maskAadhaarDisplay = (v) => {
  const d = String(v || '').replace(/\D/g, '');
  if (d.length < 4) return d;
  return `${'X'.repeat(Math.max(0, d.length - 4))}${d.slice(-4)}`;
};

/** @deprecated Prefer AepsTransactionReceiptView — kept for import compatibility. */
export const ReceiptCard = ({ result, onStatusCheck, onAck, busy, onDoAnother }) => (
  <AepsTransactionReceiptView
    result={result}
    onStatusCheck={onStatusCheck}
    onAck={onAck}
    onDoAnother={onDoAnother}
    busy={busy}
  />
);

const GateCard = ({ title, text, to }) => (
  <Card className="text-center" shadow="sm">
    <h2 className="text-lg font-bold text-slate-900 dark:text-slate-100">{title}</h2>
    <p className="mt-2 text-sm text-slate-600 dark:text-slate-400">{text}</p>
    {to ? (
      <Link to={to} className="mt-4 inline-block text-sm font-semibold text-blue-700 dark:text-blue-300">
        Continue →
      </Link>
    ) : null}
  </Card>
);

const OutcomeModal = ({ open, onClose, children }) => {
  if (!open) return null;
  return (
    <div className="fixed inset-0 z-[60] flex items-end justify-center bg-black/50 p-3 sm:items-center sm:p-6">
      <div
        role="dialog"
        aria-modal="true"
        className="max-h-[92vh] w-full max-w-2xl overflow-y-auto rounded-2xl bg-white p-4 shadow-2xl dark:bg-slate-900 sm:p-5"
      >
        <div className="mb-3 flex items-center justify-between gap-2">
          <h3 className="text-lg font-bold text-slate-900 dark:text-slate-100">Transaction result</h3>
          <Button size="sm" variant="secondary" onClick={onClose}>
            Close
          </Button>
        </div>
        {children}
      </div>
    </div>
  );
};

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
}) => {
  const { user } = useAuth();
  const isOperator = isAepsOperatorRole(user);
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
  const [outcomeOpen, setOutcomeOpen] = useState(false);
  const [msg, setMsg] = useState('');
  const [busy, setBusy] = useState(false);

  const showUserMsg = (raw) => {
    const text = isOperator ? String(raw || '') : sanitizeAepsUserMessage(raw);
    setMsg(text);
  };

  const resolveBankName = (iin) => {
    const hit = banks.find((b) => String(b.iin) === String(iin));
    return hit?.bank_name || '';
  };

  const withBankName = (body) => {
    const iin = body.nationalBankIdentificationNumber || body.iin || '';
    return {
      ...body,
      bankName: resolveBankName(iin),
    };
  };

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

  const clearOutcome = () => {
    setResult(null);
    setMsg('');
    setOutcomeOpen(false);
  };

  const openOutcome = (data) => {
    setResult(data);
    setOutcomeOpen(Boolean(data));
  };

  const afterTxn = async (res, { otpMode = false } = {}) => {
    if (!res.success) {
      if (res.data?.transaction || res.data?.merchant_tran_id) {
        openOutcome(res.data);
      } else {
        setResult(null);
        setOutcomeOpen(false);
      }
      showUserMsg(res.message || 'Transaction failed');
      return;
    }
    let data = res.data;
    openOutcome(data);
    const txn = normalizeAepsTxn(data);
    const mid = txn?.merchant_tran_id;
    const alreadyFailed = txn?.status === 'failed';
    const shouldPoll =
      !alreadyFailed &&
      (Boolean(data?.needs_status_check) || ['pending', 'timeout', 'initiated'].includes(txn?.status));

    if (shouldPoll && mid) {
      const st = await aepsAPI.statusCheck(mid, { otp_mode: otpMode });
      if (st.success) {
        openOutcome(st.data);
        data = st.data;
      } else if (st.message) {
        showUserMsg(st.message);
      }
    }

    const finalTxn = normalizeAepsTxn(data);
    if (finalTxn?.status === 'success' && mid && aepsAckAllowed(finalTxn)) {
      const ack = await aepsAPI.acknowledge(mid, { otp_mode: otpMode });
      if (ack.success) {
        openOutcome(ack.data);
        data = ack.data;
      }
    }

    const shown = normalizeAepsTxn(data);
    if (shown?.status === 'success') {
      const bal = aepsBalanceLabel(shown);
      showUserMsg(bal ? `Transaction successful. Available balance: ${bal}` : 'Transaction successful.');
    } else if (['pending', 'timeout', 'initiated'].includes(shown?.status)) {
      showUserMsg(shown?.response_message || 'Still confirming with the bank…');
    } else {
      showUserMsg(shown?.response_message || res.message || 'Transaction failed');
    }
  };

  const onSubmitBio = async (e) => {
    e.preventDefault();
    setBusy(true);
    clearOutcome();
    const geo = await getBrowserGeo();
    if (geo.status !== 'granted') {
      showUserMsg('Location is required for AEPS transactions.');
      setBusy(false);
      return;
    }
    const cap = await captureMantraFingerprint();
    if (!cap.success) {
      showUserMsg(cap.message);
      setBusy(false);
      return;
    }
    const body = withBankName({
      ...form,
      aadhaarNumber: form.aadhaarNumber.replace(/\s/g, ''),
      transactionAmount: requireAmount ? form.transactionAmount : 0,
      latitude: geo.latitude,
      longitude: geo.longitude,
      captureResponse: cap.captureResponse,
      indicatorforUID: 0,
    });
    const res = await submit(body);
    await afterTxn(res, { otpMode: false });
    setBusy(false);
  };

  const cdOtpGenerate = async () => {
    setBusy(true);
    clearOutcome();
    setPendingTranId('');
    setOtpStep('idle');
    const geo = await getBrowserGeo();
    if (geo.status !== 'granted') {
      showUserMsg('Location is required.');
      setBusy(false);
      return;
    }
    const res = await aepsAPI.cashDepositOtpGenerate(
      withBankName({
        ...form,
        aadhaarNumber: form.aadhaarNumber.replace(/\s/g, ''),
        transactionAmount: form.transactionAmount,
        latitude: geo.latitude,
        longitude: geo.longitude,
        indicatorforUID: 0,
      })
    );
    if (res.success) {
      const mid = res.data?.transaction?.merchant_tran_id || res.data?.merchant_tran_id;
      setPendingTranId(mid || '');
      setOtpStep('sent');
      showUserMsg('OTP sent to customer mobile.');
      // Keep OTP flow on-page; full receipt modal after final submit / bio
      setResult(res.data);
    } else {
      showUserMsg(res.message || 'OTP generate failed');
      if (res.data?.transaction) openOutcome(res.data);
      else {
        setResult(null);
        setOutcomeOpen(false);
      }
      setOtpStep('idle');
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
      showUserMsg('OTP validated. Submit deposit next.');
      setResult(res.data);
    } else {
      showUserMsg(res.message);
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
      otp_mode: Boolean(txn.cd_otp_mode) || cdMode === 'otp' || txn.product === 'CD_OTP',
    });
    if (st.success) {
      openOutcome(st.data);
      const shown = normalizeAepsTxn(st.data);
      showUserMsg(
        shown?.status === 'success'
          ? 'Transaction successful.'
          : shown?.response_message || 'Status updated.'
      );
    } else showUserMsg(st.message);
    setBusy(false);
  };

  const onAck = async (txn) => {
    if (!aepsAckAllowed(txn)) {
      showUserMsg('Acknowledge is not required for this product.');
      return;
    }
    setBusy(true);
    const ack = await aepsAPI.acknowledge(txn.merchant_tran_id, {
      otp_mode: Boolean(txn.cd_otp_mode) || cdMode === 'otp' || txn.product === 'CD_OTP',
    });
    if (ack.success) openOutcome(ack.data);
    else showUserMsg(ack.message);
    setBusy(false);
  };

  const onDoAnother = () => {
    clearOutcome();
    setOtpStep('idle');
    setOtpValue('');
    setPendingTranId('');
  };

  const friendlyDescription = isOperator
    ? description
    : String(description || '')
        .replace(/\(per Fingpay Cash Deposit\)/gi, '')
        .replace(/\bFingpay\b/gi, 'bank network')
        .replace(/\bTapits\b/gi, 'support')
        .trim();

  if (gate.block) {
    return <GateCard title={gate.title} text={gate.text} to={gate.to} />;
  }

  return (
    <div className="space-y-5">
      <header>
        <h2 className="text-xl font-bold text-slate-900 dark:text-slate-100">{title}</h2>
        <p className="text-sm text-slate-500 dark:text-slate-400">{friendlyDescription}</p>
      </header>

      {allowCdOtp ? (
        <div className="flex gap-2">
          <button
            type="button"
            onClick={() => {
              setCdMode('bio');
              clearOutcome();
              setOtpStep('idle');
            }}
            className={`rounded-lg px-3 py-1.5 text-xs font-semibold ring-1 ${
              cdMode === 'bio'
                ? 'bg-blue-600 text-white ring-blue-600'
                : 'bg-white dark:bg-slate-900 text-slate-700 dark:text-slate-300 ring-slate-200 dark:ring-slate-700'
            }`}
          >
            Biometric
          </button>
          <button
            type="button"
            onClick={() => {
              setCdMode('otp');
              clearOutcome();
              setOtpStep('idle');
            }}
            className={`rounded-lg px-3 py-1.5 text-xs font-semibold ring-1 ${
              cdMode === 'otp'
                ? 'bg-blue-600 text-white ring-blue-600'
                : 'bg-white dark:bg-slate-900 text-slate-700 dark:text-slate-300 ring-slate-200 dark:ring-slate-700'
            }`}
          >
            OTP deposit
          </button>
        </div>
      ) : null}

      <Card shadow="sm">
        <form
          onSubmit={cdMode === 'otp' && allowCdOtp ? (e) => e.preventDefault() : onSubmitBio}
          className="space-y-4"
        >
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
            <span className="mb-1.5 flex items-center justify-between text-sm font-medium text-gray-700 dark:text-slate-300">
              <span>Bank (IIN)</span>
              <button
                type="button"
                className="text-xs font-semibold text-blue-700 dark:text-blue-300 hover:underline"
                onClick={refreshBanks}
              >
                Refresh banks
              </button>
            </span>
            <input
              className="mb-2 w-full rounded-lg border border-gray-300 dark:border-slate-600 px-3 py-2 text-sm"
              placeholder="Search bank name or IIN"
              value={bankQuery}
              onChange={(e) => setBankQuery(e.target.value)}
            />
            <select
              className="w-full rounded-lg border border-gray-300 dark:border-slate-600 px-3 py-2.5 text-sm"
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
            <div className="space-y-3 rounded-lg border border-slate-100 dark:border-slate-800 bg-slate-50 dark:bg-slate-800/50 p-3">
              {otpStep === 'idle' || otpStep === 'sent' ? (
                <Button
                  type="button"
                  loading={busy}
                  onClick={cdOtpGenerate}
                  disabled={!form.nationalBankIdentificationNumber}
                >
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

      <OutcomeModal
        open={outcomeOpen && Boolean(result)}
        onClose={() => setOutcomeOpen(false)}
      >
        <AepsTransactionReceiptView
          result={result}
          onStatusCheck={onStatusCheck}
          onAck={onAck}
          onDoAnother={onDoAnother}
          busy={busy}
        />
      </OutcomeModal>

      {/* Errors with no receipt payload still surface in a popup so agents never miss them below the fold */}
      <OutcomeModal
        open={!result && Boolean(msg) && !busy}
        onClose={() => setMsg('')}
      >
        <p className="rounded-lg border border-slate-200 bg-slate-50 px-3 py-3 text-sm text-slate-800 dark:border-slate-700 dark:bg-slate-800/50 dark:text-slate-200">
          {msg}
        </p>
        <div className="mt-4 flex justify-end">
          <Button size="sm" onClick={() => setMsg('')}>
            OK
          </Button>
        </div>
      </OutcomeModal>
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
    description="Deposit cash via biometric or customer OTP."
    submit={aepsAPI.cashDeposit}
    requireAmount
    require2fa
    allowCdOtp
  />
);
