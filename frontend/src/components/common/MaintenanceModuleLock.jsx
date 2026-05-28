import React from 'react';
import { FaLock } from 'react-icons/fa6';
import MaintenanceBanner from './MaintenanceBanner';
import { isModuleInMaintenance, MODULE_META } from '../../utils/maintenanceMode';

/**
 * Shows a prominent maintenance panel and visually locks transactional UI beneath it.
 * Navigation, page titles, and reports remain available outside this wrapper.
 *
 * @param {'pay_in' | 'payout' | 'bbps'} moduleKey
 */
const MaintenanceModuleLock = ({ maintenance, moduleKey, children, className = '' }) => {
  const locked = isModuleInMaintenance(maintenance, moduleKey);
  const meta = MODULE_META[moduleKey] || { label: 'Module' };

  return (
    <div className={`space-y-4 sm:space-y-5 ${className}`.trim()}>
      <MaintenanceBanner maintenance={maintenance} moduleKey={moduleKey} />

      <div className="relative">
        {locked ? (
          <div
            className="pointer-events-none absolute inset-0 z-20 flex items-start justify-center rounded-xl bg-slate-900/[0.04] backdrop-blur-[1px] sm:items-center sm:min-h-[12rem]"
            aria-hidden
          >
            <div className="sticky top-4 mx-4 mt-6 flex max-w-sm items-center gap-3 rounded-xl border border-slate-200/90 bg-white/95 px-4 py-3 shadow-lg ring-1 ring-slate-900/5 sm:mt-0">
              <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-amber-100 text-amber-800">
                <FaLock size={18} />
              </div>
              <div>
                <p className="text-sm font-semibold text-slate-900">{meta.label} actions locked</p>
                <p className="text-xs text-slate-600 mt-0.5">
                  Forms below are disabled until maintenance ends.
                </p>
              </div>
            </div>
          </div>
        ) : null}

        <div
          className={
            locked
              ? 'pointer-events-none select-none opacity-[0.42] grayscale-[0.35] transition-all duration-300'
              : 'transition-all duration-300'
          }
          aria-hidden={locked ? true : undefined}
        >
          {children}
        </div>
      </div>
    </div>
  );
};

export default MaintenanceModuleLock;
