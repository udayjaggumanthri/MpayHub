export const toneClass = (tone) => {
  if (tone === 'success') return 'border-emerald-200 dark:border-emerald-800 bg-emerald-50 dark:bg-emerald-950/40 text-emerald-900 dark:text-emerald-300';
  if (tone === 'warning') return 'border-amber-300 dark:border-amber-800 bg-amber-50 dark:bg-amber-950/40 text-amber-950 dark:text-amber-200';
  if (tone === 'error') return 'border-red-200 dark:border-red-800 bg-red-50 dark:bg-red-950/40 text-red-900 dark:text-red-300';
  return 'border-slate-200 dark:border-slate-700 bg-slate-50 dark:bg-slate-800/50 text-slate-800 dark:text-slate-200';
};

export const statusBadgeClass = (status) => {
  const s = String(status || '').toUpperCase();
  if (s === 'MANUAL_ESCALATION_REQUIRED') return 'bg-amber-100 dark:bg-amber-900/40 text-amber-900 dark:text-amber-300 border-amber-300 dark:border-amber-800';
  if (s === 'ASSIGNED' || s === 'OPEN') return 'bg-blue-100 dark:bg-blue-900/40 text-blue-900 dark:text-blue-300 border-blue-300 dark:border-blue-800';
  if (s === 'RESOLVED' || s === 'CLOSED') return 'bg-emerald-100 dark:bg-emerald-900/40 text-emerald-900 dark:text-emerald-300 border-emerald-300 dark:border-emerald-800';
  return 'bg-gray-100 dark:bg-slate-800 text-gray-800 dark:text-slate-200 border-gray-300 dark:border-slate-600';
};

export const statusLabel = (status) => {
  const s = String(status || '').toUpperCase();
  if (s === 'MANUAL_ESCALATION_REQUIRED') return 'Needs manual escalation';
  if (s === 'ASSIGNED' || s === 'OPEN') return 'Open';
  if (s === 'RESOLVED') return 'Resolved';
  if (s === 'CLOSED') return 'Closed';
  if (s === 'REJECTED') return 'Rejected';
  return s ? s.replaceAll('_', ' ').toLowerCase().replace(/\b\w/g, (c) => c.toUpperCase()) : 'Unknown';
};

export const toUserMessage = (msg) => {
  const raw = String(msg || '').trim();
  if (!raw) return '';
  if (/manual escalation/i.test(raw) || /cms@billavenue\.com/i.test(raw)) {
    return 'Your complaint is saved. The provider needs manual escalation for this case. Please contact support to proceed.';
  }
  return raw;
};
