import React, { useState } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { useAuth } from '../../context/AuthContext';
import { getPostLoginPath } from '../../utils/onboardingPaths';
import { FaEye, FaEyeSlash, FaCircleExclamation, FaUserSlash } from 'react-icons/fa6';
import { FaPhone, FaLock } from 'react-icons/fa6';
import { parseLoginFailure, stripErrorFieldPrefix } from '../../utils/loginErrors';
import {
  getLoginClientContext,
  startLoginContextCapture,
} from '../../services/loginContext';
import SessionPausedNotice from './SessionPausedNotice';
import { useBranding } from '../../context/AppearanceContext';
import BrandingLogo from '../common/BrandingLogo';

const SESSION_NOTICE_CODES = new Set([
  'SESSION_IDLE',
  'SESSION_REPLACED',
  'SESSION_INVALID',
]);

const Login = () => {
  const navigate = useNavigate();
  const location = useLocation();
  const { login } = useAuth();
  const {
    siteTitle,
    loginWelcomeHeading,
    loginTagline,
    loginFooterNote,
    loginFooterPrivacyUrl,
    loginFooterTermsUrl,
    loginFooterRefundUrl,
  } = useBranding();
  const [phone, setPhone] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [rememberMe, setRememberMe] = useState(false);
  const [error, setError] = useState(null);
  const [sessionNotice, setSessionNotice] = useState(null);
  const [loading, setLoading] = useState(false);

  const showLoginError = (payload) => {
    setSessionNotice(null);
    if (!payload) {
      setError(null);
      return;
    }
    if (typeof payload === 'string') {
      setError(parseLoginFailure({ success: false, message: payload }) || {
        title: 'Unable to sign in',
        message: payload,
        variant: 'generic',
      });
      return;
    }
    const parsed =
      parseLoginFailure({ success: false, ...payload }) ||
      (payload.message
        ? {
            title: payload.errorTitle || payload.title || 'Unable to sign in',
            message: stripErrorFieldPrefix(payload.message),
            variant: payload.errorVariant || payload.variant || 'generic',
          }
        : null);
    setError(parsed);
  };

  // Request browser location once on visit (native prompt; non-blocking for login)
  React.useEffect(() => {
    startLoginContextCapture();
  }, []);

  React.useEffect(() => {
    const params = new URLSearchParams(location.search);
    const sessionCode = params.get('session');
    if (!sessionCode) return;
    if (SESSION_NOTICE_CODES.has(sessionCode)) {
      setError(null);
      setSessionNotice(sessionCode);
    } else {
      setSessionNotice(null);
      showLoginError({
        title: 'Session ended',
        message: 'Your session is no longer valid. Please sign in again.',
        variant: 'generic',
      });
    }
    navigate('/login', { replace: true });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError(null);
    setSessionNotice(null);
    setLoading(true);

    // Validate phone number (10 digits)
    if (!phone || phone.length !== 10 || !/^\d+$/.test(phone)) {
      showLoginError('Please enter a valid 10-digit phone number');
      setLoading(false);
      return;
    }

    // Validate password (backend authenticates any stored hash; do not block short passwords here)
    if (!password) {
      showLoginError('Please enter your password');
      setLoading(false);
      return;
    }

    try {
      let clientContext = null;
      try {
        clientContext = await getLoginClientContext();
      } catch {
        clientContext = null;
      }
      const result = await login(phone, password, clientContext);
      if (result.success) {
        // Store remember me preference
        if (rememberMe) {
          localStorage.setItem('mpayhub_remember_phone', phone);
        } else {
          localStorage.removeItem('mpayhub_remember_phone');
        }

        const next = getPostLoginPath(result.user);
        navigate(next, { replace: true });
      } else {
        showLoginError(result);
      }
    } catch {
      showLoginError('An error occurred. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  // Load remembered phone number
  React.useEffect(() => {
    const rememberedPhone = localStorage.getItem('mpayhub_remember_phone');
    if (rememberedPhone) {
      setPhone(rememberedPhone);
      setRememberMe(true);
    }
  }, []);

  React.useEffect(() => {
    if (location.state?.disabledAccount) {
      showLoginError({
        success: false,
        message: 'Your account is disabled. Contact your administrator.',
        errorCode: 'USER_DISABLED',
      });
      navigate(location.pathname, { replace: true, state: {} });
    }
  }, [location.state, location.pathname, navigate]);

  return (
    <div className="min-h-screen flex flex-col lg:flex-row">
      {/* Left Panel - Branding Section */}
      <div className="hidden lg:flex lg:w-1/2 relative overflow-hidden">
        {/* Background Image with Pattern */}
        <div 
          className="absolute inset-0"
          style={{
            backgroundImage: 'linear-gradient(135deg, rgba(30, 58, 138, 0.95) 0%, rgba(67, 56, 202, 0.95) 50%, rgba(79, 70, 229, 0.95) 100%), url("data:image/svg+xml,%3Csvg width=\'60\' height=\'60\' viewBox=\'0 0 60 60\' xmlns=\'http://www.w3.org/2000/svg\'%3E%3Cg fill=\'none\' fill-rule=\'evenodd\'%3E%3Cg fill=\'%23ffffff\' fill-opacity=\'0.05\'%3E%3Cpath d=\'M36 34v-4h-2v4h-4v2h4v4h2v-4h2v-2h-4zm0 0v-2h2v2h-2z\'/%3E%3C/g%3E%3C/g%3E%3C/svg%3E")',
            backgroundSize: 'cover, 60px 60px',
            backgroundPosition: 'center, center',
          }}
        >
          {/* Subtle gradient overlay */}
          <div className="absolute inset-0 bg-gradient-to-br from-blue-900/70 via-indigo-900/60 to-purple-900/70"></div>
        </div>
        
        {/* Animated Background Elements - More subtle */}
        <div className="absolute inset-0 opacity-5">
          <div className="absolute top-10 left-10 w-96 h-96 bg-cyan-300 rounded-full blur-3xl animate-pulse"></div>
          <div className="absolute bottom-10 right-10 w-80 h-80 bg-blue-400 rounded-full blur-3xl animate-pulse delay-1000"></div>
          <div className="absolute top-1/2 left-1/2 transform -translate-x-1/2 -translate-y-1/2 w-72 h-72 bg-indigo-400 rounded-full blur-3xl animate-pulse delay-500"></div>
        </div>

        {/* Content */}
        <div className="relative z-10 flex flex-col justify-center items-center p-8 xl:p-12 w-full min-h-full">
          {/* Centered Content */}
          <div className="flex flex-col items-center justify-center space-y-6 w-full -mt-16 xl:-mt-20">
            <h1 className="text-white text-2xl xl:text-3xl font-semibold tracking-wide animate-fadeIn text-center">
              {loginWelcomeHeading}
            </h1>
            
            {/* Logo/Graphic Area - Centered */}
            <div className="flex items-center justify-center">
              <div className="relative w-48 h-48 xl:w-56 xl:h-56">
                {/* Outer Circuit Pattern */}
                <div className="absolute inset-0 border-4 border-cyan-300 dark:border-cyan-800 rounded-full opacity-40 animate-spin-slow"></div>
                <div className="absolute inset-4 border-2 border-cyan-300 dark:border-cyan-800 rounded-full opacity-60"></div>
                
                {/* Center Logo */}
                <div className="absolute inset-0 flex items-center justify-center">
                  <div
                    className="w-36 h-36 xl:w-44 xl:h-44 bg-white dark:bg-slate-900 rounded-3xl flex items-center justify-center p-3 xl:p-3.5 overflow-hidden shadow-2xl ring-1 ring-black/5 ring-inset transform hover:scale-105 transition-transform duration-300"
                    aria-hidden
                  >
                    <BrandingLogo
                      className="w-full h-full object-contain object-center select-none scale-[1.08] xl:scale-[1.1] origin-center"
                      draggable={false}
                    />
                  </div>
                </div>
              </div>
            </div>
          </div>

          {/* Bottom Section - Fixed at bottom */}
          <div className="absolute bottom-8 xl:bottom-12 left-8 xl:left-12 right-8 xl:right-12 space-y-6">
            {/* Tagline */}
            <div className="text-center">
              <p className="text-cyan-200 text-lg xl:text-xl font-medium tracking-normal">
                {loginTagline}
              </p>
            </div>

            {(loginFooterNote ||
              loginFooterPrivacyUrl ||
              loginFooterTermsUrl ||
              loginFooterRefundUrl) && (
            <div className="space-y-4">
              {loginFooterNote ? (
                <p className="text-center text-sm text-gray-300">{loginFooterNote}</p>
              ) : null}
              {(loginFooterPrivacyUrl || loginFooterTermsUrl || loginFooterRefundUrl) && (
              <>
              <p className="text-gray-300 text-xs xl:text-sm font-normal text-center">Links:</p>
              <div className="flex flex-wrap justify-center gap-3">
                {loginFooterPrivacyUrl ? (
                <a
                  href={loginFooterPrivacyUrl}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="px-4 py-2 bg-gray-800/50 hover:bg-gray-800/70 text-gray-300 hover:text-cyan-300 rounded-lg text-xs xl:text-sm font-normal transition-all duration-200 border border-gray-700/50 hover:border-cyan-400/50"
                >
                  Privacy Policy
                </a>
                ) : null}
                {loginFooterTermsUrl ? (
                <a
                  href={loginFooterTermsUrl}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="px-4 py-2 bg-gray-800/50 hover:bg-gray-800/70 text-gray-300 hover:text-cyan-300 rounded-lg text-xs xl:text-sm font-normal transition-all duration-200 border border-gray-700/50 hover:border-cyan-400/50"
                >
                  Terms &amp; Conditions
                </a>
                ) : null}
                {loginFooterRefundUrl ? (
                <a
                  href={loginFooterRefundUrl}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="px-4 py-2 bg-gray-800/50 hover:bg-gray-800/70 text-gray-300 hover:text-cyan-300 rounded-lg text-xs xl:text-sm font-normal transition-all duration-200 border border-gray-700/50 hover:border-cyan-400/50"
                >
                  Refund &amp; Cancellation
                </a>
                ) : null}
              </div>
              </>
              )}
            </div>
            )}
          </div>
        </div>
      </div>

      {/* Right Panel - Login Form */}
      <div className="flex-1 flex items-center justify-center bg-white p-6 sm:p-8 lg:p-12 dark:bg-slate-950">
        <div className="w-full max-w-md">
          {/* Mobile: single brand + title block (tight vertical rhythm, separated from fields) */}
          <div className="lg:hidden mb-6 sm:mb-7 rounded-xl bg-slate-50/80 px-4 pt-4 pb-5 ring-1 ring-gray-100 dark:bg-slate-900/80 dark:ring-slate-700">
            <div className="flex flex-col items-center text-center gap-1.5 sm:gap-2">
              <p className="text-2xl font-bold uppercase tracking-[0.22em] text-blue-600/85 dark:text-blue-400/85 leading-tight">
                {loginWelcomeHeading}
              </p>
              <div className="relative flex w-full max-w-[min(94vw,24rem)] justify-center py-1">
                <BrandingLogo
                  alt={siteTitle}
                  className="h-auto w-full max-h-[12rem] sm:max-h-[14rem] object-contain object-center select-none drop-shadow-[0_6px_24px_rgba(30,58,138,0.18)] sm:drop-shadow-[0_8px_28px_rgba(30,58,138,0.2)]"
                  draggable={false}
                />
              </div>
              <h2 className="text-3xl sm:text-4xl font-bold text-gray-900 leading-tight dark:text-slate-100">
                LOGIN
              </h2>
              <p className="text-gray-600 dark:text-slate-400 text-sm sm:text-base leading-snug max-w-xs">
                Please Log into your account
              </p>
            </div>
          </div>

          {/* Login Form */}
          <div className="space-y-8">
            <div className="hidden lg:block">
              <h2 className="text-3xl sm:text-4xl font-bold text-gray-900 dark:text-slate-100 mb-2">LOGIN</h2>
              <p className="text-gray-600 dark:text-slate-400 text-base sm:text-lg">Please Log into your account</p>
              <p className="mt-2 text-xs text-gray-500 dark:text-slate-400">
                Location may be requested for account security. You can allow or deny — login still works either way.
              </p>
            </div>

            <form onSubmit={handleSubmit} className="space-y-6">
              {sessionNotice ? (
                <SessionPausedNotice
                  code={sessionNotice}
                  onDismiss={() => setSessionNotice(null)}
                />
              ) : null}

              {error && !sessionNotice ? (
                <div
                  role="alert"
                  className={`rounded-xl border p-4 shadow-sm animate-fadeIn ${
                    error.variant === 'disabled'
                      ? 'border-amber-300 dark:border-amber-800 bg-amber-50 dark:bg-amber-950/40 ring-1 ring-amber-200/80 dark:ring-amber-800/80'
                      : 'border-red-300 dark:border-red-800 bg-red-50 dark:bg-red-950/40 ring-1 ring-red-200/80 dark:ring-red-800/80'
                  }`}
                >
                  <div className="flex gap-3">
                    <div
                      className={`flex h-11 w-11 shrink-0 items-center justify-center rounded-full ${
                        error.variant === 'disabled' ? 'bg-amber-100 dark:bg-amber-900/40 text-amber-800 dark:text-amber-300' : 'bg-red-100 dark:bg-red-900/40 text-red-700 dark:text-red-300'
                      }`}
                    >
                      {error.variant === 'disabled' ? (
                        <FaUserSlash size={20} aria-hidden />
                      ) : (
                        <FaCircleExclamation size={20} aria-hidden />
                      )}
                    </div>
                    <div className="min-w-0 pt-0.5">
                      <p
                        className={`text-base font-semibold leading-snug ${
                          error.variant === 'disabled' ? 'text-amber-950 dark:text-amber-200' : 'text-red-950 dark:text-red-200'
                        }`}
                      >
                        {error.title}
                      </p>
                      <p
                        className={`mt-1.5 text-sm leading-relaxed ${
                          error.variant === 'disabled' ? 'text-amber-900 dark:text-amber-300' : 'text-red-800 dark:text-red-300'
                        }`}
                      >
                        {error.message}
                      </p>
                      {error.variant === 'disabled' ? (
                        <p className="mt-2 text-xs font-medium text-amber-800/90 dark:text-amber-300/90">
                          Only your administrator can restore access to this account.
                        </p>
                      ) : null}
                    </div>
                  </div>
                </div>
              ) : null}

              {/* Phone Number Input */}
              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-slate-300 mb-2">
                  Phone Number
                </label>
                <div className="relative">
                  <div className="absolute inset-y-0 left-0 pl-4 flex items-center pointer-events-none">
                    <FaPhone className="text-gray-400 dark:text-slate-500" size={20} />
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
                    className="w-full pl-12 pr-4 py-3.5 border-2 border-gray-200 dark:border-slate-700 rounded-xl focus:border-blue-500 focus:ring-2 focus:ring-blue-200 transition-all duration-200 text-base bg-gray-50 dark:bg-slate-800/50 focus:bg-white"
                  />
                  {/* Progress Bar */}
                  {phone.length > 0 && (
                    <div className="absolute bottom-0 left-0 right-0 h-1 bg-blue-500 rounded-b-xl" style={{ width: `${(phone.length / 10) * 100}%` }}></div>
                  )}
                </div>
              </div>

              {/* Password Input */}
              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-slate-300 mb-2">
                  Password
                </label>
                <div className="relative">
                  <div className="absolute inset-y-0 left-0 pl-4 flex items-center pointer-events-none">
                    <FaLock className="text-gray-400 dark:text-slate-500" size={20} />
                  </div>
                  <input
                    type={showPassword ? 'text' : 'password'}
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    placeholder="Enter your password"
                    required
                    className="w-full pl-12 pr-12 py-3.5 border-2 border-gray-200 dark:border-slate-700 rounded-xl focus:border-blue-500 focus:ring-2 focus:ring-blue-200 transition-all duration-200 text-base bg-gray-50 dark:bg-slate-800/50 focus:bg-white"
                  />
                  <button
                    type="button"
                    onClick={() => setShowPassword(!showPassword)}
                    className="absolute inset-y-0 right-0 pr-4 flex items-center text-gray-400 dark:text-slate-500 hover:text-gray-600 dark:hover:text-slate-400 transition-colors"
                  >
                    {showPassword ? <FaEyeSlash size={20} /> : <FaEye size={20} />}
                  </button>
                </div>
              </div>

              {/* Remember Me & Forgot Password */}
              <div className="flex items-center justify-between">
                <label className="flex items-center cursor-pointer group">
                  <input
                    type="checkbox"
                    checked={rememberMe}
                    onChange={(e) => setRememberMe(e.target.checked)}
                    className="w-4 h-4 text-blue-600 dark:text-blue-400 border-gray-300 dark:border-slate-600 rounded focus:ring-blue-500 focus:ring-2 transition-colors group-hover:border-blue-400"
                  />
                  <span className="ml-2 text-sm text-gray-600 dark:text-slate-400 group-hover:text-gray-900 transition-colors">
                    Remember me
                  </span>
                </label>
                <div className="flex flex-col items-end gap-1">
                  <button
                    type="button"
                    onClick={() => navigate('/forgot-password')}
                    className="text-sm font-medium text-blue-600 dark:text-blue-400 hover:text-blue-700 dark:hover:text-blue-200 transition-colors"
                  >
                    Forgot your Password?
                  </button>
                  <button
                    type="button"
                    onClick={() => navigate('/forgot-mpin')}
                    className="text-sm font-medium text-indigo-600 dark:text-indigo-400 hover:text-indigo-700 dark:hover:text-indigo-200 transition-colors"
                  >
                    Reset MPIN
                  </button>
                </div>
              </div>

              {/* Submit Button */}
              <button
                type="submit"
                disabled={loading}
                className="w-full bg-gradient-to-r from-blue-600 to-indigo-600 text-white font-bold py-3.5 px-6 rounded-xl hover:from-blue-700 hover:to-indigo-700 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2 transition-all duration-200 transform hover:scale-[1.02] active:scale-[0.98] shadow-lg hover:shadow-xl disabled:opacity-50 disabled:cursor-not-allowed disabled:transform-none"
              >
                {loading ? (
                  <span className="flex items-center justify-center">
                    <svg className="animate-spin -ml-1 mr-3 h-5 w-5 text-white" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                      <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                    </svg>
                    Logging in...
                  </span>
                ) : (
                  'LOGIN'
                )}
              </button>
            </form>

            {/* Mobile Footer Links */}
            <div className="lg:hidden pt-6 border-t border-gray-200 dark:border-slate-700">
              <div className="flex flex-wrap justify-center gap-3 text-sm">
                <button type="button" className="text-gray-600 dark:text-slate-400 hover:text-blue-600 transition-colors font-medium">
                  Privacy Policy
                </button>
                <span className="text-gray-300">|</span>
                <button type="button" className="text-gray-600 dark:text-slate-400 hover:text-blue-600 transition-colors font-medium">
                  Terms & Conditions
                </button>
                <span className="text-gray-300">|</span>
                <button type="button" className="text-gray-600 dark:text-slate-400 hover:text-blue-600 transition-colors font-medium">
                  Refund & Cancellation
                </button>
              </div>
              <p className="text-xs text-gray-500 dark:text-slate-400 mt-4 text-center">
                Driven by Trust, Built for Scale
              </p>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default Login;
