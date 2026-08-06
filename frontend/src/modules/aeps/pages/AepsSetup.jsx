import React, { useEffect, useMemo, useState } from 'react';
import aepsAPI from '../services/aepsApi';
import { captureMantraFingerprint, getBrowserGeo } from '../services/mantraRd';

const EMPTY = {
  firstName: '',
  lastName: '',
  middleName: '',
  merchantPhoneNumber: '',
  emailId: '',
  merchantAddress1: '',
  merchantAddress2: '',
  merchantCityName: '',
  merchantDistrictName: '',
  merchantPinCode: '',
  merchantState: '',
  companyLegalName: '',
  companyType: '',
  userPan: '',
  aadhaarNumber: '',
  gstinNumber: '',
  companyOrShopPan: '',
  companyBankAccountNumber: '',
  bankIfscCode: '',
  companyBankName: '',
  bankBranchName: '',
  bankAccountName: '',
  shopName: '',
  shopAddress: '',
  shopCity: '',
  shopDistrict: '',
  shopState: '',
  shopPincode: '',
  merchantPanImage: '',
  maskedAadharImage: '',
  backgroundImageOfShop: '',
};

const STEPS = [
  { id: 'onboarding', label: 'Merchant details' },
  { id: 'ekyc', label: 'eKYC' },
  { id: 'ready', label: 'Ready' },
];

function Field({ label, hint, required, children, className = '' }) {
  return (
    <label className={`block ${className}`}>
      <span className="text-[11px] font-semibold uppercase tracking-[0.08em] text-slate-500">
        {label}
        {required ? <span className="text-rose-500"> *</span> : null}
      </span>
      <div className="mt-1.5">{children}</div>
      {hint ? <p className="mt-1 text-xs text-slate-400">{hint}</p> : null}
    </label>
  );
}

function inputCls(extra = '') {
  return `w-full rounded-xl border border-slate-200 bg-white px-3.5 py-2.5 text-sm text-slate-900 shadow-sm outline-none transition focus:border-blue-500 focus:ring-2 focus:ring-blue-100 ${extra}`;
}

function Section({ title, subtitle, children, action }) {
  return (
    <section className="rounded-2xl border border-slate-200/80 bg-white p-5 shadow-sm sm:p-6">
      <div className="mb-5 flex flex-wrap items-start justify-between gap-3 border-b border-slate-100 pb-4">
        <div>
          <h3 className="text-base font-semibold text-slate-900">{title}</h3>
          {subtitle ? <p className="mt-1 text-sm text-slate-500">{subtitle}</p> : null}
        </div>
        {action || null}
      </div>
      {children}
    </section>
  );
}

const AepsSetup = ({ aepsStatus: status, refreshStatus }) => {
  const [form, setForm] = useState(EMPTY);
  const [meta, setMeta] = useState(null);
  const [masters, setMasters] = useState({ states: [], company_types: [] });
  const [otp, setOtp] = useState('');
  const [msg, setMsg] = useState({ type: '', text: '' });
  const [busy, setBusy] = useState(false);
  const [loading, setLoading] = useState(true);
  const [dirty, setDirty] = useState(false);

  const stage = status?.merchant?.stage || meta?.stage || 'not_started';
  const activeStep = useMemo(() => {
    if (stage === 'active') return 'ready';
    if (['onboarding_submitted', 'ekyc_pending'].includes(stage)) return 'ekyc';
    return 'onboarding';
  }, [stage]);

  const setField = (key, value) => {
    setDirty(true);
    setForm((prev) => ({ ...prev, [key]: value }));
  };

  const loadForm = async () => {
    setLoading(true);
    const res = await aepsAPI.getOnboardingForm();
    if (res.success && res.data) {
      setMeta(res.data);
      setMasters(res.data.masters || { states: [], company_types: [] });
      setForm({ ...EMPTY, ...(res.data.form || {}) });
      setDirty(false);
      if (!res.data.masters?.states?.length) {
        setMsg({
          type: 'error',
          text: 'Could not load Fingpay states master. Check provider is Active and onboarding URL is correct.',
        });
      } else if (res.data.has_saved_draft) {
        setMsg({ type: 'info', text: 'Saved draft restored. Review autofilled details before submitting.' });
      } else if (res.data.prefill?.sources?.length) {
        setMsg({
          type: 'info',
          text: `Autofilled from your mPayHub profile (${res.data.prefill.sources.join(', ')}). Complete any missing fields.`,
        });
      }
    } else {
      setMsg({ type: 'error', text: res.message || 'Could not load onboarding form.' });
    }
    setLoading(false);
  };

  useEffect(() => {
    if (status?.entitled) loadForm();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [status?.entitled, status?.merchant?.stage]);

  const notify = (type, text) => setMsg({ type, text });

  const saveDraft = async () => {
    setBusy(true);
    const res = await aepsAPI.saveOnboardingDraft(form);
    if (res.success) {
      setDirty(false);
      notify('success', 'Draft saved. You can leave and continue later.');
      await refreshStatus?.();
      await loadForm();
    } else {
      notify('error', res.message || 'Could not save draft.');
    }
    setBusy(false);
  };

  const copyResidenceToShop = () => {
    setDirty(true);
    setForm((prev) => ({
      ...prev,
      shopAddress: prev.shopAddress || prev.merchantAddress1,
      shopCity: prev.shopCity || prev.merchantCityName,
      shopDistrict: prev.shopDistrict || prev.merchantDistrictName,
      shopState: prev.shopState || prev.merchantState,
      shopPincode: prev.shopPincode || prev.merchantPinCode,
    }));
    notify('info', 'Shop address filled from residence details.');
  };

  const validateBeforeSubmit = () => {
    const required = [
      ['firstName', 'First name'],
      ['lastName', 'Last name'],
      ['merchantPhoneNumber', 'Mobile number'],
      ['emailId', 'Email'],
      ['merchantAddress1', 'Address'],
      ['merchantCityName', 'City'],
      ['merchantDistrictName', 'District'],
      ['merchantPinCode', 'PIN code'],
      ['merchantState', 'State'],
      ['companyType', 'Company / shop category'],
      ['userPan', 'PAN'],
      ['aadhaarNumber', 'Aadhaar'],
      ['gstinNumber', 'GSTIN'],
      ['companyOrShopPan', 'Company / shop PAN'],
      ['companyBankAccountNumber', 'Bank account number'],
      ['bankIfscCode', 'IFSC'],
      ['bankAccountName', 'Account holder name'],
      ['shopAddress', 'Shop address'],
      ['shopCity', 'Shop city'],
      ['shopDistrict', 'Shop district'],
      ['shopState', 'Shop state'],
      ['shopPincode', 'Shop PIN'],
    ];
    for (const [key, label] of required) {
      if (!String(form[key] || '').trim()) return `${label} is required.`;
    }
    if (!/^\d+$/.test(String(form.merchantState))) {
      return 'Select state from the Fingpay state list (numeric stateId).';
    }
    if (!/^\d+$/.test(String(form.companyType))) {
      return 'Select company type from the Fingpay master list.';
    }
    const aadhaar = String(form.aadhaarNumber || '').replace(/\s/g, '');
    if (!/^\d{12}$/.test(aadhaar)) {
      return 'Enter the full 12-digit Aadhaar (draft stores only a masked value for security).';
    }
    const pan = String(form.userPan || '').trim().toUpperCase();
    if (!/^[A-Z]{5}[0-9]{4}[A-Z]$/.test(pan)) return 'Enter a valid PAN (e.g. ABCDE1234F).';
    if (!/^[A-Z]{4}0[A-Z0-9]{6}$/i.test(String(form.bankIfscCode || '').trim())) {
      return 'Enter a valid IFSC code.';
    }
    return '';
  };

  const submitOnboarding = async () => {
    const err = validateBeforeSubmit();
    if (err) {
      notify('error', err);
      return;
    }
    setBusy(true);
    notify('', '');
    const geo = await getBrowserGeo();
    if (geo.status !== 'granted') {
      notify('error', 'Location permission is required for Fingpay onboarding.');
      setBusy(false);
      return;
    }
    // Persist draft first so refresh does not lose edits
    await aepsAPI.saveOnboardingDraft({
      ...form,
      aadhaarNumber: String(form.aadhaarNumber).replace(/\s/g, ''),
      userPan: String(form.userPan).trim().toUpperCase(),
      bankIfscCode: String(form.bankIfscCode).trim().toUpperCase(),
    });

    const res = await aepsAPI.submitOnboarding({
      latitude: geo.latitude,
      longitude: geo.longitude,
      merchant: {
        firstName: form.firstName.trim(),
        lastName: form.lastName.trim(),
        middleName: (form.middleName || '').trim(),
        merchantPhoneNumber: form.merchantPhoneNumber.trim(),
        emailId: form.emailId.trim(),
        companyLegalName: (form.companyLegalName || form.shopName || '').trim(),
        companyType: Number(form.companyType),
        merchantAddress: {
          merchantAddress1: form.merchantAddress1.trim(),
          merchantAddress2: (form.merchantAddress2 || '').trim(),
          merchantState: Number(form.merchantState),
          merchantCityName: form.merchantCityName.trim(),
          merchantDistrictName: form.merchantDistrictName.trim(),
          merchantPinCode: form.merchantPinCode.trim(),
        },
        kyc: {
          userPan: String(form.userPan).trim().toUpperCase(),
          aadhaarNumber: String(form.aadhaarNumber).replace(/\s/g, ''),
          gstinNumber: String(form.gstinNumber).trim().toUpperCase(),
          companyOrShopPan: String(form.companyOrShopPan || form.userPan).trim().toUpperCase(),
          merchantPanImage: form.merchantPanImage || undefined,
          maskedAadharImage: form.maskedAadharImage || undefined,
        },
        settlementV1: {
          companyBankAccountNumber: form.companyBankAccountNumber.trim(),
          bankIfscCode: String(form.bankIfscCode).trim().toUpperCase(),
          companyBankName: (form.companyBankName || '').trim(),
          bankBranchName: (form.bankBranchName || form.companyBankName || '').trim(),
          bankAccountName: form.bankAccountName.trim(),
        },
        merchantKycAddressData: {
          shopAddress: form.shopAddress.trim(),
          shopCity: form.shopCity.trim(),
          shopDistrict: form.shopDistrict.trim(),
          shopState: Number(form.shopState || form.merchantState),
          shopPincode: form.shopPincode.trim(),
          shopLatitude: geo.latitude,
          shopLongitude: geo.longitude,
          backgroundImageOfShop: form.backgroundImageOfShop || undefined,
        },
        // Also send flat image keys for draft/builder overlay
        merchantPanImage: form.merchantPanImage || undefined,
        maskedAadharImage: form.maskedAadharImage || undefined,
        backgroundImageOfShop: form.backgroundImageOfShop || undefined,
      },
    });
    if (res.success) {
      notify('success', 'Onboarding submitted to Fingpay. Continue with eKYC below.');
      setDirty(false);
      await refreshStatus?.();
      await loadForm();
    } else {
      notify('error', res.message || 'Onboarding submission failed.');
    }
    setBusy(false);
  };

  const startEkyc = async () => {
    setBusy(true);
    const geo = await getBrowserGeo();
    const aadhaar = String(form.aadhaarNumber || '').replace(/\s/g, '');
    const res = await aepsAPI.ekycStart({
      latitude: geo.latitude,
      longitude: geo.longitude,
      mobileNumber: form.merchantPhoneNumber,
      aadhaarNumber: /^\d{12}$/.test(aadhaar) ? aadhaar : undefined,
      panNumber: form.userPan,
      device_imei: status?.merchant?.device_imei || meta?.device_imei || '',
    });
    notify(res.success ? 'success' : 'error', res.success ? 'OTP sent to the registered mobile.' : res.message);
    setBusy(false);
  };

  const verifyOtp = async () => {
    setBusy(true);
    const res = await aepsAPI.ekycOtp(otp);
    notify(res.success ? 'success' : 'error', res.success ? 'OTP verified. Capture fingerprint next.' : res.message);
    setBusy(false);
  };

  const resendOtp = async () => {
    setBusy(true);
    const res = await aepsAPI.ekycResend();
    notify(res.success ? 'success' : 'error', res.success ? 'OTP resent.' : res.message);
    setBusy(false);
  };

  const checkEkycStatus = async () => {
    setBusy(true);
    const res = await aepsAPI.ekycStatus('EKYC');
    if (res.success) {
      notify('info', res.message || res.data?.message || JSON.stringify(res.data?.status || res.data || {}).slice(0, 200));
      await refreshStatus?.();
    } else {
      notify('error', res.message || 'Status check failed');
    }
    setBusy(false);
  };

  const onImageFile = (key, file) => {
    if (!file) return;
    if (file.size > 900 * 1024) {
      notify('error', 'Image must be under ~900KB (Fingpay base64 limit).');
      return;
    }
    const reader = new FileReader();
    reader.onload = () => {
      const dataUrl = String(reader.result || '');
      const b64 = dataUrl.includes(',') ? dataUrl.split(',')[1] : dataUrl;
      setField(key, b64);
      notify('info', `${key} attached (${Math.round(file.size / 1024)} KB). Save draft or submit.`);
    };
    reader.readAsDataURL(file);
  };

  const biometric = async () => {
    setBusy(true);
    const geo = await getBrowserGeo();
    const cap = await captureMantraFingerprint();
    if (!cap.success) {
      notify('error', cap.message || 'Fingerprint capture failed');
      setBusy(false);
      return;
    }
    const res = await aepsAPI.ekycBiometric({
      latitude: geo.latitude,
      longitude: geo.longitude,
      captureResponse: cap.captureResponse,
    });
    notify(res.success ? 'success' : 'error', res.success ? 'eKYC completed. Merchant is active.' : res.message);
    await refreshStatus?.();
    setBusy(false);
  };

  if (!status?.entitled) {
    return (
      <div className="rounded-2xl border border-slate-200 bg-white p-8 text-center shadow-sm">
        <p className="text-sm font-semibold uppercase tracking-widest text-slate-400">AEPS</p>
        <h2 className="mt-2 text-xl font-bold text-slate-900">Access required</h2>
        <p className="mt-2 text-slate-600">Ask Admin to enable AEPS for your account before onboarding.</p>
      </div>
    );
  }

  if (loading) {
    return (
      <div className="rounded-2xl border border-slate-200 bg-white p-10 text-center text-sm text-slate-500 shadow-sm">
        Loading merchant setup…
      </div>
    );
  }

  const aadhaarHint = meta?.masked_aadhaar || meta?.prefill?.hints?.aadhaarHint || '';
  const onboardingLocked = ['ekyc_pending', 'onboarding_submitted', 'active'].includes(stage);

  return (
    <div className="mx-auto max-w-5xl space-y-6">
      <header className="rounded-2xl border border-slate-200/80 bg-gradient-to-br from-slate-900 via-slate-800 to-blue-900 px-6 py-6 text-white shadow-sm sm:px-8">
        <p className="text-xs font-semibold uppercase tracking-[0.18em] text-blue-200">AEPS activation</p>
        <div className="mt-2 flex flex-wrap items-end justify-between gap-4">
          <div>
            <h2 className="text-2xl font-bold tracking-tight">Merchant setup</h2>
            <p className="mt-1 max-w-xl text-sm text-slate-300">
              Details are autofilled from your mPayHub profile, KYC, and bank account. Saved drafts are restored
              automatically.
            </p>
          </div>
          <div className="rounded-xl border border-white/10 bg-white/5 px-4 py-3 text-right text-sm">
            <p className="text-slate-300">Merchant login</p>
            <p className="font-mono font-semibold text-white">{meta?.merchant_login_id || '—'}</p>
            <p className="mt-1 text-xs capitalize text-blue-200">{String(stage).replaceAll('_', ' ')}</p>
          </div>
        </div>

        <ol className="mt-6 grid gap-2 sm:grid-cols-3">
          {STEPS.map((step, idx) => {
            const done =
              (step.id === 'onboarding' && ['ekyc_pending', 'onboarding_submitted', 'active'].includes(stage)) ||
              (step.id === 'ekyc' && stage === 'active') ||
              (step.id === 'ready' && stage === 'active');
            const current = activeStep === step.id;
            return (
              <li
                key={step.id}
                className={`rounded-xl px-3 py-2.5 text-sm ${
                  current ? 'bg-white text-slate-900' : done ? 'bg-emerald-500/20 text-emerald-100' : 'bg-white/5 text-slate-300'
                }`}
              >
                <span className="text-[10px] font-bold uppercase tracking-wider opacity-70">Step {idx + 1}</span>
                <p className="font-semibold">{step.label}</p>
              </li>
            );
          })}
        </ol>
      </header>

      {msg.text ? (
        <div
          className={`rounded-xl border px-4 py-3 text-sm ${
            msg.type === 'error'
              ? 'border-rose-200 bg-rose-50 text-rose-800'
              : msg.type === 'success'
                ? 'border-emerald-200 bg-emerald-50 text-emerald-800'
                : 'border-sky-200 bg-sky-50 text-sky-900'
          }`}
        >
          <p>{msg.text}</p>
          {msg.type === 'error' && /403|whitelist|blocked our server/i.test(msg.text) ? (
            <p className="mt-2 text-xs text-rose-700/90">
              Next step: message Tapits to whitelist server IP <strong>57.131.39.21</strong> on Production
              host <code>fingpayap.tapits.in</code>. After they confirm, click Submit to Fingpay again.
            </p>
          ) : null}
          {dirty && msg.type !== 'error' ? (
            <span className="mt-1 block text-xs opacity-70">(unsaved changes)</span>
          ) : null}
        </div>
      ) : null}

      <Section
        title="1. Personal & contact"
        subtitle="Pulled from your user profile where available. First name cannot contain spaces (Fingpay rule)."
      >
        <div className="grid gap-4 sm:grid-cols-2">
          <Field label="First name" required hint="Letters only — spaces removed on submit">
            <input className={inputCls()} value={form.firstName} onChange={(e) => setField('firstName', e.target.value)} disabled={onboardingLocked} />
          </Field>
          <Field label="Last name" required>
            <input className={inputCls()} value={form.lastName} onChange={(e) => setField('lastName', e.target.value)} disabled={onboardingLocked} />
          </Field>
          <Field label="Mobile number" required hint="10-digit merchant phone">
            <input className={inputCls()} value={form.merchantPhoneNumber} onChange={(e) => setField('merchantPhoneNumber', e.target.value)} disabled={onboardingLocked} />
          </Field>
          <Field label="Email" required>
            <input type="email" className={inputCls()} value={form.emailId} onChange={(e) => setField('emailId', e.target.value)} disabled={onboardingLocked} />
          </Field>
          <Field label="Company / legal name" className="sm:col-span-2">
            <input className={inputCls()} value={form.companyLegalName} onChange={(e) => setField('companyLegalName', e.target.value)} disabled={onboardingLocked} />
          </Field>
          <Field
            label="Company / shop category (MCC)"
            required
            className="sm:col-span-2"
            hint="Fingpay companyType master — mandatory"
          >
            <select
              className={inputCls()}
              value={form.companyType}
              onChange={(e) => setField('companyType', e.target.value)}
              disabled={onboardingLocked}
            >
              <option value="">Select category</option>
              {(masters.company_types || []).map((c) => (
                <option key={c.id} value={String(c.id)}>
                  {c.label || `${c.mccCode} — ${c.mccDescription}`}
                </option>
              ))}
            </select>
          </Field>
        </div>
      </Section>

      <Section
        title="2. Residence address"
        subtitle="State must be chosen from Fingpay getstates (numeric stateId)."
      >
        <div className="grid gap-4 sm:grid-cols-2">
          <Field label="Address line 1" required className="sm:col-span-2">
            <input className={inputCls()} value={form.merchantAddress1} onChange={(e) => setField('merchantAddress1', e.target.value)} disabled={onboardingLocked} />
          </Field>
          <Field label="Address line 2" hint="Min 11 characters (auto-padded if short)" className="sm:col-span-2">
            <input className={inputCls()} value={form.merchantAddress2} onChange={(e) => setField('merchantAddress2', e.target.value)} disabled={onboardingLocked} />
          </Field>
          <Field label="City" required>
            <input className={inputCls()} value={form.merchantCityName} onChange={(e) => setField('merchantCityName', e.target.value)} disabled={onboardingLocked} />
          </Field>
          <Field label="District" required>
            <input className={inputCls()} value={form.merchantDistrictName} onChange={(e) => setField('merchantDistrictName', e.target.value)} disabled={onboardingLocked} />
          </Field>
          <Field label="State" required>
            <select className={inputCls()} value={String(form.merchantState || '')} onChange={(e) => setField('merchantState', e.target.value)} disabled={onboardingLocked}>
              <option value="">Select state</option>
              {(masters.states || []).map((s) => (
                <option key={s.stateId} value={String(s.stateId)}>
                  {s.state}
                </option>
              ))}
            </select>
          </Field>
          <Field label="PIN code" required>
            <input className={inputCls()} value={form.merchantPinCode} onChange={(e) => setField('merchantPinCode', e.target.value)} disabled={onboardingLocked} maxLength={6} />
          </Field>
        </div>
      </Section>

      <Section title="3. KYC identity" subtitle="GSTIN & company PAN are mandatory per Fingpay (usually Super Merchant values).">
        <div className="grid gap-4 sm:grid-cols-2">
          <Field label="PAN" required>
            <input
              className={inputCls('uppercase')}
              value={form.userPan}
              onChange={(e) => setField('userPan', e.target.value.toUpperCase())}
              disabled={onboardingLocked}
              maxLength={10}
            />
          </Field>
          <Field
            label="Aadhaar number"
            required
            hint={aadhaarHint ? `Previously saved as ${aadhaarHint}. Re-enter full 12 digits to submit.` : '12-digit Aadhaar'}
          >
            <input
              className={inputCls()}
              value={form.aadhaarNumber?.startsWith?.('x') ? '' : form.aadhaarNumber}
              onChange={(e) => setField('aadhaarNumber', e.target.value.replace(/\D/g, '').slice(0, 12))}
              disabled={onboardingLocked}
              placeholder={aadhaarHint ? 'Re-enter 12-digit Aadhaar' : 'XXXX XXXX XXXX'}
              inputMode="numeric"
            />
          </Field>
          <Field label="GSTIN" required hint="From Admin AEPS provider settings when configured">
            <input
              className={inputCls('uppercase')}
              value={form.gstinNumber}
              onChange={(e) => setField('gstinNumber', e.target.value.toUpperCase())}
              disabled={onboardingLocked}
              maxLength={15}
            />
          </Field>
          <Field label="Company / shop PAN" required>
            <input
              className={inputCls('uppercase')}
              value={form.companyOrShopPan}
              onChange={(e) => setField('companyOrShopPan', e.target.value.toUpperCase())}
              disabled={onboardingLocked}
              maxLength={10}
            />
          </Field>
          <Field label="PAN image (5023)" hint={form.merchantPanImage ? 'Attached' : 'JPEG/PNG under 900KB'} required>
            <input
              type="file"
              accept="image/*"
              disabled={onboardingLocked}
              className="block w-full text-sm"
              onChange={(e) => onImageFile('merchantPanImage', e.target.files?.[0])}
            />
          </Field>
          <Field label="Masked Aadhaar image (5024)" hint={form.maskedAadharImage ? 'Attached' : 'JPEG/PNG under 900KB'} required>
            <input
              type="file"
              accept="image/*"
              disabled={onboardingLocked}
              className="block w-full text-sm"
              onChange={(e) => onImageFile('maskedAadharImage', e.target.files?.[0])}
            />
          </Field>
        </div>
      </Section>

      <Section title="4. Settlement bank" subtitle="Autofilled from your verified bank account when available.">
        <div className="grid gap-4 sm:grid-cols-2">
          <Field label="Account holder name" required>
            <input className={inputCls()} value={form.bankAccountName} onChange={(e) => setField('bankAccountName', e.target.value)} disabled={onboardingLocked} />
          </Field>
          <Field label="Bank name">
            <input className={inputCls()} value={form.companyBankName} onChange={(e) => setField('companyBankName', e.target.value)} disabled={onboardingLocked} />
          </Field>
          <Field label="Branch name" hint="Fingpay settlement.bankBranchName">
            <input className={inputCls()} value={form.bankBranchName} onChange={(e) => setField('bankBranchName', e.target.value)} disabled={onboardingLocked} />
          </Field>
          <Field label="Account number" required>
            <input className={inputCls()} value={form.companyBankAccountNumber} onChange={(e) => setField('companyBankAccountNumber', e.target.value)} disabled={onboardingLocked} />
          </Field>
          <Field label="IFSC" required>
            <input
              className={inputCls('uppercase')}
              value={form.bankIfscCode}
              onChange={(e) => setField('bankIfscCode', e.target.value.toUpperCase())}
              disabled={onboardingLocked}
              maxLength={11}
            />
          </Field>
        </div>
      </Section>

      <Section
        title="5. Shop / outlet"
        subtitle="Business location used for merchant KYC address."
        action={
          !onboardingLocked ? (
            <button
              type="button"
              onClick={copyResidenceToShop}
              className="rounded-lg border border-slate-200 bg-slate-50 px-3 py-1.5 text-xs font-semibold text-slate-700 hover:bg-slate-100"
            >
              Copy from residence
            </button>
          ) : null
        }
      >
        <div className="grid gap-4 sm:grid-cols-2">
          <Field label="Shop / business name" className="sm:col-span-2">
            <input className={inputCls()} value={form.shopName} onChange={(e) => setField('shopName', e.target.value)} disabled={onboardingLocked} />
          </Field>
          <Field label="Shop address" required className="sm:col-span-2">
            <input className={inputCls()} value={form.shopAddress} onChange={(e) => setField('shopAddress', e.target.value)} disabled={onboardingLocked} />
          </Field>
          <Field label="City" required>
            <input className={inputCls()} value={form.shopCity} onChange={(e) => setField('shopCity', e.target.value)} disabled={onboardingLocked} />
          </Field>
          <Field label="District" required>
            <input className={inputCls()} value={form.shopDistrict} onChange={(e) => setField('shopDistrict', e.target.value)} disabled={onboardingLocked} />
          </Field>
          <Field label="State" required>
            <select className={inputCls()} value={String(form.shopState || '')} onChange={(e) => setField('shopState', e.target.value)} disabled={onboardingLocked}>
              <option value="">Select state</option>
              {(masters.states || []).map((s) => (
                <option key={s.stateId} value={String(s.stateId)}>
                  {s.state}
                </option>
              ))}
            </select>
          </Field>
          <Field label="PIN code" required>
            <input className={inputCls()} value={form.shopPincode} onChange={(e) => setField('shopPincode', e.target.value)} disabled={onboardingLocked} maxLength={6} />
          </Field>
          <Field
            label="Shop background image (5041)"
            hint={form.backgroundImageOfShop ? 'Attached' : 'JPEG/PNG under 900KB'}
            className="sm:col-span-2"
            required
          >
            <input
              type="file"
              accept="image/*"
              disabled={onboardingLocked}
              className="block w-full text-sm"
              onChange={(e) => onImageFile('backgroundImageOfShop', e.target.files?.[0])}
            />
          </Field>
        </div>
      </Section>

      {!onboardingLocked ? (
        <div className="sticky bottom-3 z-10 flex flex-wrap items-center justify-between gap-3 rounded-2xl border border-slate-200 bg-white/95 px-4 py-3 shadow-lg backdrop-blur">
          <p className="text-xs text-slate-500">Save draft anytime. Submit sends the merchant to Fingpay.</p>
          <div className="flex flex-wrap gap-2">
            <Btn onClick={saveDraft} disabled={busy}>
              Save draft
            </Btn>
            <Btn onClick={submitOnboarding} disabled={busy} primary>
              Submit to Fingpay
            </Btn>
          </div>
        </div>
      ) : null}

      <Section title="6. eKYC verification" subtitle="Requires Mantra RD Service, location permission, and a registered device serial.">
        {stage === 'not_started' || stage === 'onboarding_draft' ? (
          <p className="text-sm text-slate-500">Submit merchant onboarding first, then complete eKYC here.</p>
        ) : stage === 'active' ? (
          <p className="text-sm font-medium text-emerald-700">eKYC complete — merchant is active.</p>
        ) : (
          <div className="flex flex-wrap items-end gap-3">
            <Btn onClick={startEkyc} disabled={busy}>
              Send OTP
            </Btn>
            <Btn onClick={resendOtp} disabled={busy}>
              Resend OTP
            </Btn>
            <Field label="OTP">
              <input className={inputCls('w-36')} value={otp} onChange={(e) => setOtp(e.target.value)} placeholder="6-digit OTP" />
            </Field>
            <Btn onClick={verifyOtp} disabled={busy || !otp}>
              Verify OTP
            </Btn>
            <Btn onClick={biometric} disabled={busy} primary>
              Capture fingerprint
            </Btn>
            <Btn onClick={checkEkycStatus} disabled={busy}>
              Check eKYC status
            </Btn>
          </div>
        )}
      </Section>
    </div>
  );
};

const Btn = ({ children, onClick, disabled, primary }) => (
  <button
    type="button"
    onClick={onClick}
    disabled={disabled}
    className={`rounded-xl px-4 py-2.5 text-sm font-semibold transition disabled:opacity-50 ${
      primary
        ? 'bg-blue-600 text-white shadow-sm hover:bg-blue-700'
        : 'border border-slate-200 bg-white text-slate-800 hover:bg-slate-50'
    }`}
  >
    {children}
  </button>
);

export default AepsSetup;
