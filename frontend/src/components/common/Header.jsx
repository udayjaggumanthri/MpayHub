import React, { useState, useEffect, useRef } from 'react';
import { Link, useLocation } from 'react-router-dom';
import { useAuth } from '../../context/AuthContext';
import { useBranding } from '../../context/AppearanceContext';
import { useWallet } from '../../context/WalletContext';
import { formatCurrency } from '../../utils/formatters';
import {
  FaUser,
  FaRightFromBracket,
  FaClipboardList,
  FaGear,
  FaBars,
  FaXmark,
  FaWallet,
} from 'react-icons/fa6';
import NotificationBell from '../dashboard/NotificationBell';
import BrandingLogo from './BrandingLogo';
import ThemeToggle from './ThemeToggle';

/** Keep in sync with Sidebar `top-*` / `h-[calc(100vh-…)]` offsets */
export const HEADER_OFFSET_CLASS = 'top-16';
export const HEADER_HEIGHT_CLASS = 'h-16';

const Header = ({ mobileMenuOpen = false, onToggleMobileMenu }) => {
  const { user, logout } = useAuth();
  const { siteTitle } = useBranding();
  const { wallets, availableBalance, heldBalance, loading, refreshWallets } = useWallet();
  const location = useLocation();
  const [showProfileMenu, setShowProfileMenu] = useState(false);
  const lastRefreshAtRef = useRef(0);

  const softRefresh = () => {
    const now = Date.now();
    if (now - lastRefreshAtRef.current < 8000) return;
    lastRefreshAtRef.current = now;
    refreshWallets();
  };

  // Soft-refresh balance when switching pages and when returning to the tab.
  useEffect(() => {
    if (!user) return undefined;
    softRefresh();
    return undefined;
    // eslint-disable-next-line react-hooks/exhaustive-deps -- throttle refresh on route change
  }, [user, location.pathname]);

  useEffect(() => {
    if (!user) return undefined;
    const onVisible = () => {
      if (document.visibilityState === 'visible') softRefresh();
    };
    document.addEventListener('visibilitychange', onVisible);
    const interval = window.setInterval(() => {
      if (document.visibilityState === 'visible') softRefresh();
    }, 45000);
    return () => {
      document.removeEventListener('visibilitychange', onVisible);
      window.clearInterval(interval);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [user, refreshWallets]);

  const displayBalance =
    heldBalance > 0 && availableBalance != null ? availableBalance : wallets?.main ?? 0;
  const showBalancePlaceholder = Boolean(loading && wallets == null);

  return (
    <header
      className={`sticky top-0 z-50 ${HEADER_HEIGHT_CLASS} border-b border-gray-200 bg-white shadow-sm dark:border-slate-700 dark:bg-slate-900`}
    >
      <div className="flex h-full items-center gap-2 px-3 sm:gap-3 sm:px-4 md:px-6 lg:px-8">
        <button
          type="button"
          onClick={onToggleMobileMenu}
          className="inline-flex h-10 w-10 shrink-0 items-center justify-center rounded-lg border border-gray-200 text-gray-700 transition-colors hover:bg-gray-100 focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-500 dark:border-slate-700 dark:text-slate-300 dark:hover:bg-slate-800 lg:hidden"
          aria-label={mobileMenuOpen ? 'Close menu' : 'Open menu'}
          aria-expanded={mobileMenuOpen}
        >
          {mobileMenuOpen ? <FaXmark size={18} /> : <FaBars size={18} />}
        </button>

        {/* Full brand — room for a larger logo on phone/tablet (theme lives in the menu there) */}
        <Link
          to="/dashboard"
          className="flex min-w-0 flex-1 items-center justify-start rounded-xl transition-opacity hover:opacity-90 focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-500"
          aria-label={`${siteTitle} home`}
        >
          <BrandingLogo
            className="h-11 w-auto max-w-[min(100%,11rem)] object-contain object-left sm:h-12 sm:max-w-[min(100%,14rem)] md:h-[3.25rem] md:max-w-[min(100%,16rem)]"
            draggable={false}
          />
        </Link>

        <div className="ml-auto flex shrink-0 items-center gap-1 sm:gap-2">
          {/* Desktop only — phone/tablet use Appearance in the side menu */}
          <span className="hidden lg:inline-flex">
            <ThemeToggle />
          </span>

          {user ? (
            <Link
              to="/reports/passbook"
              title="Main wallet balance — open passbook"
              className="inline-flex max-w-[8.5rem] items-center gap-1 rounded-full border border-emerald-200 bg-emerald-50 px-2 py-1.5 text-emerald-900 shadow-sm transition hover:bg-emerald-100 focus:outline-none focus-visible:ring-2 focus-visible:ring-emerald-500 dark:border-emerald-800 dark:bg-emerald-950/50 dark:text-emerald-100 dark:hover:bg-emerald-900/60 sm:max-w-none sm:gap-2 sm:px-3"
              aria-label={`Wallet balance ${formatCurrency(displayBalance)}`}
            >
              <FaWallet className="h-3.5 w-3.5 shrink-0 text-emerald-600 dark:text-emerald-400" aria-hidden />
              <span className="min-w-0 truncate text-xs font-bold tabular-nums sm:text-sm">
                {showBalancePlaceholder ? '…' : formatCurrency(displayBalance)}
              </span>
            </Link>
          ) : null}

          <NotificationBell />

          <div className="relative">
            <button
              type="button"
              onClick={() => setShowProfileMenu(!showProfileMenu)}
              className="flex items-center gap-1.5 rounded-lg px-1.5 py-2 transition-colors hover:bg-gray-100 dark:hover:bg-slate-800 sm:gap-2 sm:px-3"
            >
              <div className="flex h-7 w-7 items-center justify-center rounded-full bg-blue-600 text-xs font-semibold text-white sm:h-8 sm:w-8 sm:text-sm">
                {user?.name?.charAt(0).toUpperCase() || 'U'}
              </div>
              <span className="hidden max-w-[10rem] truncate text-sm font-medium text-gray-700 dark:text-slate-200 sm:block">
                {user?.name || 'User'}
              </span>
              <FaUser className="hidden text-gray-600 dark:text-slate-400 sm:block" size={18} />
            </button>

            {showProfileMenu && (
              <>
                <div className="fixed inset-0 z-10" onClick={() => setShowProfileMenu(false)} />
                <div className="absolute right-0 z-20 mt-2 w-48 rounded-lg border border-gray-200 bg-white py-2 shadow-lg dark:border-slate-700 dark:bg-slate-800 sm:w-56">
                  <div className="border-b border-gray-200 px-4 py-2 dark:border-slate-700">
                    <p className="text-sm font-medium text-gray-900 dark:text-slate-100">{user?.name}</p>
                    <p className="text-xs text-gray-500 dark:text-slate-400">
                      {user?.displayCode || user?.userId || user?.user_id || user?.memberId || '—'}
                    </p>
                    <p className="text-xs text-gray-500 dark:text-slate-400">{user?.role}</p>
                    <p className="mt-1.5 text-xs font-semibold tabular-nums text-emerald-700 dark:text-emerald-300">
                      Wallet {formatCurrency(displayBalance)}
                    </p>
                  </div>
                  <Link
                    to="/profile"
                    onClick={() => setShowProfileMenu(false)}
                    className="flex w-full items-center space-x-2 px-4 py-2 text-sm text-gray-700 transition-colors hover:bg-gray-100 dark:text-slate-300 dark:hover:bg-slate-700"
                  >
                    <FaGear size={14} />
                    <span>Profile &amp; settings</span>
                  </Link>
                  <Link
                    to="/audit-logs"
                    onClick={() => setShowProfileMenu(false)}
                    className="flex w-full items-center space-x-2 px-4 py-2 text-sm text-gray-700 transition-colors hover:bg-gray-100 dark:text-slate-300 dark:hover:bg-slate-700"
                  >
                    <FaClipboardList size={14} />
                    <span>Audit logs</span>
                  </Link>
                  <button
                    type="button"
                    onClick={() => {
                      setShowProfileMenu(false);
                      logout();
                    }}
                    className="flex w-full items-center space-x-2 px-4 py-2 text-sm text-gray-700 transition-colors hover:bg-gray-100 dark:text-slate-300 dark:hover:bg-slate-700"
                  >
                    <FaRightFromBracket />
                    <span>Logout</span>
                  </button>
                </div>
              </>
            )}
          </div>
        </div>
      </div>
    </header>
  );
};

export default Header;
