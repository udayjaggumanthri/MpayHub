import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../../context/AuthContext';
import { authAPI } from '../../services/api';
import { validatePAN, validateAadhaar } from '../../utils/validators';
import Card from '../common/Card';
import Button from '../common/Button';

/**
 * Step 1: PAN + Verify. Step 2: Aadhaar + Send OTP + enter OTP (demo: 123456 if SMS unavailable).
 */
const OnboardingKYC = () => {
  const navigate = useNavigate();
  const { user, refreshUser } = useAuth();
  const [step, setStep] = useState(1);
  const [pan, setPan] = useState('');
  const [aadhaar, setAadhaar] = useState('');
  const [otp, setOtp] = useState('');
  const [otpHint, setOtpHint] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!user?.onboarding) return;
    if (user.onboarding.kyc_complete) {
      navigate('/onboarding/mpin-setup', { replace: true });
      return;
    }
    if (user.onboarding.pan_verified) {
      setStep(2);
    }
  }, [user, navigate]);

  const handleVerifyPan = async (e) => {
    e.preventDefault();
    setError('');
    const p = pan.toUpperCase().trim();
    if (!validatePAN(p).valid) {
      setError('Enter a valid PAN.');
      return;
    }
    setLoading(true);
    try {
      const result = await authAPI.verifyOnboardingPan(p);
      if (result.success) {
        await refreshUser();
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

  const handleSendAadhaarOtp = async () => {
    setError('');
    const a = aadhaar.replace(/\D/g, '').slice(0, 12);
    if (!validateAadhaar(a).valid) {
      setError('Enter a valid 12-digit Aadhaar.');
      return;
    }
    setLoading(true);
    setOtpHint('');
    try {
      const result = await authAPI.sendOnboardingAadhaarOtp(a);
      if (result.success) {
        await refreshUser();
        const hint = result.data?.demo_otp_hint || '';
        setOtpHint(
          hint || 'Check your mobile for OTP. Demo: you can enter 123456 if SMS is not configured.'
        );
      } else {
        setError(result.message || 'Could not send OTP.');
      }
    } catch {
      setError('Something went wrong. Try again.');
    } finally {
      setLoading(false);
    }
  };

  const handleVerifyAadhaarOtp = async (e) => {
    e.preventDefault();
    setError('');
    if (!otp || otp.length !== 6) {
      setError('Enter the 6-digit OTP.');
      return;
    }
    setLoading(true);
    try {
      const result = await authAPI.verifyOnboardingAadhaarOtp(otp);
      if (result.success) {
        await refreshUser();
        navigate('/onboarding/mpin-setup', { replace: true });
      } else {
        setError(result.message || 'Invalid OTP.');
      }
    } catch {
      setError('Something went wrong. Try again.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="max-w-lg mx-auto px-4 py-8">
      <Card
        title="Complete KYC"
        subtitle={
          step === 1
            ? 'Step 1 of 2 — Verify your PAN.'
            : 'Step 2 of 2 — Verify your Aadhaar with an OTP sent to your registered mobile number.'
        }
        padding="lg"
      >
        <div className="mb-6 flex gap-2">
          <span
            className={`flex-1 h-1.5 rounded-full ${step >= 1 ? 'bg-blue-600' : 'bg-gray-200'}`}
          />
          <span
            className={`flex-1 h-1.5 rounded-full ${step >= 2 ? 'bg-blue-600' : 'bg-gray-200'}`}
          />
        </div>

        {step === 1 && (
          <form className="space-y-5" onSubmit={handleVerifyPan}>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">PAN</label>
              <input
                value={pan}
                onChange={(e) => setPan(e.target.value.toUpperCase().replace(/[^A-Z0-9]/g, '').slice(0, 10))}
                className="w-full px-4 py-3 border border-gray-300 rounded-lg uppercase"
                placeholder="ABCDE1234F"
                maxLength={10}
              />
            </div>
            {error ? <p className="text-sm text-red-600">{error}</p> : null}
            <Button type="submit" variant="primary" size="lg" fullWidth loading={loading}>
              Verify PAN
            </Button>
          </form>
        )}

        {step === 2 && (
          <div className="space-y-5">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Aadhaar number</label>
              <input
                value={aadhaar}
                onChange={(e) => setAadhaar(e.target.value.replace(/\D/g, '').slice(0, 12))}
                className="w-full px-4 py-3 border border-gray-300 rounded-lg"
                placeholder="12 digits"
                maxLength={12}
              />
            </div>
            <Button
              type="button"
              variant="outline"
              size="lg"
              fullWidth
              loading={loading}
              onClick={handleSendAadhaarOtp}
            >
              Send OTP
            </Button>
            {otpHint ? (
              <p className="text-sm text-gray-600 bg-blue-50 border border-blue-100 rounded-lg p-3">
                {otpHint}
              </p>
            ) : null}

            <form className="space-y-4 pt-2 border-t border-gray-100" onSubmit={handleVerifyAadhaarOtp}>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">OTP</label>
                <input
                  value={otp}
                  onChange={(e) => setOtp(e.target.value.replace(/\D/g, '').slice(0, 6))}
                  className="w-full px-4 py-3 border border-gray-300 rounded-lg text-center text-xl tracking-widest"
                  placeholder="6 digits"
                  maxLength={6}
                  inputMode="numeric"
                />
              </div>
              {error ? <p className="text-sm text-red-600">{error}</p> : null}
              <Button type="submit" variant="primary" size="lg" fullWidth loading={loading}>
                Verify OTP &amp; complete KYC
              </Button>
            </form>
          </div>
        )}
      </Card>
    </div>
  );
};

export default OnboardingKYC;
