import React from 'react';

/**
 * Compact enterprise tab bar (Vercel/Monday density).
 */
const ProfileTabs = ({ tabs, activeId, onChange }) => (
  <div className="border-b border-slate-200 dark:border-slate-700">
    <nav className="-mb-px flex flex-wrap gap-1" aria-label="Profile sections">
      {tabs.map((tab) => {
        const active = tab.id === activeId;
        return (
          <button
            key={tab.id}
            type="button"
            onClick={() => onChange(tab.id)}
            className={`relative px-4 py-2.5 text-sm font-semibold transition ${
              active
                ? 'text-slate-900 dark:text-slate-100'
                : 'text-slate-500 dark:text-slate-400 hover:text-slate-800 dark:hover:text-slate-200'
            }`}
          >
            {tab.label}
            {active ? (
              <span className="absolute inset-x-2 -bottom-px h-0.5 rounded-full bg-slate-900" />
            ) : null}
          </button>
        );
      })}
    </nav>
  </div>
);

export default ProfileTabs;
