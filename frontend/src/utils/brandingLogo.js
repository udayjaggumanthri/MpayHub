import { DEFAULT_LOGO_SRC } from './appearanceDefaults';

let cachedLogoUrl = DEFAULT_LOGO_SRC;

export function setBrandingLogoUrl(logoUrl) {
  cachedLogoUrl = logoUrl || DEFAULT_LOGO_SRC;
}

export function getBrandingLogoUrl() {
  return cachedLogoUrl;
}
