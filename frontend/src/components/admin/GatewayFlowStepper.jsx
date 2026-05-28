import React from 'react';
import { Link } from 'react-router-dom';
import { FaArrowRight } from 'react-icons/fa6';

const FLOW_STEPS = [
  { key: 'api-master', label: 'API Master', path: '/admin/api-master' },
  { key: 'payment-gateways', label: 'Payment Gateways', path: '/admin/gateways' },
  { key: 'payin-packages', label: 'Pay-in Packages', path: '/admin/pay-in-packages' },
];

const GatewayFlowStepper = ({ currentStep, subtitle }) => {
  return (
    <div className="rounded-xl border border-slate-200 bg-white px-4 py-3 shadow-sm">
      <div className="flex flex-wrap items-center gap-2">
        {FLOW_STEPS.map((step, idx) => {
          const isCurrent = step.key === currentStep;
          return (
            <React.Fragment key={step.key}>
              <Link
                to={step.path}
                className={`inline-flex items-center rounded-lg px-3 py-1.5 text-xs font-semibold transition-colors ${
                  isCurrent
                    ? 'bg-indigo-100 text-indigo-800 ring-1 ring-indigo-200'
                    : 'bg-slate-100 text-slate-700 hover:bg-slate-200'
                }`}
                aria-current={isCurrent ? 'page' : undefined}
              >
                {step.label}
              </Link>
              {idx < FLOW_STEPS.length - 1 ? (
                <FaArrowRight size={12} className="text-slate-400" />
              ) : null}
            </React.Fragment>
          );
        })}
      </div>
      {subtitle ? <p className="mt-2 text-xs text-slate-500">{subtitle}</p> : null}
    </div>
  );
};

export default GatewayFlowStepper;
