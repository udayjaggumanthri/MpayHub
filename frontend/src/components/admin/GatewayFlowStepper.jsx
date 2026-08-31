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
    <div className="rounded-xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900 px-4 py-3 shadow-sm">
      <div className="flex flex-wrap items-center gap-2">
        {FLOW_STEPS.map((step, idx) => {
          const isCurrent = step.key === currentStep;
          return (
            <React.Fragment key={step.key}>
              <Link
                to={step.path}
                className={`inline-flex items-center rounded-lg px-3 py-1.5 text-xs font-semibold transition-colors ${
                  isCurrent
                    ? 'bg-indigo-100 dark:bg-indigo-900/40 text-indigo-800 dark:text-indigo-300 ring-1 ring-indigo-200 dark:ring-indigo-800'
                    : 'bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-300 hover:bg-slate-200 dark:hover:bg-slate-700'
                }`}
                aria-current={isCurrent ? 'page' : undefined}
              >
                {step.label}
              </Link>
              {idx < FLOW_STEPS.length - 1 ? (
                <FaArrowRight size={12} className="text-slate-400 dark:text-slate-500" />
              ) : null}
            </React.Fragment>
          );
        })}
      </div>
      {subtitle ? <p className="mt-2 text-xs text-slate-500 dark:text-slate-400">{subtitle}</p> : null}
    </div>
  );
};

export default GatewayFlowStepper;
