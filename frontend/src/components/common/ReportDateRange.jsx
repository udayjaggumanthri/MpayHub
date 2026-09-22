import React, { useEffect, useRef, useState } from 'react';
import {
  constrainDmyInput,
  isoToDmy,
  normalizeIsoDate,
  parseUserDate,
  rangeDateError,
  todayIsoDate,
} from '../../utils/reportDate';

const inputClass =
  'w-full min-w-0 rounded-lg border bg-white dark:bg-slate-900 px-3 py-2.5 text-sm text-gray-900 dark:text-slate-100 focus:outline-none focus:ring-2 min-h-[44px]';

function CalendarIcon({ className = 'h-5 w-5' }) {
  return (
    <svg className={className} fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden>
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        strokeWidth={2}
        d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z"
      />
    </svg>
  );
}

/**
 * Text DD/MM/YYYY + reliable calendar open.
 * Native picker is anchored to the full field (not a 44px tip), and the
 * calendar control is a real button with a 44×44 hit target.
 */
function DateField({ id, label, isoValue, onDraftChange, sizeClass, compact = false }) {
  const [text, setText] = useState(() => isoToDmy(isoValue));
  const [localError, setLocalError] = useState('');
  const dateRef = useRef(null);

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

  const applyIso = (raw) => {
    const iso = normalizeIsoDate(raw);
    if (!iso) {
      setLocalError('Date cannot be after today.');
      return;
    }
    onDraftChange(iso);
    setText(isoToDmy(iso));
    setLocalError('');
  };

  const openCalendar = async (e) => {
    e.preventDefault();
    e.stopPropagation();
    const el = dateRef.current;
    if (!el) return;
    try {
      if (typeof el.showPicker === 'function') {
        await el.showPicker();
        return;
      }
    } catch {
      /* fall through to click() */
    }
    try {
      el.focus({ preventScroll: true });
      el.click();
    } catch {
      /* ignore */
    }
  };

  const invalid = Boolean(localError);

  return (
    <div className="min-w-0 w-full">
      {label ? (
        <label htmlFor={id} className="mb-1.5 block text-sm font-medium text-gray-700 dark:text-slate-300">
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
              : 'border-gray-300 dark:border-slate-600 focus:border-blue-500 focus:ring-blue-500'
          }`}
          lang="en-IN"
          aria-invalid={invalid}
          aria-describedby={`${id}-hint`}
          aria-label={label || 'Date'}
        />

        {/* Full-field native input: used as showPicker() anchor so the popup
            aligns under the control (not a tiny right-edge tip). */}
        <input
          ref={dateRef}
          type="date"
          lang="en-IN"
          tabIndex={-1}
          max={todayIsoDate()}
          min="2000-01-01"
          value={isoValue || ''}
          onChange={(e) => applyIso(e.target.value)}
          aria-hidden
          className="pointer-events-none absolute inset-0 h-full w-full opacity-0"
          style={{ fontSize: 16 }}
        />

        <button
          type="button"
          onMouseDown={(e) => {
            // Keep focus from jumping away before showPicker runs.
            e.preventDefault();
          }}
          onClick={openCalendar}
          className="absolute inset-y-0 right-0 z-30 flex w-12 items-center justify-center rounded-r-lg text-slate-500 transition hover:bg-slate-100 hover:text-slate-800 focus:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-blue-500 dark:text-slate-400 dark:hover:bg-slate-800 dark:hover:text-slate-200"
          aria-label={`Open ${label || 'date'} calendar`}
        >
          <CalendarIcon />
        </button>
      </div>
      {localError ? (
        <p id={`${id}-hint`} className="mt-1 text-xs text-red-600 dark:text-red-400">
          {localError}
        </p>
      ) : compact ? (
        <span id={`${id}-hint`} className="sr-only">
          Type DD/MM/YYYY or open the calendar.
        </span>
      ) : (
        <p id={`${id}-hint`} className="mt-1 text-xs text-gray-500 dark:text-slate-400">
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
  applyInline = false,
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
    ? 'w-full min-w-0 rounded-lg border bg-white dark:bg-slate-900 px-3 py-2.5 text-sm font-medium text-slate-800 dark:text-slate-200 shadow-sm focus:outline-none focus:ring-2 min-h-[44px]'
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
  const hasLabels = Boolean(fromLabel || toLabel);

  // Align Apply to the input baseline (under labels when present).
  const gridClass =
    showApply && applyInline
      ? `grid min-w-0 grid-cols-1 gap-3 md:grid-cols-[minmax(0,1fr)_minmax(0,1fr)_auto] ${
          hasLabels ? 'md:items-end' : 'md:items-center'
        }`
      : 'grid min-w-0 grid-cols-1 gap-4 sm:grid-cols-2';

  return (
    <div className={`${gridClass} ${className}`}>
      <div className="min-w-0 w-full">
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
      <div className="min-w-0 w-full">
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
          disabled={Boolean(orderError)}
          className={`inline-flex min-h-[44px] w-full items-center justify-center rounded-lg bg-blue-600 px-4 py-2.5 text-sm font-semibold text-white shadow-sm transition-colors hover:bg-blue-700 disabled:cursor-not-allowed disabled:opacity-50 ${
            applyInline ? 'md:mb-0 md:w-auto md:self-end' : 'sm:w-auto'
          }`}
        >
          {applyLabel}
        </button>
      ) : null}
      {orderError ? (
        <p className="w-full text-xs text-red-600 dark:text-red-400 sm:col-span-full md:col-span-full">
          {orderError}
        </p>
      ) : null}
    </div>
  );
}
