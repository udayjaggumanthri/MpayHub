import React from 'react';

/**
 * Shared tab strip. `tabs`: [{ id, label, count? }], controlled via `active` + `onChange`.
 */
const Tabs = ({ tabs = [], active, onChange, className = '' }) => (
  <div className={`flex flex-wrap gap-1 rounded-lg bg-slate-100 dark:bg-slate-800 p-1 ${className}`}>
    {tabs.map((tab) => {
      const isActive = tab.id === active;
      return (
        <button
          key={tab.id}
          type="button"
          onClick={() => onChange && onChange(tab.id)}
          className={`rounded-md px-3 py-1.5 text-sm font-semibold transition ${
            isActive ? 'bg-white dark:bg-slate-700 text-slate-900 dark:text-slate-100 shadow-sm' : 'text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-slate-100'
          }`}
        >
          {tab.label}
          {tab.count != null && (
            <span
              className={`ml-1.5 rounded-full px-1.5 py-0.5 text-xs font-semibold ${
                isActive ? 'bg-blue-50 dark:bg-blue-950/40 text-blue-700 dark:text-blue-300' : 'bg-slate-200 dark:bg-slate-700 text-slate-600 dark:text-slate-400'
              }`}
            >
              {tab.count}
            </span>
          )}
        </button>
      );
    })}
  </div>
);

export default Tabs;
