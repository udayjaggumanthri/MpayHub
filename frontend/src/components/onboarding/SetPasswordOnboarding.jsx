import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { authAPI } from '../../services/api';
import { useAuth } from '../../context/AuthContext';
import { getPostLoginPath } from '../../utils/onboardingPaths';
import { FaLock, FaEnvelope, FaPhone, FaCircleCheck } from 'react-icons/fa6';
import Button from '../common/Button';
import Card from '../common/Card';

const SetPasswordOnboarding = () => {
  const navigate = useNavigate();
  const { refreshUser } = useAuth();
  const [step, setStep] = useState(1);
  const [channel, setChannel] = useState('sms');
  const [otp, setOtp] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const handleSendOtp = async (selectedChannel) => {
    setChannel(selectedChannel);
    setError('');
    setLoading(true);
    try {
      const result = await authAPI.sendForcedPasswordResetOtp(selectedChannel);
      if (result.success) {
        setStep(2);
      } else {
        setError(result.message || 'Failed to send OTP. Please try again.');
      }
    } catch {
      setError('An error occurred. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  const handleOtpNext = (e) => {
    e.preventDefault();
    setError('');
    if (!otp || otp.length !== 6) {
      setError('Please enter a valid 6-digit OTP');
      return;
    }
    setStep(3);
  };

  const handleComplete = async (e) => {
    e.preventDefault();
    setError('');

    if (!newPassword || newPassword.length < 8) {
      setError('Password must be at least 8 characters');
      return;
    }
    if (newPassword !== confirmPassword) {
      setError('Passwords do not match');
      return;
    }

    setLoading(true);
    try {
      const result = await authAPI.completeForcedPasswordReset({
        otp,
        new_password: newPassword,
        confirm_password: confirmPassword,
      });
      if (result.success) {
        const u = await refreshUser();
        navigate(getPostLoginPath(u), { replace: true });
      } else {
        setError(result.message || 'Failed to update password. Please try again.');
      }
    } catch {
      setError('An error occurred. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="max-w-lg mx-auto py-8 px-4">
      <Card className="p-6 sm:p-8">
        <div className="flex items-center gap-3 mb-6">
          <div className="h-12 w-12 rounded-xl bg-indigo-100 dark:bg-indigo-900/40 flex items-center justify-center">
            <FaLock className="text-indigo-600 dark:text-indigo-400" size={22} />
          </div>
          <div>
            <h1 className="text-xl font-bold text-slate-900 dark:text-slate-100">Set your password</h1>
            <p className="text-sm text-slate-600 dark:text-slate-400">
              {step === 1 && 'Required on first login for your security'}
              {step === 2 && 'Enter the verification code we sent you'}
              {step === 3 && 'Choose a new password for your account'}
            </p>
          </div>
        </div>

        {error && (
          <p className="mb-4 text-sm text-red-600 dark:text-red-400 bg-red-50 dark:bg-red-950/40 border border-red-100 dark:border-red-900 rounded-lg px-3 py-2">
            {error}
          </p>
        )}

        {step === 1 && (
          <div className="space-y-4">
            <p className="text-sm text-slate-600 dark:text-slate-400">
              Your account was created with a temporary password. Before continuing, verify your
              identity with a one-time code and choose a new password.
            </p>
            <Button
              type="button"
              variant="primary"
              className="w-full justify-center"
              icon={FaPhone}
              loading={loading && channel === 'sms'}
              onClick={() => handleSendOtp('sms')}
            >
              Send OTP via SMS
            </Button>
            <Button
              type="button"
              variant="outline"
              className="w-full justify-center"
              icon={FaEnvelope}
              loading={loading && channel === 'email'}
              onClick={() => handleSendOtp('email')}
            >
              Send OTP via Email
            </Button>
          </div>
        )}

        {step === 2 && (
          <form onSubmit={handleOtpNext} className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-1">6-digit OTP</label>
              <input
                type="text"
                inputMode="numeric"
                maxLength={6}
                value={otp}
                onChange={(e) => setOtp(e.target.value.replace(/\D/g, '').slice(0, 6))}
                className="w-full rounded-xl border border-slate-200 dark:border-slate-700 px-4 py-3 text-center font-mono text-lg tracking-widest"
                placeholder="000000"
                autoComplete="one-time-code"
              />
            </div>
            <Button type="submit" variant="primary" className="w-full justify-center">
              Continue
            </Button>
            <button
              type="button"
              className="text-sm text-indigo-600 dark:text-indigo-400 hover:underline w-full text-center"
              onClick={() => setStep(1)}
            >
              Resend code
            </button>
          </form>
        )}

        {step === 3 && (
          <form onSubmit={handleComplete} className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-1">New password</label>
              <input
                type="password"
                value={newPassword}
                onChange={(e) => setNewPassword(e.target.value)}
                className="w-full rounded-xl border border-slate-200 dark:border-slate-700 px-4 py-3"
                minLength={8}
                autoComplete="new-password"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-1">Confirm password</label>
              <input
                type="password"
                value={confirmPassword}
                onChange={(e) => setConfirmPassword(e.target.value)}
                className="w-full rounded-xl border border-slate-200 dark:border-slate-700 px-4 py-3"
                minLength={8}
                autoComplete="new-password"
              />
            </div>
            <Button
              type="submit"
              variant="primary"
              className="w-full justify-center"
              icon={FaCircleCheck}
              loading={loading}
            >
              Save password
            </Button>
          </form>
        )}
      </Card>
    </div>
  );
};

export default SetPasswordOnboarding;
