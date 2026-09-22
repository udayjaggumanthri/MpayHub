import React from 'react';
import { useBranding } from '../../context/AppearanceContext';
import { useTheme } from '../../context/ThemeContext';
import { resolveThemeLogoUrl } from '../../utils/appearanceDefaults';

/**
 * Theme-aware brand mark.
 * Uses the dark-theme logo when available and the UI is dark; otherwise the light logo.
 * Pass `forceTheme="light"|"dark"` to lock a variant (e.g. light login panels).
 */
const BrandingLogo = ({
  className = '',
  alt,
  draggable = false,
  forceTheme,
  ...props
}) => {
  const { logoUrl, logoDarkUrl, siteTitle } = useBranding();
  const { isDark: themeIsDark } = useTheme();

  const isDark =
    forceTheme === 'light' ? false : forceTheme === 'dark' ? true : themeIsDark;

  const src = resolveThemeLogoUrl({
    logoUrl,
    logoDarkUrl,
    isDark,
  });

  return (
    <img
      src={src}
      alt={alt || siteTitle}
      className={className}
      draggable={draggable}
      {...props}
    />
  );
};

export default BrandingLogo;
