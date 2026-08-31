import React from 'react';

/**
 * Horizontal filter container with consistent spacing; children are filter controls.
 * `end` renders right-aligned actions (Apply / Reset buttons).
 */
const FilterBar = ({ children, end, className = '' }) => (
  <div
    className={`flex flex-wrap items-end gap-3 rounded-xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900 px-4 py-3 shadow-sm ${className}`}
  >
    <div className="flex flex-1 flex-wrap items-end gap-3">{children}</div>
    {end && <div className="flex items-end gap-2">{end}</div>}
  </div>
);

export default FilterBar;
