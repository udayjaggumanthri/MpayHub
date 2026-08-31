import React, { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react';
import { useLocation } from 'react-router-dom';
import { THEME_STORAGE_KEY } from '../utils/appearanceDefaults';
import { useAppearance } from './AppearanceContext';

const ThemeContext = createContext(null);

/**
 * Pre-authentication pages use the branded split-panel design, which is drawn
 * for a light background. They stay light whatever the admin default or the
 * user's stored preference is; the preference itself is left untouched.
 */
const ALWAYS_LIGHT_ROUTES = ['/login', '/forgot-password', '/forgot-mpin'];

function isAlwaysLightRoute(pathname) {
  const path = String(pathname || '').toLowerCase();
  return ALWAYS_LIGHT_ROUTES.some((route) => path === route || path.startsWith(`${route}/`));
}

function readStoredTheme() {
  try {
    const val = localStorage.getItem(THEME_STORAGE_KEY);
    return val === 'dark' || val === 'light' ? val : null;
  } catch {
    return null;
  }
}

function applyHtmlTheme(theme) {
  if (typeof document === 'undefined') return;
  const root = document.documentElement;
  if (theme === 'dark') {
    root.classList.add('dark');
  } else {
    root.classList.remove('dark');
  }
}

export function ThemeProvider({ children }) {
  const { appearance } = useAppearance();
  const { pathname } = useLocation();
  const [userTheme, setUserTheme] = useState(() => readStoredTheme());

  const forceLight = isAlwaysLightRoute(pathname);

  const effectiveTheme = useMemo(() => {
    if (forceLight) return 'light';
    if (appearance.userThemeToggleEnabled && userTheme) {
      return userTheme;
    }
    return appearance.defaultTheme === 'dark' ? 'dark' : 'light';
  }, [forceLight, appearance.defaultTheme, appearance.userThemeToggleEnabled, userTheme]);

  useEffect(() => {
    applyHtmlTheme(effectiveTheme);
  }, [effectiveTheme]);

  const setTheme = useCallback(
    (theme) => {
      if (!appearance.userThemeToggleEnabled) return;
      const next = theme === 'dark' ? 'dark' : 'light';
      setUserTheme(next);
      try {
        localStorage.setItem(THEME_STORAGE_KEY, next);
      } catch {
        /* ignore */
      }
      // The effect on `effectiveTheme` owns the html class, so forced-light
      // routes cannot be overridden from here.
    },
    [appearance.userThemeToggleEnabled]
  );

  const toggleTheme = useCallback(() => {
    setTheme(effectiveTheme === 'dark' ? 'light' : 'dark');
  }, [effectiveTheme, setTheme]);

  const value = useMemo(
    () => ({
      theme: effectiveTheme,
      isDark: effectiveTheme === 'dark',
      canToggle: appearance.userThemeToggleEnabled && !forceLight,
      setTheme,
      toggleTheme,
    }),
    [appearance.userThemeToggleEnabled, forceLight, effectiveTheme, setTheme, toggleTheme]
  );

  return <ThemeContext.Provider value={value}>{children}</ThemeContext.Provider>;
}

export function useTheme() {
  const ctx = useContext(ThemeContext);
  if (!ctx) {
    throw new Error('useTheme must be used within ThemeProvider');
  }
  return ctx;
}
