/** Default maintenance snapshot when API has not loaded yet. */
export const DEFAULT_MAINTENANCE = {
  pay_in: { enabled: true, message: '' },
  payout: { enabled: true, message: '' },
  bbps: { enabled: true, message: '' },
  aeps: { enabled: false, message: '' },
};

export function normalizeMaintenance(raw) {
  if (!raw || typeof raw !== 'object') return { ...DEFAULT_MAINTENANCE };
  const pick = (key, defaultEnabled = true) => {
    const block = raw[key] || {};
    const enabled =
      block.enabled === undefined || block.enabled === null
        ? defaultEnabled
        : block.enabled !== false;
    return {
      enabled,
      message: String(block.message || '').trim(),
    };
  };
  return {
    pay_in: pick('pay_in', true),
    payout: pick('payout', true),
    bbps: pick('bbps', true),
    aeps: pick('aeps', false),
    updated_at: raw.updated_at || null,
    reason_internal: raw.reason_internal || '',
    updated_by: raw.updated_by || null,
  };
}

export function isModuleEnabled(maintenance, moduleKey) {
  const m = maintenance?.[moduleKey];
  return m?.enabled !== false;
}

export function getModuleMessage(maintenance, moduleKey) {
  const m = maintenance?.[moduleKey];
  return (
    m?.message ||
    'This service is temporarily unavailable due to maintenance. Please try again later.'
  );
}

/** UI copy and navigation hints per module. */
export const MODULE_META = {
  pay_in: {
    label: 'Pay-in',
    title: 'Load Money paused',
    reportLabel: 'Pay-in reports',
    reportPath: '/reports/payin',
  },
  payout: {
    label: 'Payout',
    title: 'Payout paused',
    reportLabel: 'Payout reports',
    reportPath: '/reports/payout',
  },
  bbps: {
    label: 'BBPS',
    title: 'Bill payments paused',
    reportLabel: 'BBPS reports',
    reportPath: '/reports/bbps',
  },
  aeps: {
    label: 'AEPS',
    title: 'AEPS paused',
    reportLabel: 'AEPS reports',
    reportPath: '/aeps/reports',
  },
};

export function isModuleInMaintenance(maintenance, moduleKey) {
  return Boolean(maintenance && !isModuleEnabled(maintenance, moduleKey));
}

export function isMaintenanceError(result) {
  if (result?.error?.code === 'MODULE_MAINTENANCE') return result.error;
  const detail = result?.errors?.detail || result?.detail;
  if (typeof detail === 'object' && detail?.code === 'MODULE_MAINTENANCE') return detail;
  if (result?.code === 'MODULE_MAINTENANCE') return result;
  return null;
}
