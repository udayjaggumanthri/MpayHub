import React from 'react';

export function linkedContactLabel(account) {
  const rows = Array.isArray(account?.linked_contacts) ? account.linked_contacts : [];
  if (rows.length) {
    return rows.map((row) => row.name || `Contact #${row.id}`).join(', ');
  }
  if (account?.contact_name) return account.contact_name;
  if (account?.contact) return `#${account.contact}`;
  return '—';
}

export function formatOtherContacts(contacts) {
  return (contacts || [])
    .map((row) => `${row.name || 'Contact'} (${row.phone || '—'})`)
    .join(', ');
}

const BankAccountPager = ({ page, pageSize, totalCount, onPageChange }) => {
  const total = Number(totalCount);
  const knownTotal = Number.isFinite(total) ? total : 0;
  const size = pageSize > 0 ? pageSize : 20;
  const pages = Math.max(1, Math.ceil(knownTotal / size) || 1);
  const safePage = Math.min(Math.max(page, 1), pages);

  return (
    <div className="mt-4 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
      <p className="text-sm text-gray-600 dark:text-slate-400">
        {knownTotal} account{knownTotal === 1 ? '' : 's'} · page {safePage} of {pages}
      </p>
      <div className="flex gap-2">
        <button
          type="button"
          onClick={() => onPageChange(safePage - 1)}
          disabled={safePage <= 1}
          className="px-3 py-2 text-sm rounded-lg border border-gray-300 dark:border-slate-600 text-gray-700 dark:text-slate-300 disabled:opacity-40"
        >
          Previous
        </button>
        <button
          type="button"
          onClick={() => onPageChange(safePage + 1)}
          disabled={safePage >= pages}
          className="px-3 py-2 text-sm rounded-lg border border-gray-300 dark:border-slate-600 text-gray-700 dark:text-slate-300 disabled:opacity-40"
        >
          Next
        </button>
      </div>
    </div>
  );
};

export default BankAccountPager;
