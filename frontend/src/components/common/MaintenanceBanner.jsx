import React from 'react';
import { Link } from 'react-router-dom';
import { FaClock, FaLock, FaScrewdriverWrench } from 'react-icons/fa6';
import {
  getModuleMessage,
  isModuleInMaintenance,
  MODULE_META,
} from '../../utils/maintenanceMode';

/**
 * Prominent maintenance status panel for transaction modules.
 * @param {'pay_in' | 'payout' | 'bbps'} moduleKey
 * @param {'inline' | 'compact'} variant
 */
const MaintenanceBanner = ({ maintenance, moduleKey, variant = 'inline' }) => {
  if (!isModuleInMaintenance(maintenance, moduleKey)) return null;

  const meta = MODULE_META[moduleKey] || { label: 'Service', title: 'Service paused' };
  const message = getModuleMessage(maintenance, moduleKey);

  if (variant === 'compact') {
    return (
      <div
        className="flex items-start gap-3 rounded-lg border border-amber-300/80 bg-amber-50 px-3 py-2.5 text-sm text-amber-950"
        role="alert"
        aria-live="polite"
      >
        <span className="relative mt-0.5 flex h-2.5 w-2.5 shrink-0">
          <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-amber-500 opacity-60" />
          <span className="relative inline-flex h-2.5 w-2.5 rounded-full bg-amber-600" />
        </span>
        <div>
          <p className="font-semibold">{meta.title}</p>
          <p className="mt-0.5 text-amber-900/90">{message}</p>
        </div>
      </div>
    );
  }

  return (
    <div
      className="relative overflow-hidden rounded-2xl border-2 border-amber-300/90 bg-gradient-to-br from-amber-50 via-orange-50 to-amber-100/80 shadow-sm"
      role="alert"
      aria-live="polite"
    >
      <div
        className="pointer-events-none absolute -right-8 -top-8 h-32 w-32 rounded-full bg-amber-200/40 blur-2xl"
        aria-hidden
      />
      <div
        className="pointer-events-none absolute -bottom-10 -left-6 h-28 w-28 rounded-full bg-orange-200/30 blur-2xl"
        aria-hidden
      />

      <div className="relative flex flex-col gap-4 p-4 sm:flex-row sm:items-start sm:gap-5 sm:p-5">
        <div className="flex shrink-0 items-center justify-center">
          <div className="relative">
            <span className="absolute -inset-1 animate-pulse rounded-2xl bg-amber-400/30" aria-hidden />
            <div className="relative flex h-14 w-14 items-center justify-center rounded-2xl bg-gradient-to-br from-amber-500 to-orange-600 text-white shadow-md">
              <FaScrewdriverWrench size={26} aria-hidden />
            </div>
          </div>
        </div>

        <div className="min-w-0 flex-1 space-y-2">
          <div className="flex flex-wrap items-center gap-2">
            <span className="inline-flex items-center gap-1.5 rounded-full border border-amber-400/60 bg-white/80 px-2.5 py-1 text-xs font-bold uppercase tracking-wide text-amber-900 shadow-sm">
              <span className="relative flex h-2 w-2">
                <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-amber-500 opacity-75" />
                <span className="relative inline-flex h-2 w-2 rounded-full bg-amber-600" />
              </span>
              Maintenance in progress
            </span>
            <span className="inline-flex items-center gap-1 rounded-full bg-amber-900/10 px-2 py-0.5 text-xs font-medium text-amber-950">
              <FaLock size={11} aria-hidden />
              {meta.label}
            </span>
          </div>

          <h2 className="text-lg font-bold text-amber-950 sm:text-xl">{meta.title}</h2>
          <p className="text-sm leading-relaxed text-amber-950/90">{message}</p>

          <div className="flex flex-wrap items-center gap-x-4 gap-y-1 pt-1 text-xs text-amber-900/80">
            <span className="inline-flex items-center gap-1.5">
              <FaClock size={12} aria-hidden />
              New transactions in this module are paused for all users.
            </span>
            {meta.reportPath ? (
              <Link
                to={meta.reportPath}
                className="font-semibold text-amber-900 underline decoration-amber-400/80 underline-offset-2 hover:text-amber-950"
              >
                View past {meta.reportLabel.toLowerCase()} →
              </Link>
            ) : null}
          </div>
        </div>
      </div>
    </div>
  );
};

export default MaintenanceBanner;
