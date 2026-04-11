import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { authAPI } from '../../services/api';
import { validatePhone } from '../../utils/validators';
import { FaPhone, FaLock, FaCircleCheck, FaArrowLeft } from 'react-icons/fa6';

const LOGO_SRC = `${process.env.PUBLIC_URL || ''}/images/logo.svg`;

const ForgotPassword = () => {
  const navigate = useNavigate();
  const [step, setStep] = useState(1); // 1: Phone, 2: OTP, 3: New Password
  const [phone, setPhone] = useState('');
  const [otp, setOtp] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const [success, setSuccess] = useState(false);

  const handlePhoneSubmit = async (e) => {
    e.preventDefault();
    setError('');

    const phoneValidation = validatePhone(phone);
    if (!phoneValidation.valid) {
      setError(phoneValidation.message);
      return;
    }

    setLoading(true);
    try {
      const result = await authAPI.sendOTP(phone, 'password-reset');
      if (result.success) {
        setStep(2);
      } else {
        const errs = Array.isArray(result.errors) ? result.errors : [];
        setError(errs[0] || result.message || 'Failed to send OTP. Please try again.');
      }
    } catch (err) {
      setError('An error occurred. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  const handleOTPSubmit = async (e) => {
    e.preventDefault();
    setError('');

    if (!otp || otp.length !== 6) {
      setError('Please enter a valid 6-digit OTP');
      return;
    }

    setLoading(true);
    try {
      const result = await authAPI.verifyOTP(phone, otp, 'password-reset');
      if (result.success) {
        setStep(3);
      } else {
        const errs = Array.isArray(result.errors) ? result.errors : [];
        setError(errs[0] || result.message || 'Invalid or expired OTP.');
      }
    } catch (err) {
      setError('An error occurred. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  const handlePasswordReset = async (e) => {
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
      const result = await authAPI.resetPassword(
        phone,
        otp,
        newPassword,
        confirmPassword
      );
      if (result.success) {
        setSuccess(true);
        setTimeout(() => {
          navigate('/login');
        }, 3000);
      } else {
        const errs = Array.isArray(result.errors) ? result.errors : [];
        setError(errs[0] || result.message || 'Failed to reset password. Please try again.');
      }
    } catch (err) {
      setError('An error occurred. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  const stepTitle =
    step === 1 ? 'Forgot Password?' : step === 2 ? 'Verify OTP' : 'Set New Password';
  const stepSubtitle =
    step === 1
      ? 'Enter your phone number to receive OTP'
      : step === 2
        ? 'Enter the 6-digit OTP sent to your phone'
        : 'Create a new secure password';

  return (
    <div className="min-h-screen flex flex-col lg:flex-row">
      {/* Left Panel — matches Login branding (desktop lg+) */}
      <div className="hidden lg:flex lg:w-1/2 relative overflow-hidden">
        <div
          className="absolute inset-0"
          style={{
            backgroundImage:
              'linear-gradient(135deg, rgba(30, 58, 138, 0.95) 0%, rgba(67, 56, 202, 0.95) 50%, rgba(79, 70, 229, 0.95) 100%), url("data:image/svg+xml,%3Csvg width=\'60\' height=\'60\' viewBox=\'0 0 60 60\' xmlns=\'http://www.w3.org/2000/svg\'%3E%3Cg fill=\'none\' fill-rule=\'evenodd\'%3E%3Cg fill=\'%23ffffff\' fill-opacity=\'0.05\'%3E%3Cpath d=\'M36 34v-4h-2v4h-4v2h4v4h2v-4h2v-2h-4zm0 0v-2h2v2h-2z\'/%3E%3C/g%3E%3C/g%3E%3C/svg%3E")',
            backgroundSize: 'cover, 60px 60px',
            backgroundPosition: 'center, center',
          }}
        >
          <div className="absolute inset-0 bg-gradient-to-br from-blue-900/70 via-indigo-900/60 to-purple-900/70" />
        </div>

        <div className="absolute inset-0 opacity-5">
          <div className="absolute top-10 left-10 w-96 h-96 bg-cyan-300 rounded-full blur-3xl animate-pulse" />
          <div className="absolute bottom-10 right-10 w-80 h-80 bg-blue-400 rounded-full blur-3xl animate-pulse delay-1000" />
          <div className="absolute top-1/2 left-1/2 transform -translate-x-1/2 -translate-y-1/2 w-72 h-72 bg-indigo-400 rounded-full blur-3xl animate-pulse delay-500" />
        </div>

        <div className="relative z-10 flex flex-col justify-center items-center p-8 xl:p-12 w-full min-h-full">
          <div className="flex flex-col items-center justify-center space-y-6 w-full -mt-16 xl:-mt-20">
            <h1 className="text-white text-2xl xl:text-3xl font-semibold tracking-wide animate-fadeIn text-center">
              RESET PASSWORD
            </h1>

            <div className="flex items-center justify-center">
              <div className="relative w-48 h-48 xl:w-56 xl:h-56">
                <div className="absolute inset-0 border-4 border-cyan-300 rounded-full opacity-40 animate-spin-slow" />
                <div className="absolute inset-4 border-2 border-cyan-300 rounded-full opacity-60" />

                <div className="absolute inset-0 flex items-center justify-center">
                  <div
                    className="w-36 h-36 xl:w-44 xl:h-44 bg-white rounded-3xl flex items-center justify-center p-3 xl:p-3.5 overflow-hidden shadow-2xl ring-1 ring-black/5 ring-inset transform hover:scale-105 transition-transform duration-300"
                    aria-hidden
                  >
                    <img
                      src={LOGO_SRC}
                      alt="mPayhub"
                      className="w-full h-full object-contain object-center select-none scale-[1.08] xl:scale-[1.1] origin-center"
                      draggable={false}
                    />
                  </div>
                </div>
              </div>
            </div>
          </div>

          <div className="absolute bottom-8 xl:bottom-12 left-8 xl:left-12 right-8 xl:right-12 space-y-6">
            <div className="text-center">
              <p className="text-cyan-200 text-lg xl:text-xl font-medium tracking-normal">
                Secure password recovery — driven by trust, built for scale
              </p>
            </div>

            <div className="space-y-4">
              <p className="text-gray-300 text-xs xl:text-sm font-normal text-center">Links:</p>
              <div className="flex flex-wrap justify-center gap-3">
                <button
                  type="button"
                  className="px-4 py-2 bg-gray-800/50 hover:bg-gray-800/70 text-gray-300 hover:text-cyan-300 rounded-lg text-xs xl:text-sm font-normal transition-all duration-200 border border-gray-700/50 hover:border-cyan-400/50"
                >
                  Privacy Policy
                </button>
                <button
                  type="button"
                  className="px-4 py-2 bg-gray-800/50 hover:bg-gray-800/70 text-gray-300 hover:text-cyan-300 rounded-lg text-xs xl:text-sm font-normal transition-all duration-200 border border-gray-700/50 hover:border-cyan-400/50"
                >
                  Terms & Conditions
                </button>
                <button
                  type="button"
                  className="px-4 py-2 bg-gray-800/50 hover:bg-gray-800/70 text-gray-300 hover:text-cyan-300 rounded-lg text-xs xl:text-sm font-normal transition-all duration-200 border border-gray-700/50 hover:border-cyan-400/50"
                >
                  Refund & Cancellation
                </button>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Right Panel - Form */}
      <div className="flex-1 flex items-center justify-center bg-white p-6 sm:p-8 lg:p-12">
        <div className="w-full max-w-md">
          {/* Mobile — same visual system as Login (lg:hidden) */}
          <div className="lg:hidden mb-6 sm:mb-7 rounded-xl bg-slate-50/80 px-4 pt-4 pb-5 ring-1 ring-gray-100">
            <div className="flex flex-col items-center text-center gap-1.5 sm:gap-2">
              <p className="text-2xl font-bold uppercase tracking-[0.22em] text-blue-600/85 leading-tight">
                Reset password
              </p>
              <div className="relative flex w-full max-w-[min(94vw,24rem)] justify-center py-1">
                <img
                  src={LOGO_SRC}
                  alt="mPayhub"
                  className="h-auto w-full max-h-[12rem] sm:max-h-[14rem] object-contain object-center select-none drop-shadow-[0_6px_24px_rgba(30,58,138,0.18)] sm:drop-shadow-[0_8px_28px_rgba(30,58,138,0.2)]"
                  draggable={false}
                />
              </div>
              <h2 className="text-3xl sm:text-4xl font-bold text-gray-900 leading-tight">{stepTitle}</h2>
              <p className="text-gray-600 text-sm sm:text-base leading-snug max-w-xs">{stepSubtitle}</p>
            </div>
          </div>

          <div className="space-y-8">
            <div className="hidden lg:block">
              <h2 className="text-3xl sm:text-4xl font-bold text-gray-900 mb-2">{stepTitle}</h2>
              <p className="text-gray-600 text-base sm:text-lg">{stepSubtitle}</p>
            </div>

            {/* Success Message */}
            {success && (
              <div className="bg-green-50 border-l-4 border-green-500 text-green-700 p-4 rounded-lg flex items-start animate-fadeIn">
                <FaCircleCheck className="h-5 w-5 text-green-400 flex-shrink-0 mt-0.5" />
                <div className="ml-3">
                  <p className="font-semibold">Password reset successful!</p>
                  <p className="text-sm mt-1">Redirecting to login page...</p>
                </div>
              </div>
            )}

            {/* Error Message */}
            {error && !success && (
              <div className="bg-red-50 border-l-4 border-red-500 text-red-700 p-4 rounded-lg flex items-start animate-fadeIn">
                <div className="flex-shrink-0">
                  <svg className="h-5 w-5 text-red-400" viewBox="0 0 20 20" fill="currentColor">
                    <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z" clipRule="evenodd" />
                  </svg>
                </div>
                <p className="ml-3 text-sm font-medium">{error}</p>
              </div>
            )}

            {/* Step 1: Phone Number */}
            {step === 1 && (
              <form onSubmit={handlePhoneSubmit} className="space-y-6">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    Phone Number
                  </label>
                  <div className="relative">
                    <div className="absolute inset-y-0 left-0 pl-4 flex items-center pointer-events-none">
                      <FaPhone className="text-gray-400" size={20} />
                    </div>
                    <input
                      type="tel"
                      value={phone}
                      onChange={(e) => {
                        const value = e.target.value.replace(/\D/g, '');
                        if (value.length <= 10) setPhone(value);
                      }}
                      placeholder="Enter 10-digit phone number"
                      maxLength={10}
                      required
                      className="w-full pl-12 pr-4 py-3.5 border-2 border-gray-200 rounded-xl focus:border-blue-500 focus:ring-2 focus:ring-blue-200 transition-all duration-200 text-base bg-gray-50 focus:bg-white"
                    />
                  </div>
                </div>

                <div className="flex space-x-3">
                  <button
                    type="button"
                    onClick={() => navigate('/login')}
                    className="flex-1 px-4 py-3 border-2 border-gray-300 rounded-xl text-gray-700 font-medium hover:bg-gray-50 transition-colors flex items-center justify-center space-x-2"
                  >
                    <FaArrowLeft size={16} />
                    <span>Back to Login</span>
                  </button>
                  <button
                    type="submit"
                    disabled={loading || phone.length !== 10}
                    className="flex-1 bg-gradient-to-r from-blue-600 to-indigo-600 text-white font-bold py-3.5 px-6 rounded-xl hover:from-blue-700 hover:to-indigo-700 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2 transition-all duration-200 disabled:opacity-50 disabled:cursor-not-allowed"
                  >
                    {loading ? 'Sending OTP...' : 'Send OTP'}
                  </button>
                </div>
              </form>
            )}

            {/* Step 2: OTP Verification */}
            {step === 2 && (
              <form onSubmit={handleOTPSubmit} className="space-y-6">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    Enter OTP
                  </label>
                  <input
                    type="text"
                    value={otp}
                    onChange={(e) => {
                      const value = e.target.value.replace(/\D/g, '').slice(0, 6);
                      setOtp(value);
                    }}
                    placeholder="Enter 6-digit OTP"
                    maxLength={6}
                    required
                    className="w-full px-4 py-3.5 border-2 border-gray-200 rounded-xl focus:border-blue-500 focus:ring-2 focus:ring-blue-200 transition-all duration-200 text-base bg-gray-50 focus:bg-white text-center text-2xl font-bold tracking-widest"
                  />
                  <p className="mt-2 text-sm text-gray-500">
                    OTP sent to {phone.substring(0, 2)}****{phone.substring(6)}.
                  </p>
                </div>

                <div className="flex space-x-3">
                  <button
                    type="button"
                    onClick={() => setStep(1)}
                    className="flex-1 px-4 py-3 border-2 border-gray-300 rounded-xl text-gray-700 font-medium hover:bg-gray-50 transition-colors"
                  >
                    Back
                  </button>
                  <button
                    type="submit"
                    disabled={loading || otp.length !== 6}
                    className="flex-1 bg-gradient-to-r from-blue-600 to-indigo-600 text-white font-bold py-3.5 px-6 rounded-xl hover:from-blue-700 hover:to-indigo-700 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2 transition-all duration-200 disabled:opacity-50 disabled:cursor-not-allowed"
                  >
                    {loading ? 'Verifying...' : 'Verify OTP'}
                  </button>
                </div>
              </form>
            )}

            {/* Step 3: New Password */}
            {step === 3 && (
              <form onSubmit={handlePasswordReset} className="space-y-6">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    New Password
                  </label>
                  <div className="relative">
                    <div className="absolute inset-y-0 left-0 pl-4 flex items-center pointer-events-none">
                      <FaLock className="text-gray-400" size={20} />
                    </div>
                    <input
                      type="password"
                      value={newPassword}
                      onChange={(e) => setNewPassword(e.target.value)}
                      placeholder="Enter new password (min 8 characters)"
                      required
                      minLength={8}
                      className="w-full pl-12 pr-4 py-3.5 border-2 border-gray-200 rounded-xl focus:border-blue-500 focus:ring-2 focus:ring-blue-200 transition-all duration-200 text-base bg-gray-50 focus:bg-white"
                    />
                  </div>
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    Confirm New Password
                  </label>
                  <div className="relative">
                    <div className="absolute inset-y-0 left-0 pl-4 flex items-center pointer-events-none">
                      <FaLock className="text-gray-400" size={20} />
                    </div>
                    <input
                      type="password"
                      value={confirmPassword}
                      onChange={(e) => setConfirmPassword(e.target.value)}
                      placeholder="Re-enter new password"
                      required
                      minLength={8}
                      className="w-full pl-12 pr-4 py-3.5 border-2 border-gray-200 rounded-xl focus:border-blue-500 focus:ring-2 focus:ring-blue-200 transition-all duration-200 text-base bg-gray-50 focus:bg-white"
                    />
                  </div>
                </div>

                <div className="flex space-x-3">
                  <button
                    type="button"
                    onClick={() => setStep(2)}
                    className="flex-1 px-4 py-3 border-2 border-gray-300 rounded-xl text-gray-700 font-medium hover:bg-gray-50 transition-colors"
                  >
                    Back
                  </button>
                  <button
                    type="submit"
                    disabled={loading || !newPassword || !confirmPassword || newPassword !== confirmPassword}
                    className="flex-1 bg-gradient-to-r from-blue-600 to-indigo-600 text-white font-bold py-3.5 px-6 rounded-xl hover:from-blue-700 hover:to-indigo-700 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2 transition-all duration-200 disabled:opacity-50 disabled:cursor-not-allowed"
                  >
                    {loading ? 'Resetting...' : 'Reset Password'}
                  </button>
                </div>
              </form>
            )}

            {/* Back to Login Link */}
            <div className="text-center">
              <button
                type="button"
                onClick={() => navigate('/login')}
                className="text-sm font-medium text-blue-600 hover:text-blue-700 transition-colors flex items-center justify-center space-x-2"
              >
                <FaArrowLeft size={14} />
                <span>Back to Login</span>
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default ForgotPassword;
