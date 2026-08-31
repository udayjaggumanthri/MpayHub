import React from 'react';

export function Field({ label, hint, required, children, className = '' }) {
  return (
    <label className={`block ${className}`}>
      <span className="text-[11px] font-semibold uppercase tracking-[0.08em] text-slate-500 dark:text-slate-400">
        {label}
        {required ? <span className="text-rose-500"> *</span> : null}
      </span>
      <div className="mt-1.5">{children}</div>
      {hint ? <p className="mt-1 text-xs text-slate-400 dark:text-slate-500">{hint}</p> : null}
    </label>
  );
}

export function inputCls(extra = '') {
  return `w-full rounded-xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900 px-3.5 py-2.5 text-sm text-slate-900 dark:text-slate-100 shadow-sm outline-none transition focus:border-blue-500 focus:ring-2 focus:ring-blue-100 disabled:bg-slate-50 dark:disabled:bg-slate-800/50 disabled:text-slate-500 dark:disabled:text-slate-500 ${extra}`;
}

export function Section({ title, subtitle, children, action }) {
  return (
    <section className="rounded-2xl border border-slate-200/80 dark:border-slate-700/80 bg-white dark:bg-slate-900 p-5 shadow-sm sm:p-6">
      <div className="mb-5 flex flex-wrap items-start justify-between gap-3 border-b border-slate-100 dark:border-slate-800 pb-4">
        <div>
          <h3 className="text-base font-semibold text-slate-900 dark:text-slate-100">{title}</h3>
          {subtitle ? <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">{subtitle}</p> : null}
        </div>
        {action || null}
      </div>
      {children}
    </section>
  );
}

export function Btn({ children, onClick, disabled, primary, type = 'button' }) {
  return (
    <button
      type={type}
      onClick={onClick}
      disabled={disabled}
      className={`rounded-xl px-4 py-2.5 text-sm font-semibold transition disabled:cursor-not-allowed disabled:opacity-50 ${
        primary
          ? 'bg-blue-600 text-white shadow-sm hover:bg-blue-700'
          : 'border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900 text-slate-800 dark:text-slate-200 hover:bg-slate-50 dark:hover:bg-slate-800'
      }`}
    >
      {children}
    </button>
  );
}

export function InlineAlert({ type, text, children }) {
  if (!text && !children) return null;
  const styles =
    type === 'error'
      ? 'border-rose-200 dark:border-rose-800 bg-rose-50 dark:bg-rose-950/40 text-rose-800 dark:text-rose-300'
      : type === 'success'
        ? 'border-emerald-200 dark:border-emerald-800 bg-emerald-50 dark:bg-emerald-950/40 text-emerald-800 dark:text-emerald-300'
        : 'border-sky-200 dark:border-sky-800 bg-sky-50 dark:bg-sky-950/40 text-sky-900 dark:text-sky-300';
  return (
    <div className={`rounded-xl border px-4 py-3 text-sm ${styles}`} role="alert">
      {text ? <p>{text}</p> : null}
      {children}
    </div>
  );
}

export function SetupPageShell({ children }) {
  return <div className="mx-auto max-w-5xl space-y-6">{children}</div>;
}

export function SetupHeader({ title, subtitle, merchantLoginId, stage, activeStepId, steps }) {
  return (
    <header className="rounded-2xl border border-slate-200/80 dark:border-slate-700/80 bg-gradient-to-br from-slate-900 via-slate-800 to-blue-900 px-6 py-6 text-white shadow-sm sm:px-8">
      <p className="text-xs font-semibold uppercase tracking-[0.18em] text-blue-200">AEPS activation</p>
      <div className="mt-2 flex flex-wrap items-end justify-between gap-4">
        <div>
          <h2 className="text-2xl font-bold tracking-tight">{title}</h2>
          {subtitle ? <p className="mt-1 max-w-xl text-sm text-slate-300">{subtitle}</p> : null}
        </div>
        <div className="rounded-xl border border-white/10 bg-white/5 dark:bg-slate-900/5 px-4 py-3 text-right text-sm">
          <p className="text-slate-300">Merchant login</p>
          <p className="font-mono font-semibold text-white">{merchantLoginId || '—'}</p>
          <p className="mt-1 text-xs capitalize text-blue-200">{String(stage || '').replaceAll('_', ' ')}</p>
        </div>
      </div>
      {steps?.length ? (
        <ol className="mt-6 grid gap-2 sm:grid-cols-3">
          {steps.map((step, idx) => {
            const done =
              (step.id === 'onboarding' && ['ekyc_pending', 'onboarding_submitted', 'active'].includes(stage)) ||
              (step.id === 'ekyc' && stage === 'active') ||
              (step.id === 'ready' && stage === 'active');
            const current = activeStepId === step.id;
            return (
              <li
                key={step.id}
                className={`rounded-xl px-3 py-2.5 text-sm ${
                  current ? 'bg-white dark:bg-slate-900 text-slate-900 dark:text-slate-100' : done ? 'bg-emerald-500/20 text-emerald-100' : 'bg-white/5 dark:bg-slate-900/5 text-slate-300'
                }`}
              >
                <span className="text-[10px] font-bold uppercase tracking-wider opacity-70">Step {idx + 1}</span>
                <p className="font-semibold">{step.label}</p>
              </li>
            );
          })}
        </ol>
      ) : null}
    </header>
  );
}
