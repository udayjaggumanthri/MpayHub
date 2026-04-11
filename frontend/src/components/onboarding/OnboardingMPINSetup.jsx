import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../../context/AuthContext';
import { authAPI } from '../../services/api';
import { validateMPIN } from '../../utils/validators';
import Card from '../common/Card';
import Button from '../common/Button';

const OnboardingMPINSetup = () => {
  const navigate = useNavigate();
  const { user, refreshUser, markMpinSessionVerified } = useAuth();
  const [mpin, setMpin] = useState('');
  const [confirm, setConfirm] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!user?.onboarding) return;
    if (!user.onboarding.kyc_complete) {
      navigate('/onboarding/kyc', { replace: true });
      return;
    }
    if (user.onboarding.mpin_set) {
      navigate('/mpin-verification', { replace: true });
    }
  }, [user, navigate]);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    const v = validateMPIN(mpin);
    if (!v.valid) {
      setError(v.message);
      return;
    }
    if (mpin !== confirm) {
      setError('MPIN and confirmation do not match.');
      return;
    }
    setLoading(true);
    try {
      const result = await authAPI.setupOnboardingMPIN(mpin, confirm);
      if (result.success) {
        await refreshUser();
        markMpinSessionVerified();
        navigate('/dashboard', { replace: true });
      } else {
        setError(result.message || 'Could not set MPIN.');
      }
    } catch {
      setError('Something went wrong. Try again.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="max-w-md mx-auto px-4 py-8">
      <Card
        title="Set your MPIN"
        subtitle="Choose a 6-digit MPIN for transactions and session verification. You will use it after each login."
        padding="lg"
      >
        <form className="space-y-5" onSubmit={handleSubmit}>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">MPIN</label>
            <input
              type="password"
              inputMode="numeric"
              value={mpin}
              onChange={(e) => setMpin(e.target.value.replace(/\D/g, '').slice(0, 6))}
              className="w-full px-4 py-3 border border-gray-300 rounded-lg text-center text-xl tracking-widest"
              maxLength={6}
              autoComplete="new-password"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Confirm MPIN</label>
            <input
              type="password"
              inputMode="numeric"
              value={confirm}
              onChange={(e) => setConfirm(e.target.value.replace(/\D/g, '').slice(0, 6))}
              className="w-full px-4 py-3 border border-gray-300 rounded-lg text-center text-xl tracking-widest"
              maxLength={6}
              autoComplete="new-password"
            />
          </div>
          {error ? <p className="text-sm text-red-600">{error}</p> : null}
          <Button type="submit" variant="primary" size="lg" fullWidth loading={loading}>
            Save MPIN & continue
          </Button>
        </form>
      </Card>
    </div>
  );
};

export default OnboardingMPINSetup;
