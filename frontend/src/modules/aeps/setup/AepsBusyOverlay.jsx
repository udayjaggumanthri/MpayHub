import React from 'react';

export default function AepsBusyOverlay({ show, message = 'Please wait…' }) {
  if (!show) return null;
  return (
    <div
      className="fixed inset-0 z-[70] flex items-center justify-center bg-slate-900/40 backdrop-blur-[2px]"
      role="status"
      aria-live="polite"
      aria-busy="true"
    >
      <div className="mx-4 flex max-w-sm flex-col items-center rounded-2xl bg-white dark:bg-slate-900 px-8 py-7 shadow-2xl ring-1 ring-black/5">
        <div className="h-10 w-10 animate-spin rounded-full border-[3px] border-blue-200 dark:border-blue-800 border-t-blue-600" />
        <p className="mt-4 text-center text-sm font-medium text-slate-800 dark:text-slate-200">{message}</p>
        <p className="mt-1 text-center text-xs text-slate-500 dark:text-slate-400">Do not close or refresh this page.</p>
      </div>
    </div>
  );
}
