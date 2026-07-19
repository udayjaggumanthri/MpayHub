export const defaultSmsForm = {
  name: '',
  provider: 'msg91',
  sender_id: '',
  enabled: true,
  is_active: false,
  api_base_url: 'https://control.msg91.com',
  route: '',
  country_code: '91',
};

export const providerLabel = (cfg) => {
  const p = (cfg?.provider || 'msg91').toLowerCase();
  if (p === 'console') return 'Legacy console (disabled)';
  return 'MSG91';
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
