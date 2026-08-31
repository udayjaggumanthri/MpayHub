import React, { useEffect, useMemo, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import aepsAPI from '../services/aepsApi';
import { captureMantraFingerprint, detectMantraRd, getBrowserGeo } from '../services/mantraRd';
import { SETUP_STEPS } from './constants';
import AepsBusyOverlay from './AepsBusyOverlay';
import { useAepsFeedback } from './useAepsFeedback';
import { Btn, Field, InlineAlert, Section, SetupHeader, SetupPageShell, inputCls } from './ui';

export default function EkycStep({ aepsStatus: status, refreshStatus, loadingStatus }) {
  const navigate = useNavigate();
  const { inline, showError, showSuccess, showInfo, FeedbackPortal } = useAepsFeedback();

  const [meta, setMeta] = useState(null);
  const [ekycAadhaar, setEkycAadhaar] = useState('');
  const [otp, setOtp] = useState('');
  const [busy, setBusy] = useState(false);
  const [busyLabel, setBusyLabel] = useState('');
  const [loading, setLoading] = useState(true);

  const stage = status?.merchant?.stage || meta?.stage || 'not_started';
  const maskedHint = meta?.masked_aadhaar || status?.merchant?.masked_aadhaar || '';
  const hasStoredAadhaar = meta?.has_stored_aadhaar || false;
  const pan = meta?.form?.userPan || status?.merchant?.onboarding_summary?.userPan || '';
  const mobile =
    meta?.form?.merchantPhoneNumber || status?.merchant?.onboarding_summary?.merchantPhoneNumber || '';
  const deviceImei = status?.merchant?.device_imei || meta?.device_imei || '';
  const scannerSerial = status?.merchant?.scanner_serial || meta?.scanner_serial || '';

  const activeStep = useMemo(() => {
    if (stage === 'active') return 'ready';
    return 'ekyc';
  }, [stage]);

  useEffect(() => {
    if (!status?.entitled) return;
    if (stage === 'not_started' || stage === 'onboarding_draft') {
      navigate('/aeps/setup', { replace: true });
    }
  }, [stage, status?.entitled, navigate]);

  const loadMeta = async () => {
    setLoading(true);
    const res = await aepsAPI.getOnboardingForm();
    if (res.success && res.data) {
      setMeta(res.data);
    }
    setLoading(false);
  };

  useEffect(() => {
    if (status?.entitled) loadMeta();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [status?.entitled]);

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

  const startEkyc = () =>
    runBusy('Sending OTP…', async () => {
      const geo = await getBrowserGeo();
      if (geo.status !== 'granted') {
        showError('Location permission is required for Fingpay eKYC.');
        return;
      }
      if (!String(deviceImei || '').trim()) {
        showError(
          'Phone/tablet IMEI is required (Fingpay deviceIMEI header). Save it under AEPS → Device — use the 15-digit IMEI from your phone settings, not the Mantra scanner serial.',
          'Device IMEI required'
        );
        return;
      }
      const aadhaar = String(ekycAadhaar || '').replace(/\s/g, '');
      if (!hasStoredAadhaar && !/^\d{12}$/.test(aadhaar)) {
        showError(
          maskedHint
            ? `Enter the full 12-digit Aadhaar once for eKYC (onboarded as ${maskedHint}). It will be stored securely for future eKYC steps.`
            : 'Enter the full 12-digit Aadhaar to start eKYC.',
          'Aadhaar required'
        );
        return;
      }

      const res = await aepsAPI.ekycStart({
        latitude: geo.latitude,
        longitude: geo.longitude,
        mobileNumber: mobile,
        ...(aadhaar ? { aadhaarNumber: aadhaar } : {}),
        panNumber: String(pan).trim().toUpperCase(),
        device_imei: deviceImei,
        matmSerialNumber: scannerSerial,
      });
      if (res.success) {
        showSuccess('OTP sent to the registered mobile number.', { title: 'OTP sent' });
        await refreshStatus?.();
        await loadMeta();
      } else {
        showError(res.message || 'eKYC send OTP failed.');
      }
    });

  const verifyOtp = () =>
    runBusy('Verifying OTP…', async () => {
      if (!otp.trim()) {
        showError('Enter the 6-digit OTP.');
        return;
      }
      const res = await aepsAPI.ekycOtp(otp);
      if (res.success) {
        showSuccess('OTP verified. Capture your fingerprint next.', { title: 'OTP verified' });
      } else {
        showError(res.message || 'OTP verification failed.');
      }
    });

  const resendOtp = () =>
    runBusy('Resending OTP…', async () => {
      const res = await aepsAPI.ekycResend();
      if (res.success) {
        showSuccess('OTP resent to your mobile.', { title: 'OTP resent' });
      } else {
        showError(res.message || 'Could not resend OTP.');
      }
    });

  const checkEkycStatus = () =>
    runBusy('Checking status…', async () => {
      const res = await aepsAPI.ekycStatus('EKYC');
      if (res.success) {
        showInfo(
          res.message || res.data?.message || JSON.stringify(res.data?.status || res.data || {}).slice(0, 300),
          'eKYC status'
        );
        await refreshStatus?.();
      } else {
        showError(res.message || 'Status check failed.');
      }
    });

  const biometric = () =>
    runBusy('Waiting for fingerprint…', async () => {
      const geo = await getBrowserGeo();
      if (geo.status !== 'granted') {
        showError('Location permission is required for Fingpay eKYC biometric.');
        return;
      }
      const cap = await captureMantraFingerprint({ purpose: 'ekyc' });
      if (!cap.success) {
        showError(cap.message || 'Fingerprint capture failed.');
        return;
      }
      const res = await aepsAPI.ekycBiometric({
        latitude: geo.latitude,
        longitude: geo.longitude,
        captureResponse: cap.captureResponse,
        ...(String(ekycAadhaar || '').replace(/\s/g, '').length === 12
          ? { aadhaarNumber: String(ekycAadhaar).replace(/\s/g, '') }
          : {}),
      });
      if (res.success) {
        await refreshStatus?.();
        if (res.data?.needs_bank_ekyc) {
          showInfo(
            res.data?.message ||
              'Primary eKYC done. Send OTP again for Bank eKYC, then capture fingerprint.',
            'Bank eKYC required'
          );
        } else {
          showSuccess(res.data?.message || 'eKYC completed. Your merchant is now active.', {
            title: 'eKYC complete',
            onCloseNavigate: () => navigate('/aeps'),
          });
        }
      } else {
        showError(res.message || 'Biometric eKYC failed.');
      }
    });

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
        <h2 className="text-xl font-bold text-slate-900 dark:text-slate-100">Access required</h2>
        <p className="mt-2 text-slate-600 dark:text-slate-400">Ask Admin to enable AEPS for your account.</p>
      </div>
    );
  }

  if (loading) {
    return (
      <div className="rounded-2xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900 p-10 text-center text-sm text-slate-500 dark:text-slate-400 shadow-sm">
        Loading eKYC…
      </div>
    );
  }

  if (stage === 'active') {
    return (
      <SetupPageShell>
        {FeedbackPortal}
        <SetupHeader
          title="eKYC complete"
          subtitle="Your merchant is active. Complete daily 2FA before trading."
          merchantLoginId={meta?.merchant_login_id || status?.merchant?.merchant_login_id}
          stage={stage}
          activeStepId="ready"
          steps={SETUP_STEPS}
        />
        <Section title="You're ready">
          <p className="text-sm text-emerald-700 dark:text-emerald-300">eKYC and merchant activation are complete.</p>
          <div className="mt-4 flex flex-wrap gap-2">
            <Link to="/aeps/2fa" className="rounded-xl bg-blue-600 px-4 py-2.5 text-sm font-semibold text-white hover:bg-blue-700">
              Daily 2FA
            </Link>
            <Link to="/aeps/withdraw" className="rounded-xl border border-slate-200 dark:border-slate-700 px-4 py-2.5 text-sm font-semibold text-slate-800 dark:text-slate-200 hover:bg-slate-50 dark:hover:bg-slate-800">
              Start trading
            </Link>
          </div>
        </Section>
      </SetupPageShell>
    );
  }

  return (
    <SetupPageShell>
      {FeedbackPortal}
      <AepsBusyOverlay show={busy} message={busyLabel} />

      <SetupHeader
        title="eKYC verification"
        subtitle="OTP + fingerprint. Identity details are taken from onboarding — no re-entry unless missing."
        merchantLoginId={meta?.merchant_login_id || status?.merchant?.merchant_login_id}
        stage={stage}
        activeStepId={activeStep}
        steps={SETUP_STEPS}
      />

      {inline.text ? <InlineAlert type={inline.type} text={inline.text} /> : null}

      {!status?.merchant?.device_ready || !deviceImei ? (
        <InlineAlert type="info" text="Save your phone/tablet IMEI (15 digits) under Device — this is sent as the Fingpay deviceIMEI header (not the Mantra scanner serial).">
          <Link to="/aeps/device" className="mt-2 inline-block text-sm font-semibold text-blue-700 dark:text-blue-300 underline">
            Go to Device setup →
          </Link>
        </InlineAlert>
      ) : null}

      <Section title="Step 1 — Identity for eKYC">
        <div className="grid gap-4 sm:grid-cols-2">
          <Field label="Mobile (from onboarding)" hint="OTP will be sent here">
            <input className={inputCls()} value={mobile} readOnly disabled />
          </Field>
          <Field label="PAN (from onboarding)">
            <input className={inputCls('uppercase')} value={pan} readOnly disabled />
          </Field>
          {hasStoredAadhaar ? (
            <Field label="Aadhaar" className="sm:col-span-2" hint="Using Aadhaar stored securely from onboarding">
              <input className={inputCls()} value={maskedHint || 'On file'} readOnly disabled />
            </Field>
          ) : (
            <Field
              label="Aadhaar number"
              required
              className="sm:col-span-2"
              hint={
                maskedHint
                  ? `Onboarded as ${maskedHint} — enter full 12 digits once (stored encrypted for eKYC only).`
                  : 'Enter full 12-digit Aadhaar for this eKYC session.'
              }
            >
              <input
                className={inputCls()}
                value={ekycAadhaar}
                onChange={(e) => setEkycAadhaar(e.target.value.replace(/\D/g, '').slice(0, 12))}
                placeholder="Enter 12-digit Aadhaar"
                inputMode="numeric"
                autoComplete="off"
              />
            </Field>
          )}
          <Field
            label="Device IMEI (phone/tablet)"
            className="sm:col-span-2"
            hint="Fingpay deviceIMEI header — e.g. 352801082418919 from phone settings"
          >
            <input
              className={inputCls('font-mono')}
              value={deviceImei || 'Not saved — register under Device'}
              readOnly
              disabled
            />
          </Field>
          {scannerSerial ? (
            <Field label="Mantra scanner serial" className="sm:col-span-2" hint="Used locally for fingerprint capture">
              <input className={inputCls('font-mono')} value={scannerSerial} readOnly disabled />
            </Field>
          ) : null}
        </div>
      </Section>

      <Section title="Step 2 — OTP & biometric">
        <div className="flex flex-wrap items-end gap-3">
          <Btn onClick={startEkyc} disabled={busy}>
            {busy && busyLabel.includes('Sending') ? 'Sending…' : 'Send OTP'}
          </Btn>
          <Btn onClick={resendOtp} disabled={busy}>
            Resend OTP
          </Btn>
          <Field label="OTP">
            <input
              className={inputCls('w-36')}
              value={otp}
              onChange={(e) => setOtp(e.target.value.replace(/\D/g, '').slice(0, 6))}
              placeholder="6-digit OTP"
              inputMode="numeric"
            />
          </Field>
          <Btn onClick={verifyOtp} disabled={busy || !otp}>
            Verify OTP
          </Btn>
          <Btn onClick={biometric} disabled={busy} primary>
            Capture fingerprint
          </Btn>
          <Btn onClick={checkEkycStatus} disabled={busy}>
            Check status
          </Btn>
        </div>
      </Section>
    </SetupPageShell>
  );
}
