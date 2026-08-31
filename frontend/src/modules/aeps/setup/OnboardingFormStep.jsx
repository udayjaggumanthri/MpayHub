import React, { useEffect, useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import aepsAPI from '../services/aepsApi';
import { getBrowserGeo } from '../services/mantraRd';
import {
  base64ToDataUrl,
  downloadBase64AsJpeg,
  fileToCompactJpegBase64,
} from '../utils/imageBase64';
import { EMPTY_ONBOARDING_FORM, SETUP_STEPS } from './constants';
import AepsBusyOverlay from './AepsBusyOverlay';
import { useAepsFeedback } from './useAepsFeedback';
import { Btn, Field, InlineAlert, Section, SetupHeader, SetupPageShell, inputCls } from './ui';

export default function OnboardingFormStep({ aepsStatus: status, refreshStatus, loadingStatus }) {
  const navigate = useNavigate();
  const { inline, showError, showSuccess, showInfo, FeedbackPortal } = useAepsFeedback();

  const [form, setForm] = useState(EMPTY_ONBOARDING_FORM);
  const [meta, setMeta] = useState(null);
  const [masters, setMasters] = useState({ states: [], company_types: [] });
  const [savedImages, setSavedImages] = useState({
    merchantPanImage: false,
    maskedAadharImage: false,
    backgroundImageOfShop: false,
  });
  const [fingpayExchange, setFingpayExchange] = useState(null);
  const [busy, setBusy] = useState(false);
  const [busyLabel, setBusyLabel] = useState('');
  const [loading, setLoading] = useState(true);
  const [dirty, setDirty] = useState(false);

  const stage = status?.merchant?.stage || meta?.stage || 'not_started';
  const onboardingLocked = ['ekyc_pending', 'onboarding_submitted', 'active'].includes(stage);

  const activeStep = useMemo(() => {
    if (stage === 'active') return 'ready';
    if (['onboarding_submitted', 'ekyc_pending'].includes(stage)) return 'ekyc';
    return 'onboarding';
  }, [stage]);

  // After onboarding submitted, redirect to device or eKYC step
  useEffect(() => {
    if (!status?.entitled) return;
    if (stage === 'active') {
      navigate('/aeps', { replace: true });
      return;
    }
    if (['ekyc_pending', 'onboarding_submitted'].includes(stage)) {
      const next = status?.merchant?.device_ready ? '/aeps/ekyc' : '/aeps/device';
      navigate(next, { replace: true });
    }
  }, [stage, status?.entitled, status?.merchant?.device_ready, navigate]);

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
      setForm({ ...EMPTY_ONBOARDING_FORM, ...(res.data.form || {}) });
      setSavedImages({
        merchantPanImage: !!res.data.saved_images?.merchantPanImage,
        maskedAadharImage: !!res.data.saved_images?.maskedAadharImage,
        backgroundImageOfShop: !!res.data.saved_images?.backgroundImageOfShop,
      });
      setDirty(false);
      if (!res.data.masters?.states?.length) {
        showError('Could not load Fingpay states master. Check provider is Active and onboarding URL is correct.');
      }
    } else {
      showError(res.message || 'Could not load onboarding form.');
    }
    setLoading(false);
  };

  useEffect(() => {
    if (status?.entitled && !onboardingLocked) loadForm();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [status?.entitled, status?.merchant?.stage]);

  const runBusy = async (label, fn) => {
    if (busy) return;
    setBusy(true);
    setBusyLabel(label);
    try {
      await fn();
    } finally {
      setBusy(false);
      setBusyLabel('');
    }
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
    showInfo('Shop address filled from residence details.', 'Updated');
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
      return 'Enter the full 12-digit Aadhaar (only a masked value is stored after submit).';
    }
    const pan = String(form.userPan || '').trim().toUpperCase();
    if (!/^[A-Z]{5}[0-9]{4}[A-Z]$/.test(pan)) return 'Enter a valid PAN (e.g. ABCDE1234F).';
    if (!/^[A-Z]{4}0[A-Z0-9]{6}$/i.test(String(form.bankIfscCode || '').trim())) {
      return 'Enter a valid IFSC code.';
    }
    const imageChecks = [
      ['merchantPanImage', 'PAN image'],
      ['maskedAadharImage', 'Masked Aadhaar image'],
      ['backgroundImageOfShop', 'Shop background image'],
    ];
    for (const [key, label] of imageChecks) {
      if (!form[key] && !savedImages[key]) return `${label} is required.`;
    }
    return '';
  };

  const submitOnboarding = () =>
    runBusy('Submitting to Fingpay…', async () => {
      const err = validateBeforeSubmit();
      if (err) {
        showError(err);
        return;
      }
      const aadhaarDigits = String(form.aadhaarNumber || '').replace(/\D/g, '');
      if (aadhaarDigits.length !== 12) {
        showError(
          'Enter the full 12-digit Aadhaar number before submit (masked values like xxxxxxxx8750 are not accepted).'
        );
        return;
      }
      const geo = await getBrowserGeo();
      if (geo.status !== 'granted') {
        showError('Location permission is required for Fingpay onboarding.');
        return;
      }
      // Persist full Aadhaar + any NEW compact base64 images; omit unchanged images
      // so we do not re-upload large payloads on every submit.
      const draftPayload = {
        ...form,
        aadhaarNumber: aadhaarDigits,
        userPan: String(form.userPan).trim().toUpperCase(),
        bankIfscCode: String(form.bankIfscCode).trim().toUpperCase(),
      };
      // If image is only marked saved (not in form), don't send empty string that could wipe.
      for (const key of ['merchantPanImage', 'maskedAadharImage', 'backgroundImageOfShop']) {
        if (!draftPayload[key]) delete draftPayload[key];
      }
      await aepsAPI.saveOnboardingDraft(draftPayload);

      const imageOrOmit = (key) => (form[key] ? form[key] : undefined);

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
            aadhaarNumber: aadhaarDigits,
            gstinNumber: String(form.gstinNumber).trim().toUpperCase(),
            companyOrShopPan: String(form.companyOrShopPan || form.userPan).trim().toUpperCase(),
            merchantPanImage: imageOrOmit('merchantPanImage'),
            maskedAadharImage: imageOrOmit('maskedAadharImage'),
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
            backgroundImageOfShop: imageOrOmit('backgroundImageOfShop'),
          },
          merchantPanImage: imageOrOmit('merchantPanImage'),
          maskedAadharImage: imageOrOmit('maskedAadharImage'),
          backgroundImageOfShop: imageOrOmit('backgroundImageOfShop'),
        },
      });

      if (res.success) {
        setFingpayExchange(null);
        setDirty(false);
        await refreshStatus?.();
        const st = await aepsAPI.meStatus();
        const deviceReady = st.success && st.data?.merchant?.device_ready;
        showSuccess('Onboarding submitted to Fingpay successfully.', {
          title: 'Onboarding complete',
          onCloseNavigate: () => navigate(deviceReady ? '/aeps/ekyc' : '/aeps/device'),
        });
      } else {
        setFingpayExchange(res.data?.fingpay_exchange || null);
        const msg = String(res.message || '');
        if (/timeout/i.test(msg)) {
          showError(
            'Fingpay took too long to respond. Re-pick each KYC photo so it converts to compact base64, then submit again.'
          );
        } else {
          showError(msg || 'Onboarding submission failed.');
        }
      }
    });

  const saveDraft = () =>
    runBusy('Saving draft…', async () => {
      const draftPayload = { ...form };
      for (const key of ['merchantPanImage', 'maskedAadharImage', 'backgroundImageOfShop']) {
        if (!draftPayload[key]) delete draftPayload[key];
      }
      const res = await aepsAPI.saveOnboardingDraft(draftPayload);
      if (res.success) {
        setDirty(false);
        showSuccess('Draft saved. KYC images are stored as base64 only (not JPG files).', {
          title: 'Draft saved',
        });
        await refreshStatus?.();
        await loadForm();
      } else {
        showError(res.message || 'Could not save draft.');
      }
    });

  const copyFingpayExchange = async () => {
    if (!fingpayExchange) return;
    const pack = fingpayExchange.share_with_tapits || fingpayExchange;
    try {
      await navigator.clipboard.writeText(JSON.stringify(pack, null, 2));
      showInfo('Fingpay request/response copied — paste it to Tapits.', 'Copied');
    } catch {
      showError('Could not copy automatically. Select the JSON below and copy manually.');
    }
  };

  const onImageFile = async (key, file) => {
    if (!file) return;
    setBusy(true);
    setBusyLabel('Converting image to base64…');
    try {
      const { base64, bytesApprox } = await fileToCompactJpegBase64(file);
      setField(key, base64);
      setSavedImages((prev) => ({ ...prev, [key]: false }));
      showInfo(
        `${key} converted to base64 (${Math.round(bytesApprox / 1024)} KB). Only this compact code is stored — not the original JPG file.`,
        'Image ready'
      );
    } catch (err) {
      showError(err?.message || 'Could not convert image to base64.');
    } finally {
      setBusy(false);
      setBusyLabel('');
      // Allow selecting the same file again after a failed attempt.
      try {
        const input = document.getElementById(`aeps-img-${key}`);
        if (input) input.value = '';
      } catch {
        /* ignore */
      }
    }
  };

  const previewImage = async (key) => {
    if (form[key]) {
      window.open(base64ToDataUrl(form[key]), '_blank', 'noopener,noreferrer');
      return;
    }
    if (!savedImages[key]) {
      showError('No image attached yet.');
      return;
    }
    setBusy(true);
    setBusyLabel('Loading image…');
    try {
      const res = await aepsAPI.getOnboardingImage(key);
      const b64 = res.data?.base64 || res.data?.image_base64;
      if (!res.success || !b64) {
        showError(res.message || 'Could not load saved image.');
        return;
      }
      window.open(base64ToDataUrl(b64), '_blank', 'noopener,noreferrer');
    } finally {
      setBusy(false);
      setBusyLabel('');
    }
  };

  const downloadImage = async (key) => {
    const filename = `${key}.jpg`;
    if (form[key]) {
      downloadBase64AsJpeg(form[key], filename);
      return;
    }
    if (!savedImages[key]) {
      showError('No image attached yet.');
      return;
    }
    setBusy(true);
    setBusyLabel('Preparing download…');
    try {
      const res = await aepsAPI.getOnboardingImage(key);
      const b64 = res.data?.base64 || res.data?.image_base64;
      if (!res.success || !b64) {
        showError(res.message || 'Could not load saved image.');
        return;
      }
      downloadBase64AsJpeg(b64, filename);
    } finally {
      setBusy(false);
      setBusyLabel('');
    }
  };

  const imageHint = (key) => {
    if (form[key]) return `Base64 ready (${Math.round(String(form[key]).length / 1024)} KB) — preview / download below`;
    if (savedImages[key]) return 'Saved as base64 on server — re-upload only to replace';
    return 'Pick JPG/PNG — converted to compact base64 in browser (no file storage)';
  };

  const ImageField = ({ label, fieldKey, required = false, className = '' }) => (
    <Field label={label} hint={imageHint(fieldKey)} required={required} className={className}>
      <input
        id={`aeps-img-${fieldKey}`}
        type="file"
        accept="image/jpeg,image/png,image/jpg,image/webp"
        className="block w-full text-sm"
        onChange={(e) => onImageFile(fieldKey, e.target.files?.[0])}
      />
      {(form[fieldKey] || savedImages[fieldKey]) && (
        <div className="mt-2 flex flex-wrap gap-2">
          <button
            type="button"
            onClick={() => previewImage(fieldKey)}
            className="rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900 px-3 py-1.5 text-xs font-semibold text-slate-700 dark:text-slate-300 hover:bg-slate-50 dark:hover:bg-slate-800"
          >
            Preview
          </button>
          <button
            type="button"
            onClick={() => downloadImage(fieldKey)}
            className="rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900 px-3 py-1.5 text-xs font-semibold text-slate-700 dark:text-slate-300 hover:bg-slate-50 dark:hover:bg-slate-800"
          >
            Download JPG
          </button>
          {form[fieldKey] ? (
            <img
              src={base64ToDataUrl(form[fieldKey])}
              alt={label}
              className="h-16 w-16 rounded-lg border border-slate-200 dark:border-slate-700 object-cover"
            />
          ) : null}
        </div>
      )}
    </Field>
  );

  if (loadingStatus || status == null) {
    return (
      <div className="rounded-2xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900 p-10 text-center text-sm text-slate-500 dark:text-slate-400 shadow-sm">
        Checking AEPS access…
      </div>
    );
  }

  if (!status.entitled) {
    return (
      <div className="rounded-2xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900 p-8 text-center shadow-sm">
        <p className="text-sm font-semibold uppercase tracking-widest text-slate-400 dark:text-slate-500">AEPS</p>
        <h2 className="mt-2 text-xl font-bold text-slate-900 dark:text-slate-100">Access required</h2>
        <p className="mt-2 text-slate-600 dark:text-slate-400">Ask Admin to enable AEPS for your account before onboarding.</p>
      </div>
    );
  }

  if (onboardingLocked) {
    return (
      <SetupPageShell>
        <div className="rounded-2xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900 p-10 text-center text-sm text-slate-500 dark:text-slate-400 shadow-sm">
          Redirecting to the next step…
        </div>
      </SetupPageShell>
    );
  }

  if (loading) {
    return (
      <div className="rounded-2xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900 p-10 text-center text-sm text-slate-500 dark:text-slate-400 shadow-sm">
        Loading merchant setup…
      </div>
    );
  }

  const aadhaarHint = meta?.masked_aadhaar || meta?.prefill?.hints?.aadhaarHint || '';

  return (
    <SetupPageShell>
      {FeedbackPortal}
      <AepsBusyOverlay show={busy} message={busyLabel} />

      <SetupHeader
        title="Merchant setup"
        subtitle="Details are autofilled from your mPayHub profile, KYC, and bank account."
        merchantLoginId={meta?.merchant_login_id}
        stage={stage}
        activeStepId={activeStep}
        steps={SETUP_STEPS}
      />

      {inline.text ? <InlineAlert type={inline.type} text={inline.text} /> : null}

      {fingpayExchange ? (
        <InlineAlert type="error">
          <div className="space-y-2">
            <button
              type="button"
              onClick={copyFingpayExchange}
              className="rounded-lg border border-rose-300 dark:border-rose-800 bg-white dark:bg-slate-900 px-3 py-1.5 text-xs font-medium text-rose-900 dark:text-rose-300 hover:bg-rose-100 dark:hover:bg-rose-900/60"
            >
              Copy request/response for Tapits
            </button>
            <pre className="max-h-56 overflow-auto rounded-lg border border-rose-200 dark:border-rose-800 bg-white/80 dark:bg-slate-900/80 p-2 text-[11px] leading-relaxed text-rose-950 dark:text-rose-200">
              {JSON.stringify(fingpayExchange.share_with_tapits || fingpayExchange, null, 2)}
            </pre>
          </div>
        </InlineAlert>
      ) : null}

      {/* Sections 1–5 — same fields as before */}
      <Section title="1. Personal & contact" subtitle="First name cannot contain spaces (Fingpay rule).">
        <div className="grid gap-4 sm:grid-cols-2">
          <Field label="First name" required>
            <input className={inputCls()} value={form.firstName} onChange={(e) => setField('firstName', e.target.value)} />
          </Field>
          <Field label="Last name" required>
            <input className={inputCls()} value={form.lastName} onChange={(e) => setField('lastName', e.target.value)} />
          </Field>
          <Field label="Mobile number" required>
            <input className={inputCls()} value={form.merchantPhoneNumber} onChange={(e) => setField('merchantPhoneNumber', e.target.value)} />
          </Field>
          <Field label="Email" required>
            <input type="email" className={inputCls()} value={form.emailId} onChange={(e) => setField('emailId', e.target.value)} />
          </Field>
          <Field label="Company / legal name" className="sm:col-span-2">
            <input className={inputCls()} value={form.companyLegalName} onChange={(e) => setField('companyLegalName', e.target.value)} />
          </Field>
          <Field label="Company / shop category (MCC)" required className="sm:col-span-2" hint="companyType = MCC code (e.g. 4812)">
            <select className={inputCls()} value={form.companyType} onChange={(e) => setField('companyType', e.target.value)}>
              <option value="">Select category</option>
              {(masters.company_types || []).map((c) => {
                const mcc = String(c.companyType ?? c.mccCode ?? '');
                return (
                  <option key={c.id ?? mcc} value={mcc}>
                    {c.label || `${c.mccCode} — ${c.mccDescription}`}
                  </option>
                );
              })}
            </select>
          </Field>
        </div>
      </Section>

      <Section title="2. Residence address" subtitle="State from Fingpay getstates (numeric stateId).">
        <div className="grid gap-4 sm:grid-cols-2">
          <Field
            label="Address line 1"
            required
            className="sm:col-span-2"
            hint="Letters/numbers only — no & or ( ). Example: Navodaya school, ravikamtham village"
          >
            <input className={inputCls()} value={form.merchantAddress1} onChange={(e) => setField('merchantAddress1', e.target.value)} />
          </Field>
          <Field label="Address line 2" className="sm:col-span-2">
            <input className={inputCls()} value={form.merchantAddress2} onChange={(e) => setField('merchantAddress2', e.target.value)} />
          </Field>
          <Field label="City" required>
            <input className={inputCls()} value={form.merchantCityName} onChange={(e) => setField('merchantCityName', e.target.value)} />
          </Field>
          <Field label="District" required>
            <input className={inputCls()} value={form.merchantDistrictName} onChange={(e) => setField('merchantDistrictName', e.target.value)} />
          </Field>
          <Field label="State" required>
            <select className={inputCls()} value={String(form.merchantState || '')} onChange={(e) => setField('merchantState', e.target.value)}>
              <option value="">Select state</option>
              {(masters.states || []).map((s) => (
                <option key={s.stateId} value={String(s.stateId)}>
                  {s.state}
                </option>
              ))}
            </select>
          </Field>
          <Field label="PIN code" required>
            <input className={inputCls()} value={form.merchantPinCode} onChange={(e) => setField('merchantPinCode', e.target.value)} maxLength={6} />
          </Field>
        </div>
      </Section>

      <Section title="3. KYC identity">
        <div className="grid gap-4 sm:grid-cols-2">
          <Field label="PAN" required>
            <input className={inputCls('uppercase')} value={form.userPan} onChange={(e) => setField('userPan', e.target.value.toUpperCase())} maxLength={10} />
          </Field>
          <Field label="Aadhaar number" required hint={aadhaarHint ? `Hint: ${aadhaarHint}` : '12-digit Aadhaar'}>
            <input
              className={inputCls()}
              value={form.aadhaarNumber}
              onChange={(e) => setField('aadhaarNumber', e.target.value.replace(/\D/g, '').slice(0, 12))}
              inputMode="numeric"
            />
          </Field>
          <Field label="GSTIN" required>
            <input className={inputCls('uppercase')} value={form.gstinNumber} onChange={(e) => setField('gstinNumber', e.target.value.toUpperCase())} maxLength={15} />
          </Field>
          <Field label="Company / shop PAN" required>
            <input className={inputCls('uppercase')} value={form.companyOrShopPan} onChange={(e) => setField('companyOrShopPan', e.target.value.toUpperCase())} maxLength={10} />
          </Field>
          <ImageField label="PAN image" fieldKey="merchantPanImage" required />
          <ImageField label="Masked Aadhaar image" fieldKey="maskedAadharImage" required />
        </div>
      </Section>

      <Section title="4. Settlement bank">
        <div className="grid gap-4 sm:grid-cols-2">
          <Field label="Account holder name" required>
            <input className={inputCls()} value={form.bankAccountName} onChange={(e) => setField('bankAccountName', e.target.value)} />
          </Field>
          <Field label="Bank name">
            <input className={inputCls()} value={form.companyBankName} onChange={(e) => setField('companyBankName', e.target.value)} />
          </Field>
          <Field label="Branch name">
            <input className={inputCls()} value={form.bankBranchName} onChange={(e) => setField('bankBranchName', e.target.value)} />
          </Field>
          <Field label="Account number" required>
            <input className={inputCls()} value={form.companyBankAccountNumber} onChange={(e) => setField('companyBankAccountNumber', e.target.value)} />
          </Field>
          <Field label="IFSC" required>
            <input className={inputCls('uppercase')} value={form.bankIfscCode} onChange={(e) => setField('bankIfscCode', e.target.value.toUpperCase())} maxLength={11} />
          </Field>
        </div>
      </Section>

      <Section
        title="5. Shop / outlet"
        action={
          <button type="button" onClick={copyResidenceToShop} className="rounded-lg border border-slate-200 dark:border-slate-700 bg-slate-50 dark:bg-slate-800/50 px-3 py-1.5 text-xs font-semibold text-slate-700 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-slate-700">
            Copy from residence
          </button>
        }
      >
        <div className="grid gap-4 sm:grid-cols-2">
          <Field
            label="Shop address"
            required
            className="sm:col-span-2"
            hint="Letters/numbers only — no & or ( )"
          >
            <input className={inputCls()} value={form.shopAddress} onChange={(e) => setField('shopAddress', e.target.value)} />
          </Field>
          <Field label="City" required>
            <input className={inputCls()} value={form.shopCity} onChange={(e) => setField('shopCity', e.target.value)} />
          </Field>
          <Field label="District" required>
            <input className={inputCls()} value={form.shopDistrict} onChange={(e) => setField('shopDistrict', e.target.value)} />
          </Field>
          <Field label="State" required>
            <select className={inputCls()} value={String(form.shopState || '')} onChange={(e) => setField('shopState', e.target.value)}>
              <option value="">Select state</option>
              {(masters.states || []).map((s) => (
                <option key={s.stateId} value={String(s.stateId)}>
                  {s.state}
                </option>
              ))}
            </select>
          </Field>
          <Field label="PIN code" required>
            <input className={inputCls()} value={form.shopPincode} onChange={(e) => setField('shopPincode', e.target.value)} maxLength={6} />
          </Field>
          <ImageField
            label="Shop background image"
            fieldKey="backgroundImageOfShop"
            required
            className="sm:col-span-2"
          />
        </div>
      </Section>

      <div className="sticky bottom-3 z-10 flex flex-wrap items-center justify-between gap-3 rounded-2xl border border-slate-200 dark:border-slate-700 bg-white/95 dark:bg-slate-900/95 px-4 py-3 shadow-lg backdrop-blur">
        <p className="text-xs text-slate-500 dark:text-slate-400">
          {dirty ? 'Unsaved changes' : 'Save draft anytime. Submit sends the merchant to Fingpay.'}
        </p>
        <div className="flex flex-wrap gap-2">
          <Btn onClick={saveDraft} disabled={busy}>
            {busy && busyLabel.includes('Saving') ? 'Saving…' : 'Save draft'}
          </Btn>
          <Btn onClick={submitOnboarding} disabled={busy} primary>
            {busy && busyLabel.includes('Submitting') ? 'Submitting…' : 'Submit to Fingpay'}
          </Btn>
        </div>
      </div>
    </SetupPageShell>
  );
}
