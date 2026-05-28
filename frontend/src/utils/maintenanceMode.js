/** Default maintenance snapshot when API has not loaded yet. */
export const DEFAULT_MAINTENANCE = {
  pay_in: { enabled: true, message: '' },
  payout: { enabled: true, message: '' },
  bbps: { enabled: true, message: '' },
};

export function normalizeMaintenance(raw) {
  if (!raw || typeof raw !== 'object') return { ...DEFAULT_MAINTENANCE };
  const pick = (key) => {
    const block = raw[key] || {};
    return {
      enabled: block.enabled !== false,
      message: String(block.message || '').trim(),
    };
  };
  return {
    pay_in: pick('pay_in'),
    payout: pick('payout'),
    bbps: pick('bbps'),
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
