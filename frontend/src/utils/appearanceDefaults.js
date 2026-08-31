export const DEFAULT_LOGO_SRC = `${process.env.PUBLIC_URL || ''}/images/logo.png`;
export const DEFAULT_SITE_TITLE = 'mPayHub';
export const DEFAULT_LOGIN_WELCOME_HEADING = 'WELCOME TO';
export const DEFAULT_LOGIN_TAGLINE = 'Driven by trust, Built for Scale';

export const THEME_STORAGE_KEY = 'mpayhub_theme';

export const DEFAULT_APPEARANCE = {
  site_title: DEFAULT_SITE_TITLE,
  logo_url: null,
  login_welcome_heading: DEFAULT_LOGIN_WELCOME_HEADING,
  login_tagline: DEFAULT_LOGIN_TAGLINE,
  login_footer_note: '',
  login_footer_privacy_url: '',
  login_footer_terms_url: '',
  login_footer_refund_url: '',
  default_theme: 'light',
  user_theme_toggle_enabled: false,
};

export function normalizeAppearance(raw) {
  const src = raw || {};
  return {
    siteTitle: (src.site_title || '').trim() || DEFAULT_SITE_TITLE,
    logoUrl: (src.logo_url || '').trim() || null,
    loginWelcomeHeading: (src.login_welcome_heading || '').trim() || DEFAULT_LOGIN_WELCOME_HEADING,
    loginTagline: (src.login_tagline || '').trim() || DEFAULT_LOGIN_TAGLINE,
    loginFooterNote: (src.login_footer_note || '').trim(),
    loginFooterPrivacyUrl: (src.login_footer_privacy_url || '').trim(),
    loginFooterTermsUrl: (src.login_footer_terms_url || '').trim(),
    loginFooterRefundUrl: (src.login_footer_refund_url || '').trim(),
    defaultTheme: src.default_theme === 'dark' ? 'dark' : 'light',
    userThemeToggleEnabled: Boolean(src.user_theme_toggle_enabled),
    updatedAt: src.updated_at || null,
  };
}

export function resolveLogoUrl(logoUrl) {
  return logoUrl || DEFAULT_LOGO_SRC;
}
