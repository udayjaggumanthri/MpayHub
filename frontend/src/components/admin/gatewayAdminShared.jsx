import React from 'react';

export const parseList = (result) => {
  const d = result?.data;
  if (!d) return [];
  if (Array.isArray(d)) return d;
  if (Array.isArray(d.results)) return d.results;
  return [];
};

export const roleFields = [
  { key: 'gateway_fee_pct', label: 'Default gateway fee %', help: 'Fallback when a rail has no override' },
  { key: 'admin_pct', label: 'Admin %', help: 'Platform administrative share' },
  { key: 'super_distributor_pct', label: 'Super Distributor %', help: 'Upline SD commission' },
  { key: 'master_distributor_pct', label: 'Master Distributor %', help: 'Upline MD commission' },
  { key: 'distributor_pct', label: 'Distributor %', help: 'Upline distributor commission' },
];

/** Commission fields for pay-in package form (gateway fee is per-rail only). */
export const packageCommissionFields = [
  { key: 'admin_pct', label: 'Admin %', help: 'Platform administrative share' },
  { key: 'super_distributor_pct', label: 'Super Distributor %', help: 'Upline SD commission' },
  { key: 'master_distributor_pct', label: 'Master Distributor %', help: 'Upline MD commission' },
  { key: 'distributor_pct', label: 'Distributor %', help: 'Upline distributor commission' },
];

export const maxRailFeeFromPackage = (pkg) => {
  if (!pkg) return 0;
  if (pkg.max_rail_gateway_fee_pct != null && pkg.max_rail_gateway_fee_pct !== '') {
    return parseFloat(pkg.max_rail_gateway_fee_pct);
  }
  const fees = [];
  (pkg.package_gateways || []).forEach((g) => {
    const f = g.effective_gateway_fee_pct ?? g.gateway_fee_pct;
    if (f != null && f !== '') fees.push(parseFloat(f));
  });
  (pkg.package_qr_accounts || []).forEach((q) => {
    const f = q.effective_gateway_fee_pct ?? q.gateway_fee_pct;
    if (f != null && f !== '') fees.push(parseFloat(f));
  });
  if (fees.length) return Math.max(...fees);
  return parseFloat(pkg.gateway_fee_pct || 0);
};

export const packageCommissionStrip = (pkg) => [
  { k: 'Rail', v: maxRailFeeFromPackage(pkg), c: 'bg-slate-500' },
  { k: 'Adm', v: pkg.admin_pct, c: 'bg-violet-500' },
  { k: 'SD', v: pkg.super_distributor_pct, c: 'bg-sky-500' },
  { k: 'MD', v: pkg.master_distributor_pct, c: 'bg-teal-500' },
  { k: 'D', v: pkg.distributor_pct, c: 'bg-emerald-500' },
];

export const packageTotalDeductionDisplay = (pkg) => {
  if (pkg.total_deduction_pct != null && pkg.total_deduction_pct !== '') {
    return String(pkg.total_deduction_pct);
  }
  const n = (k) => parseFloat(pkg[k] ?? 0);
  return (
    maxRailFeeFromPackage(pkg) +
    n('admin_pct') +
    n('super_distributor_pct') +
    n('master_distributor_pct') +
    n('distributor_pct')
  ).toFixed(2);
};

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
    return <span className="text-sm text-slate-400 dark:text-slate-500">—</span>;
  }
  const title = r.join(' · ');
  const head = r.slice(0, 2);
  const more = r.length - 2;
  return (
    <div className="flex flex-wrap items-center gap-1.5" title={title}>
      {head.map((role) => (
        <span
          key={role}
          className="max-w-[100px] truncate px-2 py-0.5 text-xs font-medium rounded-lg bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-300 ring-1 ring-slate-200/70 dark:ring-slate-700/70"
        >
          {role}
        </span>
      ))}
      {more > 0 && (
        <span className="shrink-0 px-2 py-0.5 text-xs font-semibold rounded-lg bg-indigo-50 dark:bg-indigo-950/40 text-indigo-700 dark:text-indigo-300 ring-1 ring-indigo-100 dark:ring-indigo-900">
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
