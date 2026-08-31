import React, { useState, useEffect } from 'react';
import { FiX } from 'react-icons/fi';
import MpinInput from './MpinInput';

const MPINModal = ({ isOpen, onClose, onVerify, title = 'Enter MPIN', error = '', loading = false }) => {
  const [mpin, setMpin] = useState(['', '', '', '', '', '']);

  useEffect(() => {
    if (isOpen) {
      setMpin(['', '', '', '', '', '']);
    }
  }, [isOpen]);

  const handleSubmit = (mpinValue = mpin.join('')) => {
    if (loading) return;
    if (mpinValue.length === 6) {
      onVerify(mpinValue);
    }
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black bg-opacity-50 overflow-y-auto">
      <div className="bg-white dark:bg-slate-800 rounded-xl sm:rounded-2xl shadow-xl max-w-md w-full p-4 sm:p-6 my-auto">
        <div className="flex items-center justify-between mb-4 sm:mb-6">
          <h2 className="text-xl sm:text-2xl font-bold text-gray-800 dark:text-slate-200">{title}</h2>
          <button
            onClick={onClose}
            className="text-gray-400 dark:text-slate-500 hover:text-gray-600 dark:hover:text-slate-400 transition-colors"
          >
            <FiX size={24} />
          </button>
        </div>

        {error && (
          <div className="bg-red-50 dark:bg-red-950/40 border border-red-200 dark:border-red-800 text-red-700 dark:text-red-300 px-4 py-3 rounded-lg mb-6">
            {error}
          </div>
        )}

        <MpinInput
          variant="boxes"
          value={mpin}
          onChange={setMpin}
          onComplete={handleSubmit}
          disabled={loading}
          className="mb-6"
        />

        <div className="flex space-x-3">
          <button
            onClick={onClose}
            className="flex-1 px-4 py-3 border border-gray-300 dark:border-slate-600 rounded-lg text-gray-700 dark:text-slate-300 hover:bg-gray-50 dark:hover:bg-slate-800 transition-colors"
          >
            Cancel
          </button>
          <button
            type="button"
            onClick={() => handleSubmit()}
            disabled={mpin.some((digit) => digit === '') || loading}
            className="flex-1 px-4 py-3 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
          >
            {loading ? 'Processing…' : 'Verify'}
          </button>
        </div>
      </div>
    </div>
  );
};

export default MPINModal;
