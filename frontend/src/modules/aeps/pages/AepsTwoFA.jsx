import React, { useEffect, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import Card from '../../../components/common/Card';
import Button from '../../../components/common/Button';
import Input from '../../../components/common/Input';
import aepsAPI from '../services/aepsApi';
import { captureMantraFingerprint, getBrowserGeo } from '../services/mantraRd';

/**
 * Dedicated daily 2FA screen — bank + Aadhaar + Mantra → tfauth path.
 */
const AepsTwoFA = ({ aepsStatus: status, refreshStatus }) => {
  const [banks, setBanks] = useState([]);
  const [bankQuery, setBankQuery] = useState('');
  const [form, setForm] = useState({
    aadhaarNumber: '',
    mobileNumber: '',
    nationalBankIdentificationNumber: '',
  });
  const [msg, setMsg] = useState({ type: '', text: '' });
  const [busy, setBusy] = useState(false);
  const [forceRedo, setForceRedo] = useState(false);

  useEffect(() => {
    aepsAPI.listBanks('aeps').then((res) => {
      if (res.success) setBanks(res.data?.results || []);
    });
  }, []);

  const filteredBanks = useMemo(() => {
    const q = bankQuery.trim().toLowerCase();
    if (!q) return banks.slice(0, 80);
    return banks
      .filter(
        (b) =>
          String(b.bank_name || '').toLowerCase().includes(q) ||
          String(b.iin || '').includes(q)
      )
      .slice(0, 80);
  }, [banks, bankQuery]);

  const gate = useMemo(() => {
    if (!status?.entitled) return { block: true, to: '/aeps', text: 'AEPS access required.' };
    if (status?.merchant?.stage !== 'active')
      return { block: true, to: '/aeps/setup', text: 'Complete onboarding and eKYC first.' };
    if (!status?.merchant?.device_ready)
      return { block: true, to: '/aeps/device', text: 'Register your Mantra device first.' };
    return { block: false };
  }, [status]);

  const submit = async (e) => {
    e.preventDefault();
    setBusy(true);
    setMsg({ type: '', text: '' });
    const geo = await getBrowserGeo();
    if (geo.status !== 'granted') {
      setMsg({ type: 'error', text: 'Location permission is required for 2FA.' });
      setBusy(false);
      return;
    }
    const cap = await captureMantraFingerprint();
    if (!cap.success) {
      setMsg({ type: 'error', text: cap.message || 'Fingerprint capture failed' });
      setBusy(false);
      return;
    }
    const res = await aepsAPI.complete2fa({
      latitude: geo.latitude,
      longitude: geo.longitude,
      captureResponse: cap.captureResponse,
      aadhaarNumber: form.aadhaarNumber.replace(/\s/g, ''),
      mobileNumber: form.mobileNumber,
      nationalBankIdentificationNumber: form.nationalBankIdentificationNumber,
      indicatorforUID: 0,
    });
    if (res.success) {
      setMsg({ type: 'success', text: 'Daily 2FA completed. Cash products are unlocked for today.' });
      await refreshStatus?.();
    } else {
      setMsg({ type: 'error', text: res.message || '2FA failed' });
    }
    setBusy(false);
  };

  if (gate.block) {
    return (
      <Card className="text-center" shadow="sm">
        <h2 className="text-lg font-bold text-slate-900">Daily 2FA</h2>
        <p className="mt-2 text-sm text-slate-600">{gate.text}</p>
        <Link to={gate.to} className="mt-4 inline-block text-sm font-semibold text-blue-700">
          Continue setup →
        </Link>
      </Card>
    );
  }

  if (status?.merchant?.twofa_ok_today && !forceRedo) {
    return (
      <Card shadow="sm">
        <p className="text-xs font-semibold uppercase tracking-wide text-emerald-700">2FA</p>
        <h2 className="mt-1 text-xl font-bold text-slate-900">Already verified today</h2>
        <p className="mt-2 text-sm text-slate-600">
          You can run cash withdrawal, Aadhaar Pay, and cash deposit. Re-run only if Fingpay asks.
        </p>
        <div className="mt-4 flex flex-wrap gap-2">
          <Link
            to="/aeps/withdraw"
            className="inline-flex rounded-lg bg-blue-600 px-4 py-2.5 text-sm font-semibold text-white hover:bg-blue-700"
          >
            Go to withdraw
          </Link>
          <Button variant="secondary" onClick={() => setForceRedo(true)} type="button">
            Re-authenticate
          </Button>
        </div>
      </Card>
    );
  }

  return (
    <div className="mx-auto max-w-xl space-y-4">
      <header>
        <h2 className="text-xl font-bold text-slate-900">Daily 2FA</h2>
        <p className="text-sm text-slate-500">
          Required once per day before cash withdrawal, Aadhaar Pay, and cash deposit.
        </p>
      </header>

      {msg.text ? (
        <div
          className={`rounded-xl border px-4 py-3 text-sm ${
            msg.type === 'error'
              ? 'border-rose-200 bg-rose-50 text-rose-800'
              : 'border-emerald-200 bg-emerald-50 text-emerald-800'
          }`}
        >
          {msg.text}
        </div>
      ) : null}

      <Card shadow="sm">
        <form onSubmit={submit} className="space-y-4">
          <Input
            label="Customer / merchant Aadhaar"
            value={form.aadhaarNumber}
            onChange={(e) =>
              setForm({ ...form, aadhaarNumber: e.target.value.replace(/\D/g, '').slice(0, 12) })
            }
            required
            inputMode="numeric"
            placeholder="12-digit Aadhaar"
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
            <span className="mb-1.5 block text-sm font-medium text-gray-700">Bank (IIN)</span>
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
            >
              <option value="">Select bank</option>
              {filteredBanks.map((b) => (
                <option key={b.iin} value={b.iin}>
                  {b.bank_name} ({b.iin})
                </option>
              ))}
            </select>
          </label>
          <Button type="submit" loading={busy} fullWidth>
            Capture fingerprint & complete 2FA
          </Button>
        </form>
      </Card>
    </div>
  );
};

export default AepsTwoFA;
