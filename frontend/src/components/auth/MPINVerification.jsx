import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../../context/AuthContext';
import { SESSION_POST_MPIN_ANNOUNCE } from '../../utils/announcements';
import { getPayInOnlyRedirectPath } from '../../utils/userAccess';
import MpinInput from '../common/MpinInput';

const MPINVerification = () => {
  const navigate = useNavigate();
  const { user, verifyMPIN, refreshUser, maintenance } = useAuth();
  const [mpin, setMpin] = useState(['', '', '', '', '', '']);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!user) {
      navigate('/login');
    }
  }, [user, navigate]);

  useEffect(() => {
    refreshUser();
  }, [refreshUser]);

  const handleSubmit = async (mpinValue = mpin.join('')) => {
    if (mpinValue.length !== 6) {
      setError('Please enter 6-digit MPIN');
      return;
    }

    setLoading(true);
    setError('');

    try {
      const result = await verifyMPIN(mpinValue);
      if (result.success) {
        sessionStorage.setItem(SESSION_POST_MPIN_ANNOUNCE, '1');
        navigate(getPayInOnlyRedirectPath(user, maintenance));
      } else {
        setError(result.message || 'Invalid MPIN');
        setMpin(['', '', '', '', '', '']);
      }
    } catch (err) {
      setError('An error occurred. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-blue-50 to-indigo-100 dark:from-slate-900 dark:to-slate-800 flex items-center justify-center px-4 py-8">
      <div className="max-w-md w-full bg-white dark:bg-slate-800 rounded-2xl shadow-xl p-5 sm:p-8">
        <div className="text-center mb-6 sm:mb-8">
          <h1 className="text-2xl sm:text-3xl font-bold text-gray-800 dark:text-slate-100 mb-2">Enter MPIN</h1>
          <p className="text-gray-600 dark:text-slate-400">
            Please enter your 6-digit MPIN to continue
          </p>
          {user && (
            <p className="text-sm text-gray-500 dark:text-slate-500 mt-2">
              Logged in as: {user.name} ({user.displayCode || user.userId || user.user_id || user.memberId})
            </p>
          )}
        </div>

        {error && (
          <div className="bg-red-50 dark:bg-red-950/40 border border-red-200 dark:border-red-800 text-red-700 dark:text-red-300 px-4 py-3 rounded-lg mb-6">
            {error}
          </div>
        )}

        <form
          onSubmit={(e) => {
            e.preventDefault();
            handleSubmit();
          }}
          className="space-y-6"
        >
          <MpinInput
            variant="boxes"
            value={mpin}
            onChange={(next) => {
              setMpin(next);
              setError('');
            }}
            onComplete={handleSubmit}
            disabled={loading}
            className="mb-8"
          />

          <button
            type="submit"
            disabled={loading || mpin.some((digit) => digit === '')}
            className="w-full bg-blue-600 text-white py-3 rounded-lg font-semibold hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
          >
            {loading ? 'Verifying...' : 'Verify MPIN'}
          </button>
        </form>

        <div className="mt-6 text-center space-y-2">
          <button
            type="button"
            onClick={() => navigate('/forgot-mpin')}
            className="block w-full text-sm font-medium text-indigo-600 hover:text-indigo-800 dark:text-indigo-400 dark:hover:text-indigo-300"
          >
            Forgot MPIN? Reset via OTP
          </button>
          <button
            type="button"
            onClick={() => navigate('/login')}
            className="text-sm text-blue-600 hover:text-blue-800 dark:text-blue-400 dark:hover:text-blue-300"
          >
            Back to Login
          </button>
        </div>
      </div>
    </div>
  );
};

export default MPINVerification;
