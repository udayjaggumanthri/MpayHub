import React, { useState } from 'react';
import aepsAPI from '../services/aepsApi';
import { captureMantraFingerprint, getBrowserGeo } from '../services/mantraRd';

const emptyDraft = {
  firstName: '',
  lastName: '',
  merchantPhoneNumber: '',
  emailId: '',
  merchantAddress1: '',
  merchantCityName: '',
  merchantDistrictName: '',
  merchantPinCode: '',
  merchantState: '',
  userPan: '',
  aadhaarNumber: '',
  companyBankAccountNumber: '',
  bankIfscCode: '',
  bankAccountName: '',
  shopAddress: '',
  shopCity: '',
  shopDistrict: '',
  shopState: '',
  shopPincode: '',
};

const AepsSetup = ({ aepsStatus: status, refreshStatus }) => {
  const [draft, setDraft] = useState(emptyDraft);
  const [otp, setOtp] = useState('');
  const [msg, setMsg] = useState('');
  const [busy, setBusy] = useState(false);

  const setField = (k, v) => setDraft((d) => ({ ...d, [k]: v }));

  const saveDraft = async () => {
    setBusy(true);
    const res = await aepsAPI.saveOnboardingDraft(draft);
    setMsg(res.success ? 'Draft saved.' : res.message);
    setBusy(false);
  };

  const submitOnboarding = async () => {
    setBusy(true);
    setMsg('');
    const geo = await getBrowserGeo();
    if (geo.status !== 'granted') {
      setMsg('Location permission is required for onboarding.');
      setBusy(false);
      return;
    }
    const res = await aepsAPI.submitOnboarding({
      latitude: geo.latitude,
      longitude: geo.longitude,
      merchant: {
        firstName: draft.firstName,
        lastName: draft.lastName,
        merchantPhoneNumber: draft.merchantPhoneNumber,
        emailId: draft.emailId,
        merchantAddress: {
          merchantAddress1: draft.merchantAddress1,
          merchantAddress2: '',
          merchantState: Number(draft.merchantState) || draft.merchantState,
          merchantCityName: draft.merchantCityName,
          merchantDistrictName: draft.merchantDistrictName,
          merchantPinCode: draft.merchantPinCode,
        },
        kyc: {
          userPan: draft.userPan,
          aadhaarNumber: draft.aadhaarNumber,
        },
        settlementV1: {
          companyBankAccountNumber: draft.companyBankAccountNumber,
          bankIfscCode: draft.bankIfscCode,
          bankAccountName: draft.bankAccountName,
        },
        merchantKycAddressData: {
          shopAddress: draft.shopAddress,
          shopCity: draft.shopCity,
          shopDistrict: draft.shopDistrict,
          shopState: Number(draft.shopState) || draft.shopState,
          shopPincode: draft.shopPincode,
          shopLatitude: geo.latitude,
          shopLongitude: geo.longitude,
        },
      },
    });
    setMsg(res.success ? 'Onboarding submitted. Continue with eKYC.' : res.message);
    await refreshStatus();
    setBusy(false);
  };

  const startEkyc = async () => {
    setBusy(true);
    const geo = await getBrowserGeo();
    const res = await aepsAPI.ekycStart({
      latitude: geo.latitude,
      longitude: geo.longitude,
      mobileNumber: draft.merchantPhoneNumber,
      aadhaarNumber: draft.aadhaarNumber,
      panNumber: draft.userPan,
      device_imei: status?.merchant?.device_imei || '',
    });
    setMsg(res.success ? 'OTP sent. Enter OTP below.' : res.message);
    setBusy(false);
  };

  const verifyOtp = async () => {
    setBusy(true);
    const res = await aepsAPI.ekycOtp(otp);
    setMsg(res.success ? 'OTP verified. Capture fingerprint next.' : res.message);
    setBusy(false);
  };

  const biometric = async () => {
    setBusy(true);
    const geo = await getBrowserGeo();
    const cap = await captureMantraFingerprint();
    if (!cap.success) {
      setMsg(cap.message || 'Fingerprint capture failed');
      setBusy(false);
      return;
    }
    const res = await aepsAPI.ekycBiometric({
      latitude: geo.latitude,
      longitude: geo.longitude,
      captureResponse: cap.captureResponse,
    });
    setMsg(res.success ? 'eKYC completed. Merchant active.' : res.message);
    await refreshStatus();
    setBusy(false);
  };

  if (!status?.entitled) {
    return <p className="rounded-2xl border bg-white p-6 text-slate-600">Enable AEPS access first.</p>;
  }

  return (
    <div className="space-y-6">
      <header>
        <h2 className="text-xl font-bold text-slate-900">Setup journey</h2>
        <p className="text-sm text-slate-500">Onboarding → eKYC (Mantra) → ready</p>
      </header>

      <section className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
        <h3 className="font-semibold text-slate-900">1. Merchant onboarding</h3>
        <div className="mt-4 grid gap-3 sm:grid-cols-2">
          {Object.keys(emptyDraft).map((key) => (
            <label key={key} className="text-xs font-medium text-slate-600">
              {key}
              <input
                className="mt-1 w-full rounded-lg border border-slate-200 px-3 py-2 text-sm"
                value={draft[key]}
                onChange={(e) => setField(key, e.target.value)}
              />
            </label>
          ))}
        </div>
        <div className="mt-4 flex flex-wrap gap-2">
          <Btn onClick={saveDraft} disabled={busy}>
            Save draft
          </Btn>
          <Btn onClick={submitOnboarding} disabled={busy} primary>
            Submit to Fingpay
          </Btn>
        </div>
      </section>

      <section className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
        <h3 className="font-semibold text-slate-900">2. eKYC</h3>
        <p className="mt-1 text-sm text-slate-500">Requires Mantra device and location.</p>
        <div className="mt-4 flex flex-wrap items-end gap-3">
          <Btn onClick={startEkyc} disabled={busy}>
            Send OTP
          </Btn>
          <input
            className="rounded-lg border border-slate-200 px-3 py-2 text-sm"
            placeholder="OTP"
            value={otp}
            onChange={(e) => setOtp(e.target.value)}
          />
          <Btn onClick={verifyOtp} disabled={busy}>
            Verify OTP
          </Btn>
          <Btn onClick={biometric} disabled={busy} primary>
            Capture fingerprint
          </Btn>
        </div>
      </section>

      {msg ? <p className="text-sm font-medium text-slate-700">{msg}</p> : null}
    </div>
  );
};

const Btn = ({ children, onClick, disabled, primary }) => (
  <button
    type="button"
    onClick={onClick}
    disabled={disabled}
    className={`rounded-lg px-4 py-2 text-sm font-semibold disabled:opacity-50 ${
      primary ? 'bg-blue-600 text-white hover:bg-blue-700' : 'bg-slate-100 text-slate-800 hover:bg-slate-200'
    }`}
  >
    {children}
  </button>
);

export default AepsSetup;
