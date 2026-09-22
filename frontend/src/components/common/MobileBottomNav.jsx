import React from 'react';
import { NavLink } from 'react-router-dom';
import {
  HiHome,
  HiSquares2X2,
  HiChartBar,
  HiUserCircle,
} from 'react-icons/hi2';

const TABS = [
  { to: '/dashboard', label: 'Home', icon: HiHome, end: true },
  { to: '/services', label: 'Services', icon: HiSquares2X2 },
  { to: '/reports', label: 'Reports', icon: HiChartBar },
  { to: '/profile', label: 'Profile', icon: HiUserCircle },
];

/**
 * Mobile-only bottom navigation matching the reference (Home / Services / Reports / Profile).
 * Hidden from lg+ where the sidebar is the primary nav.
 */
const MobileBottomNav = () => (
  <nav
    aria-label="Primary"
    className="fixed inset-x-0 bottom-0 z-40 border-t border-slate-200/90 bg-white/95 pb-[env(safe-area-inset-bottom)] shadow-[0_-4px_20px_rgba(15,23,42,0.06)] backdrop-blur dark:border-slate-800 dark:bg-slate-950/95 lg:hidden"
  >
    <ul className="mx-auto grid max-w-lg grid-cols-4 px-1 pt-1">
      {TABS.map((tab) => {
        const Icon = tab.icon;
        return (
          <li key={tab.to}>
            <NavLink
              to={tab.to}
              end={tab.end}
              className={({ isActive }) =>
                `flex min-h-[52px] flex-col items-center justify-center gap-0.5 rounded-xl px-1 text-[10px] font-semibold transition ${
                  isActive
                    ? 'text-blue-600 dark:text-blue-400'
                    : 'text-slate-500 hover:text-slate-800 dark:text-slate-400 dark:hover:text-slate-200'
                }`
              }
            >
              {({ isActive }) => (
                <>
                  <span
                    className={`inline-flex h-8 w-8 items-center justify-center rounded-xl ${
                      isActive ? 'bg-blue-50 dark:bg-blue-950/50' : ''
                    }`}
                  >
                    <Icon className="h-5 w-5" aria-hidden />
                  </span>
                  <span>{tab.label}</span>
                </>
              )}
            </NavLink>
          </li>
        );
      })}
    </ul>
  </nav>
);

export default MobileBottomNav;
