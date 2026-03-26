import React, { useState, useRef, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../../context/AuthContext';

const MPINVerification = () => {
  const navigate = useNavigate();
  const { user, verifyMPIN } = useAuth();
  const [mpin, setMpin] = useState(['', '', '', '', '', '']);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const inputRefs = useRef([]);

  // Redirect if not logged in
  useEffect(() => {
    if (!user) {
      navigate('/login');
    }
  }, [user, navigate]);

  const handleChange = (index, value) => {
    // Only allow digits
    if (value && !/^\d$/.test(value)) return;

    const newMpin = [...mpin];
    newMpin[index] = value;
    setMpin(newMpin);
    setError('');

    // Auto-focus next input
    if (value && index < 5) {
      inputRefs.current[index + 1]?.focus();
    }

    // Auto-submit when all 6 digits are entered
    if (index === 5 && value && newMpin.every((digit) => digit !== '')) {
      handleSubmit(newMpin.join(''));
    }
  };

  const handleKeyDown = (index, e) => {
    // Handle backspace
    if (e.key === 'Backspace' && !mpin[index] && index > 0) {
      inputRefs.current[index - 1]?.focus();
    }

    // Handle paste
    if (e.key === 'v' && (e.ctrlKey || e.metaKey)) {
      e.preventDefault();
      navigator.clipboard.readText().then((text) => {
        const digits = text.replace(/\D/g, '').slice(0, 6).split('');
        if (digits.length === 6) {
          setMpin(digits);
          inputRefs.current[5]?.focus();
        }
      });
    }
  };

  const handlePaste = (e) => {
    e.preventDefault();
    const text = e.clipboardData.getData('text');
    const digits = text.replace(/\D/g, '').slice(0, 6).split('');
    if (digits.length === 6) {
      setMpin(digits);
      inputRefs.current[5]?.focus();
    }
  };

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
        navigate('/dashboard');
      } else {
        setError(result.message || 'Invalid MPIN');
        setMpin(['', '', '', '', '', '']);
        inputRefs.current[0]?.focus();
      }
    } catch (err) {
      setError('An error occurred. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  // Focus first input on mount
  useEffect(() => {
    inputRefs.current[0]?.focus();
  }, []);

  return (
    <div className="min-h-screen bg-gradient-to-br from-blue-50 to-indigo-100 flex items-center justify-center px-4 py-8">
      <div className="max-w-md w-full bg-white rounded-2xl shadow-xl p-8">
        <div className="text-center mb-8">
          <h1 className="text-3xl font-bold text-gray-800 mb-2">Enter MPIN</h1>
          <p className="text-gray-600">
            Please enter your 6-digit MPIN to continue
          </p>
          {user && (
            <p className="text-sm text-gray-500 mt-2">
              Logged in as: {user.name} ({user.userId})
            </p>
          )}
        </div>

        {error && (
          <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-lg mb-6">
            {error}
          </div>
        )}

        <form
          onSubmit={(e) => {
            e.preventDefault();
            handleSubmit();
          }}
          onPaste={handlePaste}
          className="space-y-6"
        >
          <div className="flex justify-center space-x-3 mb-8">
            {[0, 1, 2, 3, 4, 5].map((index) => (
              <input
                key={index}
                ref={(el) => (inputRefs.current[index] = el)}
                type="text"
                inputMode="numeric"
                maxLength={1}
                value={mpin[index]}
                onChange={(e) => handleChange(index, e.target.value)}
                onKeyDown={(e) => handleKeyDown(index, e)}
                className="w-12 h-14 text-center text-2xl font-bold border-2 border-gray-300 rounded-lg focus:border-blue-500 focus:ring-2 focus:ring-blue-200 transition-all"
                disabled={loading}
              />
            ))}
          </div>

          <button
            type="submit"
            disabled={loading || mpin.some((digit) => digit === '')}
            className="w-full bg-blue-600 text-white py-3 rounded-lg font-semibold hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
          >
            {loading ? 'Verifying...' : 'Verify MPIN'}
          </button>
        </form>

        <div className="mt-6 text-center">
          <button
            onClick={() => navigate('/login')}
            className="text-sm text-blue-600 hover:text-blue-800"
          >
            Back to Login
          </button>
        </div>
      </div>
    </div>
  );
};

export default MPINVerification;
