import React from 'react';
import { FaShieldHalved } from 'react-icons/fa6';
import { HiBolt, HiCheckBadge, HiClock, HiUsers } from 'react-icons/hi2';

const FEATURES = [
  { icon: FaShieldHalved, label: 'Bank-grade Security' },
  { icon: HiBolt, label: 'Real-time Processing' },
  { icon: HiClock, label: '24×7 Support' },
  { icon: HiUsers, label: 'Trusted by thousands' },
];

const TransactionConfidenceBanner = () => (
  <section
    aria-labelledby="dash-confidence-heading"
    className="overflow-hidden rounded-2xl bg-gradient-to-r from-slate-900 via-indigo-950 to-blue-900 px-4 py-4 text-white shadow-sm sm:px-6"
  >
    <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
      <div className="flex items-start gap-3">
        <span className="inline-flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-white/12">
          <HiCheckBadge className="h-6 w-6" aria-hidden />
        </span>
        <div>
          <h2 id="dash-confidence-heading" className="text-base font-bold">
            Transact with Confidence
          </h2>
          <p className="mt-0.5 text-xs text-white/75 sm:text-sm">Secure. Reliable. Always with you.</p>
        </div>
      </div>
      <ul className="grid grid-cols-2 gap-x-4 gap-y-2 sm:grid-cols-4">
        {FEATURES.map((item) => {
          const Icon = item.icon;
          return (
            <li key={item.label} className="flex items-center gap-2 text-[11px] font-semibold text-white/85 sm:text-xs">
              <Icon className="h-4 w-4 shrink-0 text-sky-300" aria-hidden />
              {item.label}
            </li>
          );
        })}
      </ul>
    </div>
  </section>
);

export default TransactionConfidenceBanner;
