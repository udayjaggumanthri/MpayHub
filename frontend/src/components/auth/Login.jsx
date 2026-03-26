import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../../context/AuthContext';
import Input from '../common/Input';
import Button from '../common/Button';
import { FaEye, FaEyeSlash } from 'react-icons/fa6';
import { FaPhone, FaLock } from 'react-icons/fa6';

const Login = () => {
  const navigate = useNavigate();
  const { login } = useAuth();
  const [phone, setPhone] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [rememberMe, setRememberMe] = useState(false);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setLoading(true);

    // Validate phone number (10 digits)
    if (!phone || phone.length !== 10 || !/^\d+$/.test(phone)) {
      setError('Please enter a valid 10-digit phone number');
      setLoading(false);
      return;
    }

    // Validate password
    if (!password || password.length < 3) {
      setError('Please enter a valid password');
      setLoading(false);
      return;
    }

    try {
      const result = await login(phone, password);
      if (result.success) {
        // Store remember me preference
        if (rememberMe) {
          localStorage.setItem('mpayhub_remember_phone', phone);
        } else {
          localStorage.removeItem('mpayhub_remember_phone');
        }

        // Navigate to MPIN verification
        navigate('/mpin-verification');
      } else {
        setError(result.message || 'Invalid phone number or password');
      }
    } catch (err) {
      setError('An error occurred. Please try again.');
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
              WELCOME TO
            </h1>
            
            {/* Logo/Graphic Area - Centered */}
            <div className="flex items-center justify-center">
              <div className="relative w-48 h-48 xl:w-56 xl:h-56">
                {/* Outer Circuit Pattern */}
                <div className="absolute inset-0 border-4 border-cyan-300 rounded-full opacity-40 animate-spin-slow"></div>
                <div className="absolute inset-4 border-2 border-cyan-300 rounded-full opacity-60"></div>
                
                {/* Center Logo */}
                <div className="absolute inset-0 flex items-center justify-center">
                  <div className="w-32 h-32 xl:w-40 xl:h-40 bg-gradient-to-br from-blue-500 to-indigo-600 rounded-3xl flex items-center justify-center shadow-2xl transform hover:scale-110 transition-transform duration-300">
                    <span className="text-white text-4xl xl:text-5xl font-extrabold">mP</span>
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
                Driven by trust, Built for Scale
              </p>
            </div>

            {/* Footer Links */}
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

      {/* Right Panel - Login Form */}
      <div className="flex-1 flex items-center justify-center bg-white p-6 sm:p-8 lg:p-12">
        <div className="w-full max-w-md">
          {/* Mobile Brand Section (only visible on mobile) */}
          <div className="lg:hidden text-center mb-8">
            <div className="inline-block mb-4">
              <div className="w-16 h-16 bg-gradient-to-br from-blue-600 to-indigo-700 rounded-2xl flex items-center justify-center shadow-xl">
                <span className="text-white text-2xl font-bold">mP</span>
              </div>
            </div>
            <h1 className="text-2xl font-bold text-gray-900 mb-2">WELCOME TO</h1>
            <h2 className="text-3xl font-extrabold bg-gradient-to-r from-blue-600 to-indigo-600 bg-clip-text text-transparent">
              mPayhub
            </h2>
          </div>

          {/* Login Form */}
          <div className="space-y-8">
            <div>
              <h2 className="text-3xl sm:text-4xl font-bold text-gray-900 mb-2">LOGIN</h2>
              <p className="text-gray-600 text-base sm:text-lg">Please Log into your account</p>
            </div>

            <form onSubmit={handleSubmit} className="space-y-6">
              {error && (
                <div className="bg-red-50 border-l-4 border-red-500 text-red-700 p-4 rounded-lg flex items-start animate-fadeIn">
                  <div className="flex-shrink-0">
                    <svg className="h-5 w-5 text-red-400" viewBox="0 0 20 20" fill="currentColor">
                      <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z" clipRule="evenodd" />
                    </svg>
                  </div>
                  <p className="ml-3 text-sm font-medium">{error}</p>
                </div>
              )}

              {/* Phone Number Input */}
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
                  {/* Progress Bar */}
                  {phone.length > 0 && (
                    <div className="absolute bottom-0 left-0 right-0 h-1 bg-blue-500 rounded-b-xl" style={{ width: `${(phone.length / 10) * 100}%` }}></div>
                  )}
                </div>
              </div>

              {/* Password Input */}
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Password
                </label>
                <div className="relative">
                  <div className="absolute inset-y-0 left-0 pl-4 flex items-center pointer-events-none">
                    <FaLock className="text-gray-400" size={20} />
                  </div>
                  <input
                    type={showPassword ? 'text' : 'password'}
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    placeholder="Enter your password"
                    required
                    className="w-full pl-12 pr-12 py-3.5 border-2 border-gray-200 rounded-xl focus:border-blue-500 focus:ring-2 focus:ring-blue-200 transition-all duration-200 text-base bg-gray-50 focus:bg-white"
                  />
                  <button
                    type="button"
                    onClick={() => setShowPassword(!showPassword)}
                    className="absolute inset-y-0 right-0 pr-4 flex items-center text-gray-400 hover:text-gray-600 transition-colors"
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
                    className="w-4 h-4 text-blue-600 border-gray-300 rounded focus:ring-blue-500 focus:ring-2 transition-colors group-hover:border-blue-400"
                  />
                  <span className="ml-2 text-sm text-gray-600 group-hover:text-gray-900 transition-colors">
                    Remember me
                  </span>
                </label>
                <button
                  type="button"
                  onClick={() => navigate('/forgot-password')}
                  className="text-sm font-medium text-blue-600 hover:text-blue-700 transition-colors"
                >
                  Forgot your Password?
                </button>
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
            <div className="lg:hidden pt-6 border-t border-gray-200">
              <div className="flex flex-wrap justify-center gap-3 text-sm">
                <button type="button" className="text-gray-600 hover:text-blue-600 transition-colors font-medium">
                  Privacy Policy
                </button>
                <span className="text-gray-300">|</span>
                <button type="button" className="text-gray-600 hover:text-blue-600 transition-colors font-medium">
                  Terms & Conditions
                </button>
                <span className="text-gray-300">|</span>
                <button type="button" className="text-gray-600 hover:text-blue-600 transition-colors font-medium">
                  Refund & Cancellation
                </button>
              </div>
              <p className="text-xs text-gray-500 mt-4 text-center">
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
