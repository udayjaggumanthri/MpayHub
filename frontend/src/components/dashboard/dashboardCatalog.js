/**
 * Role-, access-, and maintenance-aware tile registry for the dashboard.
 *
 * Channel "Payments & services" shows transactional products.
 * Load Money / Payout are primary actions beside the main wallet card.
 */
import {
  HiArrowDownTray,
  HiArrowUpTray,
  HiBuildingLibrary,
  HiChartBar,
  HiCog6Tooth,
  HiFingerPrint,
  HiMegaphone,
  HiPaperAirplane,
  HiPlus,
  HiQrCode,
  HiSquares2X2,
} from 'react-icons/hi2';
import bMnemonicPrimary from '../../assets/bbps/b-mnemonic-primary.svg';
import {
  canUsePayInModule,
  userMayPayOut,
} from '../../utils/accessControl';
import { isModuleEnabled } from '../../utils/maintenanceMode';
import {
  getMenuForRole,
  isAdminOperationalIsolationRole,
  isFinancialTxBlockedRole,
} from '../../utils/rolePermissions';

const NOTE_PAUSED = 'Paused';
const NOTE_UNAVAILABLE = 'Unavailable';

/** Flat list of every path present in a role's menu, including submenus. */
function menuPathsForRole(role) {
  const items = getMenuForRole(role) || [];
  const paths = [];
  items.forEach((item) => {
    if (item?.path) paths.push(item.path);
    (item?.submenu || []).forEach((sub) => {
      if (sub?.path) paths.push(sub.path);
    });
  });
  return paths;
}

/** True when the role's menu contains the path or anything beneath it. */
export function roleHasPath(role, path) {
  return menuPathsForRole(role).some((p) => p === path || p.startsWith(`${path}/`));
}

function moduleState(maintenance, moduleKey, accountAllowed = true) {
  if (!isModuleEnabled(maintenance, moduleKey)) {
    return { disabled: true, note: NOTE_PAUSED };
  }
  if (!accountAllowed) {
    return { disabled: true, note: NOTE_UNAVAILABLE };
  }
  return { disabled: false, note: '' };
}

/**
 * Money actions rendered inside the greeting banner.
 * @param {{ user: object, maintenance: object, navigate: Function, qrStats: object|null }} ctx
 */
export function buildPrimaryActions({ user, maintenance, navigate, qrStats }) {
  const role = user?.role || '';

  if (isAdminOperationalIsolationRole(role)) {
    const pending = qrStats?.pending_count ?? 0;
    return [
      {
        id: 'admin-qr-ops',
        title: 'QR queue',
        description: 'Review manual QR pay-in submissions',
        icon: HiQrCode,
        badge: pending > 0 ? pending : null,
        onClick: () => navigate('/admin/pay-in-qr-operations?status=PENDING_REVIEW'),
      },
      {
        id: 'admin-payin-report',
        title: 'Pay-in report',
        description: 'Review load-money transactions',
        icon: HiChartBar,
        onClick: () => navigate('/reports/payin'),
      },
    ];
  }

  if (isFinancialTxBlockedRole(role)) return [];

  const payIn = moduleState(maintenance, 'pay_in', canUsePayInModule(user, maintenance));
  const payOut = moduleState(maintenance, 'payout', userMayPayOut(user));

  return [
    {
      id: 'load-money',
      title: 'Load Money',
      shortLabel: 'Add funds',
      description: 'Add funds to your wallet instantly and securely',
      icon: HiPlus,
      onClick: () => navigate('/fund-management/load-money'),
      ...payIn,
    },
    {
      id: 'payout',
      title: 'Payout',
      shortLabel: 'Send to bank',
      description: 'Transfer to bank account quickly and safely',
      icon: HiPaperAirplane,
      onClick: () => navigate('/fund-management/payout'),
      ...payOut,
    },
  ];
}

/**
 * Compact service tiles.
 * Channel: Pay Bill + AEPS + CMS (and Load Money / Payout when not already in banner).
 * Admin: platform ops shortcuts.
 * @param {{ user: object, maintenance: object, navigate: Function, qrStats: object|null, includeFundActions?: boolean }} ctx
 */
export function buildServiceTiles({
  user,
  maintenance,
  navigate,
  qrStats,
  includeFundActions = false,
}) {
  const role = user?.role || '';

  if (isAdminOperationalIsolationRole(role)) {
    const pending = qrStats?.pending_count ?? 0;
    return [
      {
        id: 'admin-qr-ops',
        title: 'QR operations',
        description:
          pending > 0
            ? `${pending} submission${pending === 1 ? '' : 's'} awaiting review`
            : 'Review manual QR pay-in submissions',
        icon: HiQrCode,
        tone: 'amber',
        badge: pending > 0 ? pending : null,
        onClick: () => navigate('/admin/pay-in-qr-operations?status=PENDING_REVIEW'),
      },
      {
        id: 'admin-gateways',
        title: 'Payment gateways',
        description: 'Configure payment gateways',
        icon: HiCog6Tooth,
        tone: 'slate',
        onClick: () => navigate('/admin/gateways'),
      },
      {
        id: 'admin-packages',
        title: 'Pay-in packages',
        description: 'Commission splits and payout slabs',
        icon: HiSquares2X2,
        tone: 'indigo',
        onClick: () => navigate('/admin/pay-in-packages'),
      },
      {
        id: 'admin-announcements',
        title: 'Announcements',
        description: 'Platform notices and banners',
        icon: HiMegaphone,
        tone: 'violet',
        onClick: () => navigate('/admin/announcements'),
      },
      {
        id: 'admin-payin-report',
        title: 'Pay-in report',
        description: 'Review load-money transactions',
        icon: HiChartBar,
        tone: 'emerald',
        onClick: () => navigate('/reports/payin'),
      },
    ];
  }

  const tiles = [];
  const canPay = userMayPayOut(user);

  if (includeFundActions && !isFinancialTxBlockedRole(role)) {
    const payIn = moduleState(maintenance, 'pay_in', canUsePayInModule(user, maintenance));
    const payOut = moduleState(maintenance, 'payout', canPay);
    tiles.push(
      {
        id: 'load-money',
        title: 'Load Money',
        description: 'Top up your main wallet',
        icon: HiArrowDownTray,
        tone: 'blue',
        onClick: () => navigate('/fund-management/load-money'),
        ...payIn,
      },
      {
        id: 'payout',
        title: 'Payout',
        description: 'Withdraw to linked bank account',
        icon: HiArrowUpTray,
        tone: 'indigo',
        onClick: () => navigate('/fund-management/payout'),
        ...payOut,
      },
    );
  }

  if (roleHasPath(role, '/bill-payments')) {
    tiles.push({
      id: 'bbps-pay',
      title: 'Pay Bill',
      description: 'Electricity, mobile, DTH & more',
      iconImage: bMnemonicPrimary,
      tone: 'violet',
      onClick: () => navigate('/bill-payments/pay'),
      ...moduleState(maintenance, 'bbps', canPay),
    });
  }

  if (roleHasPath(role, '/aeps') && (isAdminOperationalIsolationRole(role) || user?.access?.aeps_entitled)) {
    tiles.push({
      id: 'aeps',
      title: 'AEPS',
      description: 'Aadhaar banking, withdrawal & balance',
      icon: HiFingerPrint,
      tone: 'sky',
      onClick: () => navigate('/aeps'),
      ...moduleState(maintenance, 'aeps'),
    });
  }

  if (roleHasPath(role, '/cms') && (isAdminOperationalIsolationRole(role) || user?.access?.cms_entitled)) {
    tiles.push({
      id: 'cms',
      title: 'CMS',
      description: 'Cash management collections',
      icon: HiBuildingLibrary,
      tone: 'emerald',
      onClick: () => navigate('/cms'),
      ...moduleState(maintenance, 'cms'),
    });
  }

  return tiles;
}

/**
 * Full product catalog for the dedicated Services page and mobile Services tab.
 * Includes Load Money, Payout, Pay Bill, AEPS, CMS (role + maintenance aware).
 */
export function buildAllProductServices({ user, maintenance, navigate }) {
  return buildServiceTiles({
    user,
    maintenance,
    navigate,
    qrStats: null,
    includeFundActions: true,
  });
}
