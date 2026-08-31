import React, { useState } from 'react';
import { FiChevronDown, FiFilter } from 'react-icons/fi';

/** Shared control styles for filter inputs and selects. */
export const FILTER_INPUT_CLASS =
  'w-full min-w-0 rounded-lg border border-gray-300 dark:border-slate-600 bg-white dark:bg-slate-900 px-3 py-2 text-sm text-gray-900 dark:text-slate-100 shadow-sm placeholder:text-gray-400 dark:placeholder:text-slate-500 focus:border-blue-500 focus:outline-none focus:ring-2 focus:ring-blue-500/20 min-h-[42px]';

export const FILTER_SELECT_CLASS = FILTER_INPUT_CLASS;

const spanClass = {
  1: '',
  2: 'sm:col-span-2',
  3: 'sm:col-span-2 lg:col-span-3',
  full: 'col-span-full',
};

/** Compact show/hide filters toggle with optional active-count badge. */
export function ReportFilterToggle({ open, onToggle, activeCount = 0, className = '' }) {
  return (
    <button
      type="button"
      onClick={onToggle}
      aria-expanded={open}
      className={`inline-flex min-h-[40px] items-center gap-2 rounded-lg border border-gray-300 dark:border-slate-600 bg-white dark:bg-slate-900 px-3.5 py-2 text-sm font-semibold text-gray-800 dark:text-slate-200 shadow-sm transition hover:bg-gray-50 dark:hover:bg-slate-800 ${className}`}
    >
      <FiFilter className="h-4 w-4 shrink-0 text-gray-500 dark:text-slate-400" aria-hidden />
      <span>{open ? 'Hide filters' : 'Show filters'}</span>
      {activeCount > 0 ? (
        <span className="rounded-full bg-blue-100 dark:bg-blue-900/40 px-2 py-0.5 text-xs font-bold text-blue-700 dark:text-blue-300">
          {activeCount}
        </span>
      ) : null}
      <FiChevronDown
        className={`h-4 w-4 shrink-0 text-gray-400 dark:text-slate-500 transition-transform ${open ? 'rotate-180' : ''}`}
        aria-hidden
      />
    </button>
  );
}

/**
 * Collapsible filter section — hidden by default; expand to edit and apply.
 */
export function CollapsibleReportFilters({
  defaultOpen = false,
  open: controlledOpen,
  onOpenChange,
  activeCount = 0,
  toolbarEnd = null,
  className = '',
  children,
  ...panelProps
}) {
  const [internalOpen, setInternalOpen] = useState(defaultOpen);
  const open = controlledOpen ?? internalOpen;
  const setOpen = onOpenChange ?? setInternalOpen;

  return (
    <div className={`mb-3 ${className}`}>
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex flex-wrap items-center gap-2">
          <ReportFilterToggle
            open={open}
            onToggle={() => setOpen(!open)}
            activeCount={activeCount}
          />
          {!open && activeCount > 0 ? (
            <span className="text-xs text-gray-500 dark:text-slate-400">
              {activeCount} active filter{activeCount === 1 ? '' : 's'} — click Show filters to edit
            </span>
          ) : null}
        </div>
        {toolbarEnd ? <div className="flex flex-wrap items-center gap-2">{toolbarEnd}</div> : null}
      </div>
      {open ? (
        <ReportFilterPanel embedded className="mt-2 rounded-lg border border-gray-200 dark:border-slate-700 bg-gray-50/80 dark:bg-slate-800/50 p-3 sm:p-4" {...panelProps}>
          {children}
        </ReportFilterPanel>
      ) : null}
    </div>
  );
}

/**
 * Filter panel shell — consistent padding, border, and action row across reports/admin lists.
 */
export function ReportFilterPanel({
  title = '',
  children,
  onApply,
  onClear,
  applyLabel = 'Apply filters',
  clearLabel = 'Clear filters',
  applying = false,
  className = '',
  embedded = false,
  actions,
}) {
  return (
    <div
      className={`${
        embedded
          ? ''
          : 'mb-3 rounded-xl border border-gray-200 dark:border-slate-700 bg-gray-50/90 dark:bg-slate-800/50 p-3 sm:p-4'
      } ${className}`}
    >
      {title ? (
        <h3 className="mb-2 text-xs font-semibold uppercase tracking-wide text-gray-600 dark:text-slate-400">{title}</h3>
      ) : null}
      <div className="space-y-3">{children}</div>
      {actions || onApply || onClear ? (
        <div className="mt-3 flex flex-col-reverse gap-2 border-t border-gray-200/80 dark:border-slate-700/80 pt-3 sm:flex-row sm:items-center sm:justify-end">
          {actions}
          {onClear ? (
            <button
              type="button"
              onClick={onClear}
              disabled={applying}
              className="inline-flex min-h-[40px] w-full items-center justify-center rounded-lg border border-gray-300 dark:border-slate-600 bg-white dark:bg-slate-900 px-4 py-2 text-sm font-semibold text-gray-700 dark:text-slate-300 shadow-sm transition hover:bg-gray-50 dark:hover:bg-slate-800 disabled:opacity-60 sm:w-auto"
            >
              {clearLabel}
            </button>
          ) : null}
          {onApply ? (
            <button
              type="button"
              onClick={onApply}
              disabled={applying}
              className="inline-flex min-h-[40px] w-full items-center justify-center gap-2 rounded-lg bg-blue-600 px-4 py-2 text-sm font-semibold text-white shadow-sm transition hover:bg-blue-700 disabled:opacity-60 sm:w-auto"
            >
              <FiFilter className="h-4 w-4 shrink-0" aria-hidden />
              {applyLabel}
            </button>
          ) : null}
        </div>
      ) : null}
    </div>
  );
}

/**
 * Responsive filter grid — 1 col mobile, 2 cols tablet, 3 cols desktop.
 */
export function ReportFilterGrid({ children, className = '' }) {
  return (
    <div className={`grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-3 ${className}`}>
      {children}
    </div>
  );
}

/**
 * Single filter field with label; use span="full" for date ranges or wide search.
 */
export function ReportFilterField({ label, htmlFor, children, span = 1, className = '' }) {
  return (
    <div className={`min-w-0 ${spanClass[span] || ''} ${className}`}>
      {label ? (
        <label htmlFor={htmlFor} className="mb-1 block text-sm font-medium text-gray-700 dark:text-slate-300">
          {label}
        </label>
      ) : null}
      {children}
    </div>
  );
}

/**
 * Full-width row for date range pickers (keeps From/To on one line on tablet+).
 */
export function ReportFilterDateRow({ children, className = '' }) {
  return <div className={`min-w-0 w-full ${className}`}>{children}</div>;
}
