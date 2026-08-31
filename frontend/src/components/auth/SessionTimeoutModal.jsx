import React from 'react';
import { getSessionNoticeCopy } from './SessionPausedNotice';

/**
 * Mixpanel-inspired session timeout overlay:
 * blurred app behind, white centered card, single LOGIN CTA.
 * Colors match mPayHub brand (primary blue / indigo).
 */
const SessionTimeoutModal = ({ code = 'SESSION_IDLE', onLogin }) => {
  const idle = !code || code === 'SESSION_IDLE' || code === 'SESSION_INVALID';
  const title = idle ? 'Session timeout' : getSessionNoticeCopy(code).title;
  const message = idle
    ? "You weren't clicking around any more, so we logged you out for your protection. To get back in, just login again."
    : getSessionNoticeCopy(code).message;

  return (
    <div
      className="fixed inset-0 z-[200] flex items-center justify-center p-4 sm:p-6"
      role="dialog"
      aria-modal="true"
      aria-labelledby="session-timeout-title"
      aria-describedby="session-timeout-desc"
    >
      {/* Soft blur of the frozen app */}
      <div
        className="absolute inset-0 bg-slate-900/35 backdrop-blur-[6px]"
        aria-hidden
      />

      <div className="relative w-full max-w-[420px] overflow-hidden rounded-2xl bg-white dark:bg-slate-900 px-8 pb-8 pt-10 text-center shadow-2xl shadow-slate-900/20 ring-1 ring-black/5 animate-fadeIn">
        {/* Friendly sleep illustration (calm, brand-tinted) */}
        <div className="relative mx-auto mb-6 flex h-24 w-28 items-center justify-center" aria-hidden>
          <div className="absolute inset-x-4 bottom-1 h-3 rounded-full bg-blue-100/90 dark:bg-blue-900/40 blur-[1px]" />
          <div className="relative flex h-16 w-20 items-end justify-center">
            <div className="relative h-14 w-16 rounded-[1.35rem] bg-gradient-to-b from-blue-100 dark:from-blue-900/40 to-indigo-50 dark:to-indigo-950/40 ring-1 ring-blue-200/80 dark:ring-blue-800/80">
              <div className="absolute left-3.5 top-5 h-2 w-2.5 rounded-full bg-blue-400/80" />
              <div className="absolute right-3.5 top-5 h-2 w-2.5 rounded-full bg-blue-400/80" />
              <div className="absolute bottom-3.5 left-1/2 h-1.5 w-5 -translate-x-1/2 rounded-full bg-blue-300/70" />
            </div>
          </div>
          <span className="absolute right-0 top-0 select-none text-[11px] font-semibold tracking-widest text-blue-400">
            z
          </span>
          <span className="absolute right-2 top-3 select-none text-[13px] font-semibold tracking-widest text-blue-500">
            z
          </span>
          <span className="absolute -right-1 top-6 select-none text-[15px] font-bold tracking-widest text-blue-600 dark:text-blue-400">
            Z
          </span>
        </div>

        <h2
          id="session-timeout-title"
          className="text-2xl font-bold tracking-tight text-slate-800 dark:text-slate-200"
        >
          {title}
        </h2>
        <p
          id="session-timeout-desc"
          className="mx-auto mt-3 max-w-[20rem] text-[15px] leading-relaxed text-slate-500 dark:text-slate-400"
        >
          {message}
        </p>

        <button
          type="button"
          onClick={onLogin}
          className="mt-8 w-full rounded-lg bg-gradient-to-r from-blue-600 to-indigo-600 px-6 py-3.5 text-sm font-bold uppercase tracking-[0.12em] text-white shadow-lg shadow-blue-600/25 transition hover:from-blue-700 hover:to-indigo-700 focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-500 focus-visible:ring-offset-2"
        >
          Login
        </button>
      </div>
    </div>
  );
};

export default SessionTimeoutModal;
