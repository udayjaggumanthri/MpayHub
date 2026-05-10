export const toneClass = (tone) => {
  if (tone === 'success') return 'border-emerald-200 bg-emerald-50 text-emerald-900';
  if (tone === 'warning') return 'border-amber-300 bg-amber-50 text-amber-950';
  if (tone === 'error') return 'border-red-200 bg-red-50 text-red-900';
  return 'border-slate-200 bg-slate-50 text-slate-800';
};

export const statusBadgeClass = (status) => {
  const s = String(status || '').toUpperCase();
  if (s === 'MANUAL_ESCALATION_REQUIRED') return 'bg-amber-100 text-amber-900 border-amber-300';
  if (s === 'ASSIGNED' || s === 'OPEN') return 'bg-blue-100 text-blue-900 border-blue-300';
  if (s === 'RESOLVED' || s === 'CLOSED') return 'bg-emerald-100 text-emerald-900 border-emerald-300';
  return 'bg-gray-100 text-gray-800 border-gray-300';
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
