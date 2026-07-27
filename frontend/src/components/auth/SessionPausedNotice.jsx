import React from 'react';
import { FaArrowRotateRight, FaDesktop } from 'react-icons/fa6';

/**
 * Calm session-paused notice for login (idle / invalid / replaced).
 * Not an error — invites the user to continue signing in.
 */
const COPY = {
  SESSION_IDLE: {
    title: 'Session timeout',
    message:
      "You weren't clicking around any more, so we logged you out for your protection. Sign in below to get back in.",
  },
  SESSION_REPLACED: {
    title: 'Signed in elsewhere',
    message:
      'This session ended because you signed in on another device. Sign in here if you want to continue on this one.',
  },
  SESSION_INVALID: {
    title: 'Session timeout',
    message:
      'Your previous session is no longer active. Sign in below to pick up where you left off.',
  },
};

export function getSessionNoticeCopy(code) {
  return COPY[code] || COPY.SESSION_INVALID;
}

const SessionPausedNotice = ({ code = 'SESSION_IDLE', onDismiss }) => {
  const { title, message } = getSessionNoticeCopy(code);

  return (
    <div
      role="status"
      aria-live="polite"
      className="overflow-hidden rounded-2xl border border-sky-200/90 bg-gradient-to-b from-sky-50 to-white shadow-sm ring-1 ring-sky-100 animate-fadeIn"
    >
      <div className="flex flex-col items-center px-5 pb-5 pt-6 text-center sm:px-6">
        <div className="relative mb-4 flex h-16 w-20 items-center justify-center">
          <div
            className="absolute inset-0 rounded-2xl bg-sky-100/80"
            aria-hidden
          />
          <div className="relative flex h-12 w-16 flex-col overflow-hidden rounded-lg border-2 border-sky-500/80 bg-white shadow-sm">
            <div className="flex h-3 items-center gap-0.5 border-b border-sky-100 bg-sky-50 px-1.5">
              <span className="h-1 w-1 rounded-full bg-sky-300" />
              <span className="h-1 w-1 rounded-full bg-sky-300" />
              <span className="h-1 w-1 rounded-full bg-sky-300" />
            </div>
            <div className="flex flex-1 items-center justify-center">
              <FaDesktop className="text-sky-600" size={18} aria-hidden />
            </div>
          </div>
          <div
            className="absolute -right-1 -top-1 flex h-7 w-7 items-center justify-center rounded-full bg-sky-600 text-white shadow-md ring-2 ring-white"
            aria-hidden
          >
            <FaArrowRotateRight size={12} />
          </div>
        </div>

        <h3 className="text-lg font-semibold tracking-tight text-slate-900 sm:text-xl">
          {title}
        </h3>
        <p className="mt-2 max-w-sm text-sm leading-relaxed text-slate-600">
          {message}
        </p>

        <p className="mt-4 text-xs font-medium text-sky-700/90">
          Enter your phone and password below to resume
        </p>

        {typeof onDismiss === 'function' ? (
          <button
            type="button"
            onClick={onDismiss}
            className="mt-3 text-xs font-semibold text-slate-500 underline-offset-2 hover:text-slate-700 hover:underline"
          >
            Dismiss
          </button>
        ) : null}
      </div>
    </div>
  );
};

export default SessionPausedNotice;
