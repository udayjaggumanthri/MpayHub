import React, { useEffect, useMemo, useState } from 'react';
import { HiOutlineIdentification, HiUsers } from 'react-icons/hi2';
import {
  greetingThemeFor,
  msUntilNextHour,
} from './dashboardGreeting';

/**
 * Time-of-day greeting banner.
 * Photo stays sharp; light slots keep a light left fade even when the app is in
 * dark mode (no dark gradient washed over the image). Right copy is padded so
 * it never clips the edge.
 */
const GreetingBanner = ({ user }) => {
  const [now, setNow] = useState(() => new Date());

  useEffect(() => {
    let timer = window.setTimeout(function tick() {
      setNow(new Date());
      timer = window.setTimeout(tick, msUntilNextHour(new Date()));
    }, msUntilNextHour(new Date()));
    return () => window.clearTimeout(timer);
  }, []);

  const theme = useMemo(() => greetingThemeFor(now), [now]);
  const slot = theme.slot;

  const firstName = String(user?.name || '').trim().split(/\s+/)[0] || 'there';
  const userCode = user?.displayCode || user?.userId || user?.user_id || user?.memberId || '—';
  const isActive = user?.is_active !== false;
  const isLight = theme.tone === 'light';

  // Banner panel follows PHOTO tone only — never app dark: classes on the image.
  const panelClass = isLight
    ? 'from-white via-white/95 to-transparent'
    : slot === 'evening'
      ? 'from-[#1a1030] via-[#1a1030]/88 to-transparent'
      : 'from-[#071428] via-[#071428]/88 to-transparent';

  const titleMuted = isLight ? 'text-slate-600' : 'text-white/80';
  const titleStrong = isLight ? 'text-blue-800' : 'text-white';
  const messageClass = isLight ? 'text-slate-600' : 'text-white/75';
  const chipClass = isLight
    ? 'bg-slate-100/95 text-slate-700 ring-1 ring-slate-200/90'
    : 'bg-white/12 text-white ring-1 ring-white/25';

  return (
    <section
      aria-labelledby="dash-greeting-heading"
      className="relative isolate overflow-hidden rounded-2xl shadow-sm ring-1 ring-slate-200/70 dark:ring-slate-700/60"
    >
      <img
        src={theme.image}
        alt=""
        aria-hidden
        className="absolute inset-0 h-full w-full object-cover object-[72%_center]"
      />

      <div
        className={`pointer-events-none absolute inset-y-0 left-0 w-full bg-gradient-to-r sm:w-[70%] lg:w-[55%] ${panelClass}`}
        aria-hidden
      />

      <div className="relative flex min-h-0 flex-col gap-3 px-4 py-4 sm:min-h-[11.5rem] sm:gap-4 sm:px-6 sm:py-6 lg:flex-row lg:items-center lg:gap-6 lg:pr-10">
        <div className="min-w-0 max-w-md flex-1">
          <h1 id="dash-greeting-heading" className="leading-tight">
            <span className={`block text-sm font-medium sm:text-lg ${titleMuted}`}>
              {theme.label},
            </span>
            <span className={`mt-0.5 block text-2xl font-bold tracking-tight sm:text-4xl ${titleStrong}`}>
              {firstName}!
            </span>
          </h1>
          <p className={`mt-1.5 hidden text-sm leading-relaxed sm:mt-2 sm:block ${messageClass}`}>
            {theme.message}
          </p>

          <div
            className={`mt-3 inline-flex max-w-full flex-wrap items-center gap-x-3 gap-y-1 rounded-full px-3 py-1.5 text-[11px] font-semibold sm:mt-4 ${chipClass}`}
          >
            <span className="inline-flex items-center gap-1.5">
              <HiOutlineIdentification className="h-3.5 w-3.5 opacity-70" aria-hidden />
              {userCode}
            </span>
            {user?.role ? (
              <>
                <span className="h-3 w-px bg-current opacity-25" aria-hidden />
                <span className="inline-flex items-center gap-1.5">
                  <HiUsers className="h-3.5 w-3.5 opacity-70" aria-hidden />
                  {user.role}
                </span>
              </>
            ) : null}
            <span className="h-3 w-px bg-current opacity-25" aria-hidden />
            <span className="inline-flex items-center gap-1.5">
              <span
                className={`h-1.5 w-1.5 rounded-full ${isActive ? 'bg-emerald-500' : 'bg-amber-400'}`}
                aria-hidden
              />
              {isActive ? 'Active' : 'Inactive'}
            </span>
          </div>
        </div>

        {/* Quote card — desktop only; keeps mobile above-the-fold for wallet actions */}
        <div
          className={`hidden w-full max-w-sm shrink-0 rounded-2xl px-5 py-4 shadow-md sm:block lg:ml-auto lg:w-[17.5rem] lg:text-center ${
            isLight
              ? 'bg-white text-slate-800 ring-1 ring-slate-200/80'
              : 'bg-slate-950/80 text-white ring-1 ring-white/20'
          }`}
        >
          <p className="text-[15px] font-semibold italic leading-snug sm:text-base">
            &ldquo;{theme.quote}&rdquo;
          </p>
          <p
            className={`mt-2.5 text-[10px] font-bold uppercase tracking-[0.2em] ${
              isLight ? 'text-slate-500' : 'text-white/70'
            }`}
          >
            {theme.brandLine}
          </p>
          <div
            className={`mx-auto mt-3 h-px w-10 ${isLight ? 'bg-slate-200' : 'bg-white/25'}`}
            aria-hidden
          />
          <p
            className={`mt-3 text-xs font-semibold leading-snug sm:text-[13px] ${
              isLight ? 'text-slate-700' : 'text-white/95'
            }`}
          >
            {theme.sidePhrase}
          </p>
        </div>
      </div>
    </section>
  );
};

export default GreetingBanner;
