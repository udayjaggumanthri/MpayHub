import React, { useCallback, useEffect, useState } from 'react';
import { FaRotate } from 'react-icons/fa6';
import { useAppearance } from '../../context/AppearanceContext';
import { adminAPI } from '../../services/api';
import { normalizeAppearance } from '../../utils/appearanceDefaults';
import Button from '../common/Button';
import Card from '../common/Card';
import Input from '../common/Input';
import BrandingLogo from '../common/BrandingLogo';

const defaultForm = () => ({
  site_title: '',
  login_welcome_heading: '',
  login_tagline: '',
  login_footer_note: '',
  login_footer_privacy_url: '',
  login_footer_terms_url: '',
  login_footer_refund_url: '',
  default_theme: 'light',
  user_theme_toggle_enabled: false,
});

const AppearanceSettings = () => {
  const { refreshAppearance } = useAppearance();
  const [form, setForm] = useState(defaultForm);
  const [logoPreview, setLogoPreview] = useState(null);
  const [logoFile, setLogoFile] = useState(null);
  const [removeLogo, setRemoveLogo] = useState(false);
  const [meta, setMeta] = useState({ updated_at: null, updated_by: null });
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');

  const applyFromApi = useCallback((raw) => {
    const normalized = normalizeAppearance(raw);
    setForm({
      site_title: normalized.siteTitle,
      login_welcome_heading: normalized.loginWelcomeHeading,
      login_tagline: normalized.loginTagline,
      login_footer_note: normalized.loginFooterNote,
      login_footer_privacy_url: normalized.loginFooterPrivacyUrl,
      login_footer_terms_url: normalized.loginFooterTermsUrl,
      login_footer_refund_url: normalized.loginFooterRefundUrl,
      default_theme: normalized.defaultTheme,
      user_theme_toggle_enabled: normalized.userThemeToggleEnabled,
    });
    setLogoPreview(normalized.logoUrl);
    setLogoFile(null);
    setRemoveLogo(false);
    setMeta({ updated_at: raw?.updated_at || null, updated_by: raw?.updated_by || null });
  }, []);

  const load = useCallback(async () => {
    setLoading(true);
    setError('');
    const res = await adminAPI.getAppearanceConfig();
    if (res.success && res.data?.appearance) {
      applyFromApi(res.data.appearance);
    } else {
      setError(res.message || 'Failed to load appearance settings.');
    }
    setLoading(false);
  }, [applyFromApi]);

  useEffect(() => {
    load();
  }, [load]);

  const handleLogoChange = (event) => {
    const file = event.target.files?.[0];
    if (!file) return;
    setLogoFile(file);
    setRemoveLogo(false);
    setLogoPreview(URL.createObjectURL(file));
  };

  const handleSave = async () => {
    setSaving(true);
    setError('');
    setSuccess('');
    const fd = new FormData();
    fd.append('site_title', form.site_title);
    fd.append('login_welcome_heading', form.login_welcome_heading);
    fd.append('login_tagline', form.login_tagline);
    fd.append('login_footer_note', form.login_footer_note);
    fd.append('login_footer_privacy_url', form.login_footer_privacy_url);
    fd.append('login_footer_terms_url', form.login_footer_terms_url);
    fd.append('login_footer_refund_url', form.login_footer_refund_url);
    fd.append('default_theme', form.default_theme);
    fd.append('user_theme_toggle_enabled', form.user_theme_toggle_enabled ? 'true' : 'false');
    if (removeLogo) fd.append('remove_logo', 'true');
    if (logoFile) fd.append('logo', logoFile);

    const res = await adminAPI.patchAppearanceConfig(fd);
    setSaving(false);
    if (!res.success) {
      setError(res.message || 'Failed to save appearance settings.');
      return;
    }
    applyFromApi(res.data?.appearance);
    await refreshAppearance();
    setSuccess('Appearance settings saved.');
  };

  if (loading) {
    return (
      <div className="max-w-4xl mx-auto py-8 text-center text-gray-600 dark:text-slate-400">
        Loading appearance settings…
      </div>
    );
  }

  return (
    <div className="max-w-4xl mx-auto space-y-6">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 dark:text-slate-100">Appearance &amp; theme</h1>
          <p className="mt-1 text-sm text-gray-600 dark:text-slate-400">
            Manage branding, login page content, and application theme defaults.
          </p>
        </div>
        <Button type="button" variant="outline" icon={FaRotate} onClick={load} size="sm">
          Refresh
        </Button>
      </div>

      {error ? (
        <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800 dark:border-red-900 dark:bg-red-950/40 dark:text-red-200">
          {error}
        </div>
      ) : null}
      {success ? (
        <div className="rounded-lg border border-green-200 bg-green-50 px-4 py-3 text-sm text-green-800 dark:border-green-900 dark:bg-green-950/40 dark:text-green-200">
          {success}
        </div>
      ) : null}

      <Card title="Branding" subtitle="Logo and site title shown across the application.">
        <div className="space-y-4">
          <Input
            label="Site title"
            value={form.site_title}
            onChange={(e) => setForm({ ...form, site_title: e.target.value })}
            placeholder="mPayHub"
          />
          <div>
            <label className="mb-2 block text-sm font-medium text-gray-700 dark:text-slate-300">
              Application logo
            </label>
            <div className="flex flex-wrap items-center gap-4">
              <div className="flex h-20 w-40 items-center justify-center rounded-lg border border-gray-200 bg-gray-50 p-2 dark:border-slate-600 dark:bg-slate-800">
                {logoPreview ? (
                  <img src={logoPreview} alt="Logo preview" className="max-h-full max-w-full object-contain" />
                ) : (
                  <BrandingLogo className="max-h-full max-w-full object-contain" />
                )}
              </div>
              <div className="space-y-2">
                <input
                  type="file"
                  accept="image/jpeg,image/png,image/webp,image/gif"
                  onChange={handleLogoChange}
                  className="block text-sm text-gray-600 dark:text-slate-300"
                />
                {logoPreview ? (
                  <button
                    type="button"
                    onClick={() => {
                      setRemoveLogo(true);
                      setLogoFile(null);
                      setLogoPreview(null);
                    }}
                    className="text-sm font-semibold text-red-600 hover:underline dark:text-red-400"
                  >
                    Remove logo
                  </button>
                ) : null}
              </div>
            </div>
          </div>
        </div>
      </Card>

      <Card title="Login page content" subtitle="Welcome text and optional footer links on the login screen.">
        <div className="space-y-4">
          <Input
            label="Welcome heading"
            value={form.login_welcome_heading}
            onChange={(e) => setForm({ ...form, login_welcome_heading: e.target.value })}
            placeholder="WELCOME TO"
          />
          <Input
            label="Tagline"
            value={form.login_tagline}
            onChange={(e) => setForm({ ...form, login_tagline: e.target.value })}
            placeholder="Driven by trust, Built for Scale"
          />
          <Input
            label="Footer note (optional)"
            value={form.login_footer_note}
            onChange={(e) => setForm({ ...form, login_footer_note: e.target.value })}
            placeholder="Additional text above footer links"
          />
          <Input
            label="Privacy policy URL (optional)"
            value={form.login_footer_privacy_url}
            onChange={(e) => setForm({ ...form, login_footer_privacy_url: e.target.value })}
            placeholder="https://"
          />
          <Input
            label="Terms & conditions URL (optional)"
            value={form.login_footer_terms_url}
            onChange={(e) => setForm({ ...form, login_footer_terms_url: e.target.value })}
            placeholder="https://"
          />
          <Input
            label="Refund & cancellation URL (optional)"
            value={form.login_footer_refund_url}
            onChange={(e) => setForm({ ...form, login_footer_refund_url: e.target.value })}
            placeholder="https://"
          />
        </div>
      </Card>

      <Card title="Theme" subtitle="Default theme and whether users can switch themes themselves.">
        <div className="space-y-4">
          <fieldset>
            <legend className="mb-2 block text-sm font-medium text-gray-700 dark:text-slate-300">
              Default theme
            </legend>
            <div className="flex flex-wrap gap-4">
              {['light', 'dark'].map((theme) => (
                <label key={theme} className="inline-flex cursor-pointer items-center gap-2 text-sm text-gray-700 dark:text-slate-200">
                  <input
                    type="radio"
                    name="default_theme"
                    value={theme}
                    checked={form.default_theme === theme}
                    onChange={() => setForm({ ...form, default_theme: theme })}
                    className="text-blue-600 dark:text-blue-400 focus:ring-blue-500"
                  />
                  <span className="capitalize">{theme}</span>
                </label>
              ))}
            </div>
          </fieldset>
          <label className="flex cursor-pointer items-start gap-3">
            <input
              type="checkbox"
              checked={form.user_theme_toggle_enabled}
              onChange={(e) => setForm({ ...form, user_theme_toggle_enabled: e.target.checked })}
              className="mt-1 rounded border-gray-300 dark:border-slate-600 text-blue-600 dark:text-blue-400 focus:ring-blue-500"
            />
            <span>
              <span className="block text-sm font-medium text-gray-900 dark:text-slate-100">
                Allow users to change theme
              </span>
              <span className="block text-sm text-gray-600 dark:text-slate-400">
                When enabled, a theme toggle appears in the header. When disabled, everyone uses the admin default.
              </span>
            </span>
          </label>
        </div>
      </Card>

      <div className="flex flex-col-reverse gap-3 sm:flex-row sm:justify-end">
        <Button type="button" variant="primary" loading={saving} onClick={handleSave}>
          Save appearance settings
        </Button>
      </div>

      {meta.updated_at ? (
        <p className="text-xs text-gray-500 dark:text-slate-500">
          Last updated: {new Date(meta.updated_at).toLocaleString()}
          {meta.updated_by?.name ? ` by ${meta.updated_by.name}` : ''}
        </p>
      ) : null}
    </div>
  );
};

export default AppearanceSettings;
