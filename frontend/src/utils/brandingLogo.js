import { DEFAULT_LOGO_SRC } from './appearanceDefaults';

let cachedLogoUrl = DEFAULT_LOGO_SRC;
let cachedLogoDarkUrl = null;

export function setBrandingLogoUrl(logoUrl, logoDarkUrl = null) {
  cachedLogoUrl = logoUrl || DEFAULT_LOGO_SRC;
  cachedLogoDarkUrl = logoDarkUrl || null;
}

export function getBrandingLogoUrl({ preferDark = false } = {}) {
  if (preferDark && cachedLogoDarkUrl) return cachedLogoDarkUrl;
  return cachedLogoUrl;
}

export function getBrandingLogoDarkUrl() {
  return cachedLogoDarkUrl;
}
