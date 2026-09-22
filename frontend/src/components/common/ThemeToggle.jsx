import React from 'react';
import { FiMoon, FiSun } from 'react-icons/fi';
import { useTheme } from '../../context/ThemeContext';

/**
 * Compact icon button (header) or labeled light/dark control (mobile menu).
 * Renders nothing when theme switching is disabled by appearance settings.
 */
const ThemeToggle = ({ className = '', variant = 'icon' }) => {
  const { isDark, toggleTheme, setTheme, canToggle } = useTheme();

  if (!canToggle) return null;

  if (variant === 'segmented') {
    return (
      <div
        className={`inline-flex shrink-0 rounded-lg border border-gray-300 bg-gray-100 p-0.5 dark:border-slate-600 dark:bg-slate-800 ${className}`}
        role="group"
        aria-label="Theme"
      >
        <button
          type="button"
          onClick={() => setTheme('light')}
          aria-pressed={!isDark}
          aria-label="Light theme"
          title="Light theme"
          className={`inline-flex h-8 w-8 items-center justify-center rounded-md transition focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-500 ${
            !isDark
              ? 'bg-white text-slate-900 shadow-sm dark:bg-slate-700 dark:text-white'
              : 'text-slate-500 hover:text-slate-800 dark:text-slate-400 dark:hover:text-slate-200'
          }`}
        >
          <FiSun className="h-4 w-4" aria-hidden />
        </button>
        <button
          type="button"
          onClick={() => setTheme('dark')}
          aria-pressed={isDark}
          aria-label="Dark theme"
          title="Dark theme"
          className={`inline-flex h-8 w-8 items-center justify-center rounded-md transition focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-500 ${
            isDark
              ? 'bg-white text-slate-900 shadow-sm dark:bg-slate-700 dark:text-white'
              : 'text-slate-500 hover:text-slate-800 dark:text-slate-400 dark:hover:text-slate-200'
          }`}
        >
          <FiMoon className="h-4 w-4" aria-hidden />
        </button>
      </div>
    );
  }

  return (
    <button
      type="button"
      onClick={toggleTheme}
      aria-label={isDark ? 'Switch to light theme' : 'Switch to dark theme'}
      title={isDark ? 'Switch to light theme' : 'Switch to dark theme'}
      className={`inline-flex h-9 w-9 shrink-0 items-center justify-center rounded-lg border border-gray-300 bg-white text-gray-700 shadow-sm transition hover:bg-gray-50 focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-500 focus-visible:ring-offset-2 motion-reduce:transition-none dark:border-slate-600 dark:bg-slate-800 dark:text-slate-100 dark:hover:bg-slate-700 ${className}`}
    >
      {isDark ? <FiSun className="h-4 w-4" aria-hidden /> : <FiMoon className="h-4 w-4" aria-hidden />}
    </button>
  );
};

export default ThemeToggle;
