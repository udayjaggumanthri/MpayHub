import React from 'react';

export const parseList = (result) => {
  const d = result?.data;
  if (!d) return [];
  if (Array.isArray(d)) return d;
  if (Array.isArray(d.results)) return d.results;
  return [];
};

export const roleFields = [
  { key: 'gateway_fee_pct', label: 'Gateway Fee %', help: 'Provider/network cost slice' },
  { key: 'admin_pct', label: 'Admin %', help: 'Platform administrative share' },
  { key: 'super_distributor_pct', label: 'Super Distributor %', help: 'Upline SD commission' },
  { key: 'master_distributor_pct', label: 'Master Distributor %', help: 'Upline MD commission' },
  { key: 'distributor_pct', label: 'Distributor %', help: 'Upline distributor commission' },
  {
    key: 'retailer_commission_pct',
    label: 'Retailer % (to platform)',
    help: 'Merged into Admin (platform) share on pay-in — not paid to the retailer commission wallet',
  },
];

export const firstErrorMessage = (result, fallback) => {
  const errors = result?.errors;
  if (Array.isArray(errors) && errors.length) return String(errors[0]);
  if (errors && typeof errors === 'object') {
    const first = Object.values(errors)[0];
    if (Array.isArray(first) && first.length) return String(first[0]);
    if (typeof first === 'string') return first;
  }
  return result?.message || fallback;
};

export const categoryShortLabel = (value) => {
  const map = {
    'third-party': 'Third party',
    'slpe-gold': 'SLPE Gold',
    'slpe-silver': 'SLPE Silver',
  };
  return map[value] || value || '—';
};

export const VisibleRolesSummary = ({ roles }) => {
  const r = roles || [];
  if (!r.length) {
    return <span className="text-sm text-slate-400">—</span>;
  }
  const title = r.join(' · ');
  const head = r.slice(0, 2);
  const more = r.length - 2;
  return (
    <div className="flex flex-wrap items-center gap-1.5" title={title}>
      {head.map((role) => (
        <span
          key={role}
          className="max-w-[100px] truncate px-2 py-0.5 text-xs font-medium rounded-lg bg-slate-100 text-slate-700 ring-1 ring-slate-200/70"
        >
          {role}
        </span>
      ))}
      {more > 0 && (
        <span className="shrink-0 px-2 py-0.5 text-xs font-semibold rounded-lg bg-indigo-50 text-indigo-700 ring-1 ring-indigo-100">
          +{more}
        </span>
      )}
    </div>
  );
};

export const pct = (v) => {
  const n = parseFloat(v);
  if (Number.isNaN(n)) return '0';
  return String(n);
};

export const packageCommissionStrip = (pkg) => [
  { k: 'Gw', v: pkg.gateway_fee_pct, c: 'bg-slate-500' },
  { k: 'Adm', v: pkg.admin_pct, c: 'bg-violet-500' },
  { k: 'SD', v: pkg.super_distributor_pct, c: 'bg-sky-500' },
  { k: 'MD', v: pkg.master_distributor_pct, c: 'bg-teal-500' },
  { k: 'D', v: pkg.distributor_pct, c: 'bg-emerald-500' },
  { k: 'R→P', v: pkg.retailer_commission_pct, c: 'bg-amber-500' },
];

export const packageTotalDeductionDisplay = (pkg) => {
  if (pkg.total_deduction_pct != null && pkg.total_deduction_pct !== '') {
    return String(pkg.total_deduction_pct);
  }
  const n = (k) => parseFloat(pkg[k] ?? 0);
  return (
    n('gateway_fee_pct') +
    n('admin_pct') +
    n('super_distributor_pct') +
    n('master_distributor_pct') +
    n('distributor_pct') +
    n('retailer_commission_pct')
  ).toFixed(2);
};

export const GATEWAY_CATEGORIES = [
  { value: 'slpe-gold', label: 'SLPE Gold Travel' },
  { value: 'slpe-silver', label: 'SLPE Silver Prime Edu' },
  { value: 'third-party', label: 'Third Party (Razorpay, PayU, etc.)' },
];

export const VISIBLE_ROLES = [
  'Admin',
  'Super Distributor',
  'Master Distributor',
  'Distributor',
  'Retailer',
];
