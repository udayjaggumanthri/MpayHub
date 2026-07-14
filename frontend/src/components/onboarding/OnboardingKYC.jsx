import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { FaIdCard, FaLock, FaClock } from 'react-icons/fa6';
import { useAuth } from '../../context/AuthContext';
import { authAPI } from '../../services/api';
import { validatePAN, validateAadhaar } from '../../utils/validators';
import Card from '../common/Card';
import Button from '../common/Button';
import KycDetailsCard from './KycDetailsCard';
import KycProfileSyncModal from './KycProfileSyncModal';

const inputClass =
  'w-full px-4 py-3 border border-slate-200 rounded-xl focus:border-indigo-300 focus:ring-2 focus:ring-indigo-500/20 outline-none transition';

/**
 * Step 1: PAN + name. Step 2: optional Aadhaar pre-check + DigiLocker redirect.
 */
const OnboardingKYC = () => {
  const navigate = useNavigate();
  const { user, refreshUser } = useAuth();
  const [step, setStep] = useState(1);
  const [pan, setPan] = useState('');
  const [panName, setPanName] = useState('');
  const [aadhaar, setAadhaar] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const [bootLoading, setBootLoading] = useState(true);
  const [panDetails, setPanDetails] = useState(null);
  const [profileSyncOffer, setProfileSyncOffer] = useState(null);
  const [profileSyncOpen, setProfileSyncOpen] = useState(false);
  const [profileSyncLoading, setProfileSyncLoading] = useState(false);

  useEffect(() => {
    if (!user?.onboarding) {
      setBootLoading(false);
      return;
    }
    if (user.onboarding.kyc_complete) {
      navigate('/onboarding/mpin-setup', { replace: true });
      return;
    }
    // Provider documents done — stay on this page for Admin approval / rejection messaging.
    if (user.onboarding.awaiting_admin_approval || user.onboarding.kyc_rejected) {
      setBootLoading(false);
      return;
    }
    if (user.onboarding.pan_verified) {
      setStep(2);
      if (user.kyc_verification?.pan && !panDetails) {
        const kv = user.kyc_verification.pan;
        setPanDetails({
          pan: kv.pan,
          name: kv.name,
          date_of_birth: kv.date_of_birth,
          pan_type: kv.pan_type,
        });
      }
    }
    setBootLoading(false);
  }, [user, navigate, panDetails]);

  useEffect(() => {
    if (panName.trim()) return;
    const fromProfile = `${user?.first_name || ''} ${user?.last_name || ''}`.trim();
    if (fromProfile) setPanName(fromProfile);
  }, [user, panName]);

  const openProfileSyncIfNeeded = (payload) => {
    const offer = payload?.profile_sync || payload?.kyc_details?.profile_sync;
    if (offer?.status === 'pending_confirmation' && offer?.sync_token) {
      setProfileSyncOffer(offer);
      setProfileSyncOpen(true);
      return true;
    }
    return false;
  };

  const handleProfileSyncConfirm = async () => {
    if (!profileSyncOffer?.sync_token) return;
    setProfileSyncLoading(true);
    try {
      const res = await authAPI.confirmProfileSync(profileSyncOffer.sync_token);
      if (res.success) {
        await refreshUser();
        setProfileSyncOpen(false);
        setProfileSyncOffer(null);
      }
    } finally {
      setProfileSyncLoading(false);
    }
  };

  const handleProfileSyncDecline = async () => {
    if (!profileSyncOffer?.sync_token) return { warning: '' };
    setProfileSyncLoading(true);
    try {
      const res = await authAPI.declineProfileSync(profileSyncOffer.sync_token);
      setProfileSyncOpen(false);
      setProfileSyncOffer(null);
      return { warning: res.message || 'Profile was not updated.' };
    } finally {
      setProfileSyncLoading(false);
    }
    return { warning: '' };
  };

  const handleVerifyPan = async (e) => {
    e.preventDefault();
    setError('');
    const p = pan.toUpperCase().trim();
    if (!validatePAN(p).valid) {
      setError('Enter a valid PAN.');
      return;
    }
    const name = panName.trim();
    if (!name) {
      setError('Enter your name as per PAN.');
      return;
    }
    setLoading(true);
    try {
      const result = await authAPI.verifyOnboardingPan(p, name);
      if (result.success) {
        setPanDetails(result.data?.kyc_details || null);
        await refreshUser();
        openProfileSyncIfNeeded(result.data);
        setStep(2);
      } else {
        setError(result.message || 'PAN verification failed.');
      }
    } catch {
      setError('Something went wrong. Try again.');
    } finally {
      setLoading(false);
    }
  };

  const handleDigilocker = async () => {
    setError('');
    const a = aadhaar.replace(/\D/g, '').slice(0, 12);
    if (a && !validateAadhaar(a).valid) {
      setError('Enter a valid 12-digit Aadhaar or leave blank.');
      return;
    }
    setLoading(true);
    try {
      const result = await authAPI.initOnboardingDigilocker(a || undefined);
      if (result.success && result.data?.url) {
        const vid = result.data.verification_id || '';
        if (vid) {
          sessionStorage.setItem('digilocker_verification_id', vid);
        }
        window.location.href = result.data.url;
        return;
      }
      setError(result.message || 'Could not start DigiLocker verification.');
    } catch {
      setError('Something went wrong. Try again.');
    } finally {
      setLoading(false);
    }
  };

  if (bootLoading) {
    return (
      <div className="max-w-lg mx-auto px-4 py-8">
        <Card title="Complete KYC" subtitle="Loading your verification status…" padding="lg">
          <div className="flex justify-center py-8">
            <div className="h-8 w-8 animate-spin rounded-full border-2 border-indigo-600 border-t-transparent" />
          </div>
        </Card>
      </div>
    );
  }

  if (user?.onboarding?.awaiting_admin_approval) {
    return (
      <div className="max-w-lg mx-auto px-4 py-8">
        <Card
          title="KYC under review"
          subtitle="Your documents were verified. An administrator must approve your KYC before your account becomes active."
          padding="lg"
        >
          <div className="rounded-xl border border-amber-200 bg-amber-50/70 px-4 py-4 space-y-3">
            <div className="flex items-start gap-3">
              <FaClock className="text-amber-600 shrink-0 mt-0.5" size={20} />
              <div className="text-sm text-amber-950 space-y-2">
                <p className="font-semibold">Awaiting Admin approval</p>
                <p>
                  PAN and Aadhaar checks are complete. You will be able to set your MPIN and use
                  services once an administrator approves your KYC.
                </p>
                <ul className="list-disc list-inside space-y-1 text-amber-900/90">
                  <li>PAN verified</li>
                  <li>Aadhaar verified</li>
                  <li>Manual Admin review pending</li>
                </ul>
              </div>
            </div>
            <Button type="button" variant="outline" size="md" fullWidth onClick={() => refreshUser()}>
              Refresh status
            </Button>
          </div>
        </Card>
      </div>
    );
  }

  if (user?.onboarding?.kyc_rejected) {
    return (
      <div className="max-w-lg mx-auto px-4 py-8">
        <Card
          title="KYC needs attention"
          subtitle="An administrator reviewed your KYC and could not approve it yet."
          padding="lg"
        >
          <div className="rounded-xl border border-red-200 bg-red-50/70 px-4 py-4 space-y-3">
            <p className="text-sm text-red-900">
              Please contact your administrator or support for next steps. Your account will remain
              inactive until KYC is approved.
            </p>
            <Button type="button" variant="outline" size="md" fullWidth onClick={() => refreshUser()}>
              Refresh status
            </Button>
          </div>
        </Card>
      </div>
    );
  }

  return (
    <div className="max-w-lg mx-auto px-4 py-8">
      <Card
        title="Complete KYC"
        subtitle={
          step === 1
            ? 'Verify your PAN with Cashfree before linking Aadhaar via DigiLocker.'
            : 'Link your Aadhaar through the secure government DigiLocker portal.'
        }
        padding="lg"
      >
        <div className="mb-6 flex items-center gap-3" aria-label={`Step ${step} of 2`}>
          {[
            { n: 1, label: 'PAN' },
            { n: 2, label: 'Aadhaar' },
          ].map((s) => (
            <div key={s.n} className="flex-1">
              <div className="flex items-center gap-2 mb-1">
                <span
                  className={`h-7 w-7 rounded-full flex items-center justify-center text-xs font-bold ${
                    step >= s.n ? 'bg-indigo-600 text-white' : 'bg-slate-200 text-slate-600'
                  }`}
                >
                  {s.n}
                </span>
                <span className={`text-xs font-semibold ${step >= s.n ? 'text-indigo-700' : 'text-slate-500'}`}>
                  {s.label}
                </span>
              </div>
              <div className={`h-1.5 rounded-full ${step >= s.n ? 'bg-indigo-600' : 'bg-slate-200'}`} />
            </div>
          ))}
        </div>

        <div aria-live="polite">
          {step === 1 && (
            <form className="space-y-5" onSubmit={handleVerifyPan}>
              <div className="flex items-center gap-3 rounded-xl border border-indigo-100 bg-indigo-50/50 px-4 py-3">
                <FaIdCard className="text-indigo-600 shrink-0" size={20} />
                <p className="text-sm text-indigo-900">
                  Enter your PAN and name exactly as printed on your PAN card.
                </p>
              </div>
              <div>
                <label htmlFor="onboarding-pan" className="block text-sm font-medium text-slate-700 mb-1">
                  PAN
                </label>
                <input
                  id="onboarding-pan"
                  value={pan}
                  onChange={(e) => setPan(e.target.value.toUpperCase().replace(/[^A-Z0-9]/g, '').slice(0, 10))}
                  className={`${inputClass} uppercase font-mono`}
                  placeholder="ABCDE1234F"
                  maxLength={10}
                  autoComplete="off"
                />
              </div>
              <div>
                <label htmlFor="onboarding-pan-name" className="block text-sm font-medium text-slate-700 mb-1">
                  Name as per PAN
                </label>
                <input
                  id="onboarding-pan-name"
                  value={panName}
                  onChange={(e) => setPanName(e.target.value)}
                  className={inputClass}
                  placeholder="Full name on PAN card"
                  maxLength={200}
                />
              </div>
              {error ? (
                <p role="alert" className="text-sm text-red-700 bg-red-50 border border-red-100 rounded-lg px-3 py-2">
                  {error}
                </p>
              ) : null}
              <Button type="submit" variant="primary" size="lg" fullWidth loading={loading}>
                Verify PAN
              </Button>
            </form>
          )}

          {step === 2 && (
            <div className="space-y-5">
              <KycDetailsCard details={panDetails} title="PAN verified" />
              <button
                type="button"
                onClick={() => setStep(1)}
                className="text-sm font-medium text-indigo-700 hover:text-indigo-900"
              >
                Change PAN details
              </button>
              <div className="rounded-xl border border-blue-100 bg-blue-50/60 px-4 py-3 space-y-2">
                <div className="flex items-center gap-2 text-blue-900 font-semibold text-sm">
                  <FaLock size={14} />
                  Secure DigiLocker verification
                </div>
                <ul className="text-sm text-blue-900/90 list-disc list-inside space-y-1">
                  <li>You will be redirected to the official DigiLocker portal.</li>
                  <li>Only Aadhaar details you consent to share are retrieved.</li>
                  <li>Your Aadhaar number is never stored in full on our servers.</li>
                </ul>
              </div>
              <div>
                <label htmlFor="onboarding-aadhaar" className="block text-sm font-medium text-slate-700 mb-1">
                  Aadhaar number <span className="text-slate-400 font-normal">(optional pre-check)</span>
                </label>
                <input
                  id="onboarding-aadhaar"
                  value={aadhaar}
                  onChange={(e) => setAadhaar(e.target.value.replace(/\D/g, '').slice(0, 12))}
                  className={`${inputClass} font-mono`}
                  placeholder="12 digits — optional"
                  maxLength={12}
                  inputMode="numeric"
                />
              </div>
              {error ? (
                <p role="alert" className="text-sm text-red-700 bg-red-50 border border-red-100 rounded-lg px-3 py-2">
                  {error}
                </p>
              ) : null}
              <Button
                type="button"
                variant="primary"
                size="lg"
                fullWidth
                loading={loading}
                onClick={handleDigilocker}
              >
                Continue with DigiLocker
              </Button>
            </div>
          )}
        </div>
      </Card>

      <KycProfileSyncModal
        open={profileSyncOpen}
        profileSync={profileSyncOffer}
        loading={profileSyncLoading}
        onConfirm={handleProfileSyncConfirm}
        onDecline={handleProfileSyncDecline}
        onClose={() => !profileSyncLoading && setProfileSyncOpen(false)}
      />
    </div>
  );
};

export default OnboardingKYC;
