import React from 'react';

/**
 * Shared tab strip. `tabs`: [{ id, label, count? }], controlled via `active` + `onChange`.
 */
const Tabs = ({ tabs = [], active, onChange, className = '' }) => (
  <div className={`flex flex-wrap gap-1 rounded-lg bg-slate-100 p-1 ${className}`}>
    {tabs.map((tab) => {
      const isActive = tab.id === active;
      return (
        <button
          key={tab.id}
          type="button"
          onClick={() => onChange && onChange(tab.id)}
          className={`rounded-md px-3 py-1.5 text-sm font-semibold transition ${
            isActive ? 'bg-white text-slate-900 shadow-sm' : 'text-slate-600 hover:text-slate-900'
          }`}
        >
          {tab.label}
          {tab.count != null && (
            <span
              className={`ml-1.5 rounded-full px-1.5 py-0.5 text-xs font-semibold ${
                isActive ? 'bg-blue-50 text-blue-700' : 'bg-slate-200 text-slate-600'
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
