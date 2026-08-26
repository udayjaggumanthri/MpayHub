import React, { useEffect, useState } from 'react';
import {
  constrainDmyInput,
  isoToDmy,
  normalizeIsoDate,
  parseUserDate,
  rangeDateError,
  todayIsoDate,
} from '../../utils/reportDate';

const inputClass =
  'w-full min-w-0 rounded-lg border bg-white px-3 py-2.5 text-sm text-gray-900 focus:outline-none focus:ring-2 min-h-[44px]';

function DateField({ id, label, isoValue, onDraftChange, sizeClass, compact = false }) {
  const [text, setText] = useState(() => isoToDmy(isoValue));
  const [localError, setLocalError] = useState('');

  useEffect(() => {
    setText(isoToDmy(isoValue));
    if (!isoValue) setLocalError('');
  }, [isoValue]);

  const commitText = () => {
    const trimmed = text.trim();
    if (!trimmed) {
      onDraftChange('');
      setText('');
      setLocalError('');
      return;
    }
    const { iso, error } = parseUserDate(trimmed);
    if (iso) {
      onDraftChange(iso);
      setText(isoToDmy(iso));
      setLocalError('');
      return;
    }
    setLocalError(error || 'Enter a valid date as DD/MM/YYYY.');
    onDraftChange('');
  };

  const onCalendar = (e) => {
    const iso = normalizeIsoDate(e.target.value);
    if (!iso) {
      setLocalError('Date cannot be after today.');
      return;
    }
    onDraftChange(iso);
    setText(isoToDmy(iso));
    setLocalError('');
  };

  const invalid = Boolean(localError);

  return (
    <div className="min-w-0 w-full">
      {label ? (
        <label htmlFor={id} className="mb-1.5 block text-sm font-medium text-gray-700">
          {label}
        </label>
      ) : null}
      <div className="relative min-w-0">
        <input
          id={id}
          type="text"
          inputMode="numeric"
          autoComplete="off"
          placeholder="DD/MM/YYYY"
          maxLength={10}
          value={text}
          onChange={(e) => {
            setText(constrainDmyInput(e.target.value, text));
            setLocalError('');
          }}
          onBlur={commitText}
          onKeyDown={(e) => {
            if (e.key === 'Enter') {
              e.preventDefault();
              commitText();
            }
          }}
          className={`${sizeClass || inputClass} pr-12 ${
            invalid
              ? 'border-red-400 focus:border-red-500 focus:ring-red-500'
              : 'border-gray-300 focus:border-blue-500 focus:ring-blue-500'
          }`}
          lang="en-IN"
          aria-invalid={invalid}
          aria-describedby={`${id}-hint`}
          aria-label={label || 'Date'}
        />
        <span
          className="pointer-events-none absolute inset-y-0 right-0 z-10 flex w-11 items-center justify-center text-gray-500"
          aria-hidden
        >
          <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z"
            />
          </svg>
        </span>
        {/* Native picker sits on the icon. It must be a real tappable control (not
            sr-only / showPicker-from-button) or phones will ignore the tap. */}
        <input
          type="date"
          lang="en-IN"
          max={todayIsoDate()}
          min="2000-01-01"
          value={isoValue || ''}
          onChange={onCalendar}
          onClick={(e) => e.stopPropagation()}
          aria-label={`${label || 'Date'} calendar`}
          className="absolute inset-y-0 right-0 z-20 w-11 cursor-pointer opacity-0"
          style={{ fontSize: 16 }}
        />
      </div>
      {localError ? (
        <p id={`${id}-hint`} className="mt-1 text-xs text-red-600">
          {localError}
        </p>
      ) : compact ? null : (
        <p id={`${id}-hint`} className="mt-1 text-xs text-gray-500">
          Type DD/MM/YYYY, or tap the calendar. Today or earlier.
        </p>
      )}
    </div>
  );
}

/**
 * From/To date filters. Invalid values never become API dates.
 * Fetch stays the parent's responsibility (Apply).
 */
export default function ReportDateRange({
  dateFrom = '',
  dateTo = '',
  onChange,
  onApply,
  showApply = false,
  applyLabel = 'Apply',
  fromLabel = 'From Date',
  toLabel = 'To Date',
  idPrefix = 'report-date',
  compact = false,
  className = '',
}) {
  const [draftFrom, setDraftFrom] = useState(dateFrom || '');
  const [draftTo, setDraftTo] = useState(dateTo || '');

  useEffect(() => {
    setDraftFrom(dateFrom || '');
  }, [dateFrom]);
  useEffect(() => {
    setDraftTo(dateTo || '');
  }, [dateTo]);

  const fieldClass = compact
    ? 'w-full min-w-0 rounded-md border bg-white px-2 py-2 text-sm font-medium text-slate-800 shadow-sm focus:outline-none focus:ring-1 min-h-[44px]'
    : inputClass;

  const emit = (from, to) => {
    const payload = {
      dateFrom: normalizeIsoDate(from),
      dateTo: normalizeIsoDate(to),
    };
    if (typeof onChange === 'function') onChange(payload);
    return payload;
  };

  const commitToParent = () => {
    const payload = emit(draftFrom, draftTo);
    if (typeof onApply === 'function') onApply(payload);
  };

  const orderError = rangeDateError(draftFrom, draftTo);

  return (
    <div className={`flex min-w-0 flex-col gap-3 sm:flex-row sm:flex-wrap sm:items-end ${className}`}>
      <div className="min-w-0 w-full sm:min-w-[168px] sm:flex-1">
        <DateField
          id={`${idPrefix}-from`}
          label={fromLabel}
          isoValue={draftFrom}
          sizeClass={fieldClass}
          compact={compact}
          onDraftChange={(iso) => {
            setDraftFrom(iso);
            if (!showApply) emit(iso, draftTo);
          }}
        />
      </div>
      <div className="min-w-0 w-full sm:min-w-[168px] sm:flex-1">
        <DateField
          id={`${idPrefix}-to`}
          label={toLabel}
          isoValue={draftTo}
          sizeClass={fieldClass}
          compact={compact}
          onDraftChange={(iso) => {
            setDraftTo(iso);
            if (!showApply) emit(draftFrom, iso);
          }}
        />
      </div>
      {showApply ? (
        <button
          type="button"
          onClick={commitToParent}
          className="inline-flex min-h-[44px] w-full items-center justify-center rounded-lg bg-blue-600 px-4 py-2.5 text-sm font-semibold text-white shadow-sm hover:bg-blue-700 sm:w-auto"
        >
          {applyLabel}
        </button>
      ) : null}
      {orderError ? <p className="w-full text-xs text-red-600">{orderError}</p> : null}
    </div>
  );
}
