import React, { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react';
import { systemAPI } from '../services/api';
import {
  DEFAULT_APPEARANCE,
  normalizeAppearance,
  resolveLogoUrl,
} from '../utils/appearanceDefaults';
import { setBrandingLogoUrl } from '../utils/brandingLogo';

const AppearanceContext = createContext(null);

export function AppearanceProvider({ children }) {
  const [appearance, setAppearance] = useState(() => normalizeAppearance(DEFAULT_APPEARANCE));
  const [loading, setLoading] = useState(true);

  const applyAppearance = useCallback((raw) => {
    const next = normalizeAppearance(raw);
    setAppearance(next);
    setBrandingLogoUrl(resolveLogoUrl(next.logoUrl));
    if (typeof document !== 'undefined') {
      document.title = next.siteTitle;
    }
  }, []);

  const refreshAppearance = useCallback(async () => {
    const res = await systemAPI.getAppearance();
    if (res.success && res.data?.appearance) {
      applyAppearance(res.data.appearance);
    }
    return res;
  }, [applyAppearance]);

  useEffect(() => {
    let active = true;
    (async () => {
      setLoading(true);
      const res = await systemAPI.getAppearance();
      if (!active) return;
      if (res.success && res.data?.appearance) {
        applyAppearance(res.data.appearance);
      } else {
        applyAppearance(DEFAULT_APPEARANCE);
      }
      setLoading(false);
    })();
    return () => {
      active = false;
    };
  }, [applyAppearance]);

  const value = useMemo(
    () => ({
      appearance,
      loading,
      refreshAppearance,
      logoUrl: resolveLogoUrl(appearance.logoUrl),
      siteTitle: appearance.siteTitle,
    }),
    [appearance, loading, refreshAppearance]
  );

  return <AppearanceContext.Provider value={value}>{children}</AppearanceContext.Provider>;
}

export function useAppearance() {
  const ctx = useContext(AppearanceContext);
  if (!ctx) {
    throw new Error('useAppearance must be used within AppearanceProvider');
  }
  return ctx;
}

export function useBranding() {
  const { appearance, logoUrl, siteTitle } = useAppearance();
  return {
    logoUrl,
    siteTitle,
    loginWelcomeHeading: appearance.loginWelcomeHeading,
    loginTagline: appearance.loginTagline,
    loginFooterNote: appearance.loginFooterNote,
    loginFooterPrivacyUrl: appearance.loginFooterPrivacyUrl,
    loginFooterTermsUrl: appearance.loginFooterTermsUrl,
    loginFooterRefundUrl: appearance.loginFooterRefundUrl,
    defaultTheme: appearance.defaultTheme,
    userThemeToggleEnabled: appearance.userThemeToggleEnabled,
  };
}
