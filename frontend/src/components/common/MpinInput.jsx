import React, { useState, useRef, useEffect } from 'react';
import { FaEye, FaEyeSlash } from 'react-icons/fa6';
import Input from './Input';

/**
 * Shared MPIN input with show/hide privacy toggle.
 * variant: 'boxes' (6-digit) | 'single' (password field)
 */
const MpinInput = ({
  variant = 'boxes',
  value,
  onChange,
  onComplete,
  disabled = false,
  error,
  label,
  placeholder = 'Enter 6-digit MPIN',
  className = '',
}) => {
  const [showMpin, setShowMpin] = useState(false);
  const inputRefs = useRef([]);

  const digits = variant === 'boxes'
    ? (Array.isArray(value) ? value : String(value || '').padEnd(6, ' ').split('').slice(0, 6).map((d) => (d === ' ' ? '' : d)))
    : [];

  const handleBoxChange = (index, char) => {
    if (char && !/^\d$/.test(char)) return;
    const next = [...digits];
    next[index] = char;
    onChange?.(next);
    if (char && index < 5) inputRefs.current[index + 1]?.focus();
    if (index === 5 && char && next.every((d) => d !== '')) {
      onComplete?.(next.join(''));
    }
  };

  const handleBoxKeyDown = (index, e) => {
    if (e.key === 'Backspace' && !digits[index] && index > 0) {
      inputRefs.current[index - 1]?.focus();
    }
  };

  const handlePaste = (e) => {
    e.preventDefault();
    const text = e.clipboardData.getData('text');
    const parsed = text.replace(/\D/g, '').slice(0, 6).split('');
    if (variant === 'boxes' && parsed.length === 6) {
      onChange?.(parsed);
      inputRefs.current[5]?.focus();
      onComplete?.(parsed.join(''));
      return;
    }
    if (variant === 'single') {
      onChange?.(parsed.join(''));
    }
  };

  useEffect(() => {
    if (variant === 'boxes') inputRefs.current[0]?.focus();
  }, [variant]);

  if (variant === 'single') {
    return (
      <div className={className}>
        <Input
          label={label}
          type={showMpin ? 'text' : 'password'}
          inputMode="numeric"
          maxLength={6}
          value={value || ''}
          onChange={(e) => onChange?.(e.target.value.replace(/\D/g, '').slice(0, 6))}
          placeholder={placeholder}
          disabled={disabled}
          error={error}
          rightIcon={showMpin ? FaEyeSlash : FaEye}
          onRightIconClick={() => setShowMpin((v) => !v)}
          className="tracking-widest text-center"
        />
      </div>
    );
  }

  return (
    <div className={className}>
      {label ? <p className="text-sm font-medium text-gray-700 dark:text-slate-300 mb-3 text-center">{label}</p> : null}
      {/* Boxes flex down to fit narrow phones instead of overflowing the card */}
      <div className="flex w-full items-center justify-center gap-1.5 sm:gap-2">
        {/* Balances the toggle so the digit group stays optically centred */}
        <span aria-hidden className="w-8 shrink-0 sm:w-10" />
        <div className="flex min-w-0 flex-1 justify-center gap-1.5 sm:gap-2.5">
          {[0, 1, 2, 3, 4, 5].map((index) => (
            <input
              key={index}
              ref={(el) => {
                inputRefs.current[index] = el;
              }}
              type={showMpin ? 'text' : 'password'}
              inputMode="numeric"
              maxLength={1}
              value={digits[index] || ''}
              onChange={(e) => handleBoxChange(index, e.target.value)}
              onKeyDown={(e) => handleBoxKeyDown(index, e)}
              onPaste={handlePaste}
              className="h-12 w-full min-w-0 max-w-[3rem] flex-1 rounded-lg border-2 border-gray-300 bg-white text-center text-xl font-bold text-gray-900 transition-all focus:border-blue-500 focus:ring-2 focus:ring-blue-200 disabled:opacity-60 dark:border-slate-600 dark:bg-slate-900 dark:text-slate-100 dark:focus:ring-blue-900/60 sm:h-14 sm:text-2xl"
              disabled={disabled}
              autoComplete="off"
            />
          ))}
        </div>
        <button
          type="button"
          onClick={() => setShowMpin((v) => !v)}
          className="inline-flex h-10 w-8 shrink-0 items-center justify-center text-gray-500 transition-colors hover:text-gray-700 dark:text-slate-400 dark:hover:text-slate-300 sm:w-10"
          aria-label={showMpin ? 'Hide MPIN' : 'Show MPIN'}
        >
          {showMpin ? <FaEyeSlash size={18} /> : <FaEye size={18} />}
        </button>
      </div>
      {error ? <p className="mt-2 text-sm text-red-600 dark:text-red-400 text-center">{error}</p> : null}
    </div>
  );
};

export default MpinInput;
