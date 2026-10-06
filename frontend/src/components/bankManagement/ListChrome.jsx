import React from 'react';
import { FaMagnifyingGlass } from 'react-icons/fa6';
import Button from '../common/Button';

export const filterInputClass =
  'w-full h-11 rounded-lg border border-gray-300 bg-white pl-10 pr-3 text-sm text-gray-900 focus:border-transparent focus:ring-2 focus:ring-blue-500 dark:border-slate-600 dark:bg-slate-900 dark:text-slate-100';

export function FilterField({ label, children }) {
  return (
    <label className="block min-w-0">
      <span className="mb-1.5 block text-sm font-medium text-gray-700 dark:text-slate-300">{label}</span>
      <span className="relative block">
        <FaMagnifyingGlass
          className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-gray-400 dark:text-slate-500"
          size={15}
        />
        {children}
      </span>
    </label>
  );
}

export function FilterActions({ onClear, onApply }) {
  return (
    <div className="flex items-center justify-end gap-3 sm:col-span-2 xl:col-span-1">
      <Button type="button" variant="outline" onClick={onClear} className="h-11 min-w-[6.5rem]">
        Clear
      </Button>
      <Button type="button" variant="primary" onClick={onApply} className="h-11 min-w-[6.5rem]">
        Apply
      </Button>
    </div>
  );
}

export function DataTableScroll({ children }) {
  return (
    <div className="hidden max-h-[calc(100vh-14rem)] overflow-auto overscroll-x-contain rounded-lg border border-gray-200 dark:border-slate-700 md:block">
      {children}
    </div>
  );
}

export const thClass =
  'sticky top-0 z-20 whitespace-nowrap border-b border-gray-200 bg-gray-50 px-3 py-2.5 text-left text-xs font-semibold uppercase tracking-wide text-gray-500 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-400';

export const tdClass =
  'whitespace-nowrap border-b border-gray-100 bg-white px-3 py-2.5 text-sm text-gray-800 group-hover:bg-gray-50 dark:border-slate-800 dark:bg-slate-900 dark:text-slate-200 dark:group-hover:bg-slate-800';

export const actionThClass = `${thClass} right-0 z-30 text-center shadow-[-8px_0_8px_-8px_rgba(15,23,42,0.18)]`;

export const actionTdClass = `${tdClass} sticky right-0 z-10 text-center shadow-[-8px_0_8px_-8px_rgba(15,23,42,0.12)]`;
