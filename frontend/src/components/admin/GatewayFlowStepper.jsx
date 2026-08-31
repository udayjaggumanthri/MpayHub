import React from 'react';
import { Link } from 'react-router-dom';
import { FaArrowRight } from 'react-icons/fa6';

const FLOW_STEPS = [
  { key: 'api-master', label: 'API Master', path: '/admin/api-master' },
  { key: 'payment-gateways', label: 'Payment Gateways', path: '/admin/gateways' },
  { key: 'payin-packages', label: 'Pay-in Packages', path: '/admin/pay-in-packages' },
  { key: 'qr-accounts', label: 'QR Accounts', path: '/admin/pay-in-qr-accounts' },
  { key: 'qr-operations', label: 'QR Operations', path: '/admin/pay-in-qr-operations' },
];

const GatewayFlowStepper = ({ currentStep, subtitle }) => {
  return (
    <div className="rounded-xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900 px-3 py-3 sm:px-4 shadow-sm">
      <div className="overflow-x-auto -mx-1 px-1 pb-0.5">
        <div className="flex w-max min-w-full flex-wrap items-center gap-x-2 gap-y-2 sm:w-auto sm:min-w-0">
          {FLOW_STEPS.map((step, idx) => {
            const isCurrent = step.key === currentStep;
            return (
              <React.Fragment key={step.key}>
                <Link
                  to={step.path}
                  className={`inline-flex shrink-0 items-center rounded-lg px-2.5 py-1.5 text-[11px] font-semibold transition-colors sm:px-3 sm:text-xs ${
                    isCurrent
                      ? 'bg-indigo-100 dark:bg-indigo-900/40 text-indigo-800 dark:text-indigo-300 ring-1 ring-indigo-200 dark:ring-indigo-800'
                      : 'bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-300 hover:bg-slate-200 dark:hover:bg-slate-700'
                  }`}
                  aria-current={isCurrent ? 'page' : undefined}
                >
                  {step.label}
                </Link>
                {idx < FLOW_STEPS.length - 1 ? (
                  <FaArrowRight
                    size={10}
                    className="hidden shrink-0 text-slate-400 dark:text-slate-500 sm:block sm:size-3"
                    aria-hidden
                  />
                ) : null}
              </React.Fragment>
            );
          })}
        </div>
      </div>
      {subtitle ? (
        <p className="mt-2 text-xs leading-relaxed text-slate-500 dark:text-slate-400">{subtitle}</p>
      ) : null}
    </div>
  );
};

export default GatewayFlowStepper;
