/**
 * Admin / Super Admin quick-action catalog + per-user local preferences.
 * Shared by Admin and Super Admin (same ops home UI).
 */
import {
  HiAdjustmentsHorizontal,
  HiBell,
  HiChartBar,
  HiCog6Tooth,
  HiFingerPrint,
  HiMegaphone,
  HiQrCode,
  HiSquares2X2,
  HiUsers,
  HiWrenchScrewdriver,
  HiBanknotes,
  HiBuildingLibrary,
  HiClipboardDocumentList,
  HiCreditCard,
  HiEnvelope,
  HiPaintBrush,
  HiShieldCheck,
  HiDevicePhoneMobile,
  HiArrowPath,
  HiDocumentChartBar,
  HiServerStack,
} from 'react-icons/hi2';

export const ADMIN_QUICK_ICON_MAP = {
  qr: HiQrCode,
  cog: HiCog6Tooth,
  packages: HiSquares2X2,
  chart: HiChartBar,
  adjust: HiAdjustmentsHorizontal,
  megaphone: HiMegaphone,
  bell: HiBell,
  fingerprint: HiFingerPrint,
  users: HiUsers,
  wrench: HiWrenchScrewdriver,
  banknotes: HiBanknotes,
  building: HiBuildingLibrary,
  clipboard: HiClipboardDocumentList,
  card: HiCreditCard,
  envelope: HiEnvelope,
  paint: HiPaintBrush,
  shield: HiShieldCheck,
  phone: HiDevicePhoneMobile,
  refresh: HiArrowPath,
  docchart: HiDocumentChartBar,
  server: HiServerStack,
};

export const ADMIN_QUICK_TONES = [
  'from-amber-500 to-orange-600',
  'from-slate-600 to-slate-800',
  'from-indigo-600 to-violet-700',
  'from-emerald-600 to-teal-700',
  'from-cyan-600 to-sky-700',
  'from-fuchsia-600 to-pink-600',
  'from-rose-500 to-red-600',
  'from-blue-600 to-indigo-700',
  'from-violet-600 to-purple-700',
  'from-slate-700 to-indigo-900',
  'from-teal-500 to-emerald-700',
  'from-orange-500 to-rose-600',
];

/**
 * Full pool of shortcuts admins can pin to the dashboard.
 * `badgeKey: 'qrPending'` wires live QR pending count when present.
 */
export const ADMIN_QUICK_ACTION_CATALOG = [
  {
    id: 'qr-ops',
    title: 'QR Operations',
    description: 'Review manual QR pay-ins',
    path: '/admin/pay-in-qr-operations?status=PENDING_REVIEW',
    iconKey: 'qr',
    tone: 'from-amber-500 to-orange-600',
    badgeKey: 'qrPending',
  },
  {
    id: 'gateways',
    title: 'Payment Gateways',
    description: 'Configure payment rails',
    path: '/admin/gateways',
    iconKey: 'cog',
    tone: 'from-slate-600 to-slate-800',
  },
  {
    id: 'packages',
    title: 'Pay-in Packages',
    description: 'Commission & payout slabs',
    path: '/admin/pay-in-packages',
    iconKey: 'packages',
    tone: 'from-indigo-600 to-violet-700',
  },
  {
    id: 'payin-report',
    title: 'Pay-in Report',
    description: 'Load-money ledger',
    path: '/reports/payin',
    iconKey: 'chart',
    tone: 'from-emerald-600 to-teal-700',
  },
  {
    id: 'wallet-adj',
    title: 'Wallet Adjustments',
    description: 'Credit / debit corrections',
    path: '/admin/wallet-adjustments',
    iconKey: 'adjust',
    tone: 'from-cyan-600 to-sky-700',
  },
  {
    id: 'announcements',
    title: 'Announcements',
    description: 'Platform notices',
    path: '/admin/announcements',
    iconKey: 'megaphone',
    tone: 'from-fuchsia-600 to-pink-600',
  },
  {
    id: 'bbps-console',
    title: 'BBPS Console',
    description: 'Biller catalog & float',
    path: '/admin/bbps',
    iconKey: 'bell',
    tone: 'from-rose-500 to-red-600',
  },
  {
    id: 'aeps',
    title: 'AEPS',
    description: 'Aadhaar banking ops',
    path: '/aeps',
    iconKey: 'fingerprint',
    tone: 'from-blue-600 to-indigo-700',
  },
  {
    id: 'users',
    title: 'User Management',
    description: 'Directory & access',
    path: '/user-management/users',
    iconKey: 'users',
    tone: 'from-violet-600 to-purple-700',
  },
  {
    id: 'platform',
    title: 'Platform Settings',
    description: 'Maintenance & roles',
    path: '/admin/maintenance',
    iconKey: 'wrench',
    tone: 'from-slate-700 to-indigo-900',
  },
  {
    id: 'payout-report',
    title: 'Payout Report',
    description: 'Withdrawal ledger',
    path: '/reports/payout',
    iconKey: 'banknotes',
    tone: 'from-teal-500 to-emerald-700',
  },
  {
    id: 'bbps-report',
    title: 'BBPS Report',
    description: 'Bill payment ledger',
    path: '/reports/bbps',
    iconKey: 'docchart',
    tone: 'from-orange-500 to-rose-600',
  },
  {
    id: 'passbook',
    title: 'Passbook',
    description: 'Wallet statement',
    path: '/reports/passbook',
    iconKey: 'clipboard',
    tone: 'from-sky-600 to-blue-700',
  },
  {
    id: 'commission-report',
    title: 'Commission Report',
    description: 'Earnings breakdown',
    path: '/reports/commission',
    iconKey: 'chart',
    tone: 'from-lime-600 to-green-700',
  },
  {
    id: 'service-fee-tracker',
    title: 'Service Fee Tracker',
    description: 'Gateway charges (not Main)',
    path: '/reports/service-fees',
    iconKey: 'docchart',
    tone: 'from-amber-500 to-orange-600',
  },
  {
    id: 'distributed',
    title: 'Distributed Wallets',
    description: 'Network balances',
    path: '/wallets/distributed',
    iconKey: 'building',
    tone: 'from-cyan-500 to-blue-600',
  },
  {
    id: 'qr-accounts',
    title: 'QR Accounts',
    description: 'Manual QR bank accounts',
    path: '/admin/pay-in-qr-accounts',
    iconKey: 'card',
    tone: 'from-amber-600 to-yellow-700',
  },
  {
    id: 'roles',
    title: 'Roles & Permissions',
    description: 'Access control matrix',
    path: '/admin/roles-permissions',
    iconKey: 'shield',
    tone: 'from-indigo-700 to-blue-900',
  },
  {
    id: 'kyc-approvals',
    title: 'KYC Approvals',
    description: 'Pending verification queue',
    path: '/admin/kyc-approvals',
    iconKey: 'shield',
    tone: 'from-amber-500 to-orange-600',
    badgeKey: 'kycPending',
  },
  {
    id: 'appearance',
    title: 'Appearance',
    description: 'Branding & theme',
    path: '/admin/appearance',
    iconKey: 'paint',
    tone: 'from-pink-500 to-rose-600',
  },
  {
    id: 'email-notif',
    title: 'Email Notifications',
    description: 'Transactional email rules',
    path: '/admin/email-notifications',
    iconKey: 'envelope',
    tone: 'from-blue-500 to-cyan-600',
  },
  {
    id: 'sms-settings',
    title: 'SMS Settings',
    description: 'SMS gateway & templates',
    path: '/admin/sms-settings',
    iconKey: 'phone',
    tone: 'from-violet-500 to-fuchsia-600',
  },
  {
    id: 'api-master',
    title: 'API Master',
    description: 'Integration endpoints',
    path: '/admin/api-master',
    iconKey: 'server',
    tone: 'from-slate-500 to-zinc-700',
  },
  {
    id: 'aeps-merchants',
    title: 'AEPS Merchants',
    description: 'Merchant onboarding',
    path: '/admin/aeps/merchants',
    iconKey: 'fingerprint',
    tone: 'from-blue-700 to-indigo-800',
  },
  {
    id: 'aeps-recon',
    title: 'AEPS Recon',
    description: 'Settlement reconciliation',
    path: '/admin/aeps/recon',
    iconKey: 'refresh',
    tone: 'from-emerald-700 to-teal-800',
  },
  {
    id: 'cms',
    title: 'CMS',
    description: 'Cash management services',
    path: '/cms',
    iconKey: 'building',
    tone: 'from-stone-600 to-neutral-800',
  },
  {
    id: 'cms-agents',
    title: 'CMS Agents',
    description: 'Agent directory',
    path: '/admin/cms/agents',
    iconKey: 'users',
    tone: 'from-stone-500 to-amber-800',
  },
];

export const DEFAULT_ADMIN_QUICK_ACTION_IDS = [
  'kyc-approvals',
  'qr-ops',
  'gateways',
  'packages',
  'payin-report',
  'wallet-adj',
  'announcements',
  'bbps-console',
  'aeps',
  'users',
];

const STORAGE_PREFIX = 'mpayhub.adminQuickActions.v1';

function storageKey(userId) {
  return `${STORAGE_PREFIX}.${userId || 'anon'}`;
}

function catalogById() {
  return Object.fromEntries(ADMIN_QUICK_ACTION_CATALOG.map((a) => [a.id, a]));
}

/**
 * Prefs shape:
 * {
 *   order: string[],           // visible shortcut ids in display order
 *   overrides: { [id]: { title?, description? } }
 * }
 */
export function loadAdminQuickActionPrefs(userId) {
  try {
    const raw = localStorage.getItem(storageKey(userId));
    if (!raw) {
      return { order: [...DEFAULT_ADMIN_QUICK_ACTION_IDS], overrides: {} };
    }
    const parsed = JSON.parse(raw);
    const known = catalogById();
    const order = Array.isArray(parsed.order)
      ? parsed.order.filter((id) => known[id])
      : [...DEFAULT_ADMIN_QUICK_ACTION_IDS];
    const overrides =
      parsed.overrides && typeof parsed.overrides === 'object' ? parsed.overrides : {};
    return {
      order: order.length ? order : [...DEFAULT_ADMIN_QUICK_ACTION_IDS],
      overrides,
    };
  } catch {
    return { order: [...DEFAULT_ADMIN_QUICK_ACTION_IDS], overrides: {} };
  }
}

export function saveAdminQuickActionPrefs(userId, prefs) {
  try {
    localStorage.setItem(
      storageKey(userId),
      JSON.stringify({
        order: prefs.order || [],
        overrides: prefs.overrides || {},
      })
    );
  } catch {
    /* ignore quota / private mode */
  }
}

export function resetAdminQuickActionPrefs(userId) {
  try {
    localStorage.removeItem(storageKey(userId));
  } catch {
    /* ignore */
  }
  return { order: [...DEFAULT_ADMIN_QUICK_ACTION_IDS], overrides: {} };
}

/**
 * Resolve visible actions with icons, badges, navigation handlers.
 */
export function resolveAdminQuickActions({ navigate, qrStats, kycAwaiting = 0, prefs }) {
  const known = catalogById();
  const pending = qrStats?.pending_count ?? 0;
  const kycPending = Number(kycAwaiting) || 0;
  const order = prefs?.order?.length ? prefs.order : DEFAULT_ADMIN_QUICK_ACTION_IDS;
  const overrides = prefs?.overrides || {};

  return order
    .map((id) => {
      const base = known[id];
      if (!base) return null;
      const over = overrides[id] || {};
      const Icon = ADMIN_QUICK_ICON_MAP[base.iconKey] || HiSquares2X2;
      let badge = null;
      if (base.badgeKey === 'qrPending' && pending > 0) badge = pending;
      if (base.badgeKey === 'kycPending' && kycPending > 0) badge = kycPending;
      return {
        id: base.id,
        title: over.title || base.title,
        description: over.description || base.description,
        path: base.path,
        iconKey: base.iconKey,
        tone: base.tone,
        icon: Icon,
        badge,
        onClick: () => navigate(base.path),
      };
    })
    .filter(Boolean);
}

export function getAvailableToAdd(prefs) {
  const pinned = new Set(prefs?.order || []);
  return ADMIN_QUICK_ACTION_CATALOG.filter((a) => !pinned.has(a.id));
}

/** @deprecated Prefer resolveAdminQuickActions + prefs */
export function buildAdminQuickActions({ navigate, qrStats }) {
  return resolveAdminQuickActions({
    navigate,
    qrStats,
    prefs: { order: DEFAULT_ADMIN_QUICK_ACTION_IDS, overrides: {} },
  });
}
