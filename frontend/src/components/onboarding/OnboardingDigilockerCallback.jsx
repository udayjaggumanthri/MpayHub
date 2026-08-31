import React, { useEffect, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../../context/AuthContext';
import { authAPI } from '../../services/api';
import Card from '../common/Card';
import Button from '../common/Button';
import KycDetailsCard from './KycDetailsCard';
import KycProfileSyncModal from './KycProfileSyncModal';

const POLL_INTERVAL_MS = 3000;
const MAX_POLLS = 40;

/**
 * Return URL after Cashfree DigiLocker redirect. Polls status then completes KYC.
 */
const OnboardingDigilockerCallback = () => {
  const navigate = useNavigate();
  const { refreshUser } = useAuth();
  const [status, setStatus] = useState('PENDING');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(true);
  const [kycDetails, setKycDetails] = useState(null);
  const [profileSyncOffer, setProfileSyncOffer] = useState(null);
  const [profileSyncOpen, setProfileSyncOpen] = useState(false);
  const [profileSyncLoading, setProfileSyncLoading] = useState(false);
  const pollCount = useRef(0);
  const completed = useRef(false);

  const verificationId =
    sessionStorage.getItem('digilocker_verification_id') ||
    new URLSearchParams(window.location.search).get('verification_id') ||
    '';

  useEffect(() => {
    if (!verificationId) {
      setError('Missing DigiLocker session. Start verification again from KYC.');
      setLoading(false);
      return;
    }

    let cancelled = false;
    let timer = null;

    const tryComplete = async () => {
      const completeResult = await authAPI.completeDigilockerKyc(verificationId);
      if (completeResult.success) {
        completed.current = true;
        sessionStorage.removeItem('digilocker_verification_id');
        setKycDetails(completeResult.data?.kyc_details || null);
        setLoading(false);
        await refreshUser();
        const offer = completeResult.data?.profile_sync || completeResult.data?.kyc_details?.profile_sync;
        if (offer?.status === 'pending_confirmation' && offer?.sync_token) {
          setProfileSyncOffer(offer);
          setProfileSyncOpen(true);
        } else {
          setTimeout(() => navigate('/onboarding/kyc', { replace: true }), 2500);
        }
        return true;
      }
      return false;
    };

    const poll = async () => {
      if (cancelled || completed.current) return;

      const result = await authAPI.getDigilockerStatus(verificationId);
      if (!result.success) {
        if (pollCount.current >= MAX_POLLS) {
          setError(result.message || 'DigiLocker verification timed out. Try again.');
          setLoading(false);
        }
        return;
      }

      const nextStatus = (result.data?.status || 'PENDING').toUpperCase();
      setStatus(nextStatus);

      if (nextStatus === 'AUTHENTICATED' || nextStatus === 'SUCCESS') {
        const done = await tryComplete();
        if (!done) {
          setError('Could not finalize Aadhaar verification. Try again.');
          setLoading(false);
        }
        return;
      }

      if (['FAILED', 'EXPIRED', 'CANCELLED'].includes(nextStatus)) {
        setError(`DigiLocker verification ${nextStatus.toLowerCase()}. Please try again.`);
        setLoading(false);
        return;
      }

      pollCount.current += 1;
      if (pollCount.current >= MAX_POLLS) {
        setError('Verification is taking longer than expected. Check back shortly or retry.');
        setLoading(false);
      }
    };

    poll();
    timer = setInterval(poll, POLL_INTERVAL_MS);

    return () => {
      cancelled = true;
      if (timer) clearInterval(timer);
    };
  }, [verificationId, navigate, refreshUser]);

  const handleProfileSyncConfirm = async () => {
    if (!profileSyncOffer?.sync_token) return;
    setProfileSyncLoading(true);
    try {
      const res = await authAPI.confirmProfileSync(profileSyncOffer.sync_token);
      if (res.success) {
        await refreshUser();
        setProfileSyncOpen(false);
        setProfileSyncOffer(null);
        navigate('/onboarding/kyc', { replace: true });
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
      navigate('/onboarding/kyc', { replace: true });
      return { warning: res.message || 'Profile was not updated.' };
    } finally {
      setProfileSyncLoading(false);
    }
    return { warning: '' };
  };

  return (
    <div className="max-w-lg mx-auto px-4 py-8">
      <Card
        title="DigiLocker verification"
        subtitle="Completing your Aadhaar verification…"
        padding="lg"
      >
        {kycDetails ? (
          <div className="space-y-4">
            <KycDetailsCard details={kycDetails} title="Aadhaar verified — details from DigiLocker" />
            <p className="text-sm text-gray-600 dark:text-slate-400 text-center">
              Documents verified. Waiting for Admin approval before account activation…
            </p>
          </div>
        ) : null}

        {loading && !error && !kycDetails ? (
          <div className="text-center space-y-4 py-6">
            <div className="animate-spin rounded-full h-10 w-10 border-b-2 border-blue-600 mx-auto" />
            <p className="text-sm text-gray-600 dark:text-slate-400">Status: {status}</p>
            <p className="text-xs text-gray-500 dark:text-slate-400">Do not close this window.</p>
          </div>
        ) : null}

        {error ? (
          <div className="space-y-4">
            <p className="text-sm text-red-600 dark:text-red-400">{error}</p>
            <Button
              type="button"
              variant="primary"
              fullWidth
              onClick={() => navigate('/onboarding/kyc', { replace: true })}
            >
              Back to KYC
            </Button>
          </div>
        ) : null}
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

export default OnboardingDigilockerCallback;
