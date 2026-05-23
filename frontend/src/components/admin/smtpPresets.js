export const SMTP_PRESETS = {
  gmail_tls: {
    label: 'Gmail — 587 TLS',
    host: 'smtp.gmail.com',
    port: 587,
    use_tls: true,
    use_ssl: false,
  },
  gmail_ssl: {
    label: 'Gmail — 465 SSL',
    host: 'smtp.gmail.com',
    port: 465,
    use_tls: false,
    use_ssl: true,
  },
  zoho_tls: {
    label: 'Zoho — 587 TLS',
    host: 'smtppro.zoho.in',
    port: 587,
    use_tls: true,
    use_ssl: false,
  },
  zoho_ssl: {
    label: 'Zoho — 465 SSL',
    host: 'smtppro.zoho.in',
    port: 465,
    use_tls: false,
    use_ssl: true,
  },
  outlook: {
    label: 'Outlook / Microsoft 365 — 587 TLS',
    host: 'smtp.office365.com',
    port: 587,
    use_tls: true,
    use_ssl: false,
  },
};

export const defaultSmtpForm = {
  name: '',
  host: '',
  port: 587,
  use_tls: true,
  use_ssl: false,
  username: '',
  from_email: '',
  enabled: true,
  is_active: false,
};

export const applySmtpPreset = (presetKey, setForm) => {
  const preset = SMTP_PRESETS[presetKey];
  if (!preset) return;
  setForm((p) => ({
    ...p,
    host: preset.host,
    port: preset.port,
    use_tls: preset.use_tls,
    use_ssl: preset.use_ssl,
  }));
};

export const providerLabel = (cfg) => {
  const host = (cfg?.host || '').toLowerCase();
  if (host.includes('gmail')) return 'Gmail';
  if (host.includes('zoho')) return 'Zoho';
  if (host.includes('office365') || host.includes('outlook')) return 'Outlook';
  if (host) return host.split('.')[0] || 'SMTP';
  return 'Custom';
};

export const formatApiErrors = (errors) => {
  if (!errors || typeof errors !== 'object') return '';
  const parts = [];
  Object.entries(errors).forEach(([field, msgs]) => {
    const text = Array.isArray(msgs) ? msgs.join(', ') : String(msgs);
    parts.push(`${field}: ${text}`);
  });
  return parts.join(' · ');
};
