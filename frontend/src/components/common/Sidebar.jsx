import React, { useState, useEffect, useRef } from 'react';
import { Link, useLocation } from 'react-router-dom';
import { useAuth } from '../../context/AuthContext';
import {
  filterMenusByModules,
  getMenuForRole,
} from '../../utils/rolePermissions';
import { shouldBlockPathForUser } from '../../utils/userAccess';
import { adminAPI } from '../../services/api';
import {
  FiX,
  FiChevronDown,
  FiChevronRight,
  FiChevronLeft,
  FiSidebar,
} from 'react-icons/fi';
import {
  HiHomeModern,
  HiUsers,
  HiChartBar,
  HiCog6Tooth,
  HiUserCircle,
  HiBanknotes,
  HiQrCode,
  HiBell,
  HiWallet,
  HiFingerPrint,
  HiWrenchScrewdriver,
  HiSquares2X2,
  HiArrowsRightLeft,
} from 'react-icons/hi2';
import bMnemonicPrimary from '../../assets/bbps/b-mnemonic-primary.svg';
import { HEADER_OFFSET_CLASS } from './Header';

const BBPS_MENU_ICON = 'bbps-mnemonic';
const SIDEBAR_STORAGE_KEY = 'mpayhub_sidebar_collapsed';
const LG_QUERY = '(min-width: 1024px)';

/** Desktop rail width — wide enough for icons; logo is not shown here. */
export const SIDEBAR_RAIL_WIDTH_CLASS = 'lg:w-20';
export const SIDEBAR_RAIL_MARGIN_CLASS = 'lg:ml-20';
export const SIDEBAR_EXPANDED_WIDTH_CLASS = 'lg:w-64';
export const SIDEBAR_EXPANDED_MARGIN_CLASS = 'lg:ml-64';

export { SIDEBAR_STORAGE_KEY };

function useIsDesktopLg() {
  const [isDesktop, setIsDesktop] = useState(() => {
    if (typeof window === 'undefined') return false;
    if (window.matchMedia) return window.matchMedia(LG_QUERY).matches;
    return window.innerWidth >= 1024;
  });

  useEffect(() => {
    if (typeof window === 'undefined') return undefined;
    const sync = () => {
      if (window.matchMedia) {
        setIsDesktop(window.matchMedia(LG_QUERY).matches);
      } else {
        setIsDesktop(window.innerWidth >= 1024);
      }
    };
    sync();
    const mq = window.matchMedia ? window.matchMedia(LG_QUERY) : null;
    if (mq?.addEventListener) {
      mq.addEventListener('change', sync);
      window.addEventListener('resize', sync);
      return () => {
        mq.removeEventListener('change', sync);
        window.removeEventListener('resize', sync);
      };
    }
    if (mq?.addListener) {
      mq.addListener(sync);
      window.addEventListener('resize', sync);
      return () => {
        mq.removeListener(sync);
        window.removeEventListener('resize', sync);
      };
    }
    window.addEventListener('resize', sync);
    return () => window.removeEventListener('resize', sync);
  }, []);

  return isDesktop;
}

const Sidebar = ({
  mobileMenuOpen = false,
  setMobileMenuOpen = () => {},
  collapsed = false,
  onCollapsedChange = () => {},
}) => {
  const { user } = useAuth();
  const location = useLocation();
  const isDesktop = useIsDesktopLg();
  const [expandedMenus, setExpandedMenus] = useState({});
  const [enabledModules, setEnabledModules] = useState(null);
  const [flyoutMenu, setFlyoutMenu] = useState(null);
  const menuNavRef = useRef(null);
  const flyoutTimerRef = useRef(null);

  // Icon rail: desktop hide only. Never while the mobile drawer is open (avoids
  // DevTools/viewport quirks applying rail UI on phone widths).
  const railMode = Boolean(collapsed) && isDesktop && !mobileMenuOpen;
  const showLabels = !railMode;

  useEffect(() => {
    let cancelled = false;
    (async () => {
      const res = await adminAPI.getMyPermissions();
      if (cancelled) return;
      if (res.success && Array.isArray(res.data?.modules)) {
        setEnabledModules(res.data.modules);
      } else {
        setEnabledModules([]);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [user?.role, user?.id]);

  const menu = getMenuForRole(user?.role || 'Retailer');
  const rawMenuItems = filterMenusByModules(
    Array.isArray(menu) ? menu : [],
    enabledModules,
  );

  const menuItems = rawMenuItems
    .map((item) => {
      if (!item.submenu?.length) {
        return shouldBlockPathForUser(user, item.path) ? null : item;
      }
      const submenu = item.submenu.filter((sub) => !shouldBlockPathForUser(user, sub.path));
      if (!submenu.length && shouldBlockPathForUser(user, item.path)) {
        return null;
      }
      return { ...item, submenu };
    })
    .filter(Boolean);

  useEffect(() => {
    if (mobileMenuOpen && menuNavRef.current) {
      menuNavRef.current.scrollTop = 0;
      const timer = setTimeout(() => {
        if (menuNavRef.current) {
          menuNavRef.current.scrollTop = 0;
        }
      }, 50);
      return () => clearTimeout(timer);
    }
  }, [mobileMenuOpen]);

  useEffect(() => {
    setFlyoutMenu(null);
  }, [location.pathname, collapsed, isDesktop]);

  const getIcon = (iconName) => {
    const icons = {
      dashboard: HiHomeModern,
      users: HiUsers,
      reports: HiChartBar,
      profile: HiUserCircle,
      settings: HiCog6Tooth,
      platform: HiWrenchScrewdriver,
      payin: HiBanknotes,
      payout: HiArrowsRightLeft,
      qr: HiQrCode,
      notifications: HiBell,
      wallet: HiWallet,
      aeps: HiFingerPrint,
      'bbps-console': HiSquares2X2,
    };
    return icons[iconName] || HiHomeModern;
  };

  const isBbpsMenuIcon = (iconName) =>
    iconName === BBPS_MENU_ICON || iconName === 'bills';

  const MenuIcon = ({ iconName, active }) => {
    if (isBbpsMenuIcon(iconName)) {
      return (
        <img
          src={bMnemonicPrimary}
          alt="Bill Payment"
          className={`flex-shrink-0 object-contain object-center ${
            railMode ? 'h-8 w-8' : 'h-10 w-10'
          }`}
          draggable={false}
        />
      );
    }
    const Icon = getIcon(iconName);
    return (
      <div
        className={`flex-shrink-0 rounded-lg p-1.5 transition-colors ${
          active ? 'bg-blue-100 dark:bg-blue-900/40' : 'bg-gray-100 dark:bg-slate-800'
        }`}
      >
        <Icon
          size={railMode ? 16 : 18}
          className={active ? 'text-blue-600 dark:text-blue-400' : 'text-gray-600 dark:text-slate-400'}
        />
      </div>
    );
  };

  const toggleMenu = (menuName) => {
    setExpandedMenus((prev) => ({
      ...prev,
      [menuName]: !prev[menuName],
    }));
  };

  const isActive = (path, { exact = false } = {}) => {
    if (exact) {
      return location.pathname === path;
    }
    return location.pathname === path || location.pathname.startsWith(`${path}/`);
  };

  useEffect(() => {
    const path = location.pathname;
    const pathActive = (p) => path === p || path.startsWith(`${p}/`);
    const items = filterMenusByModules(
      getMenuForRole(user?.role || 'Retailer'),
      enabledModules,
    );
    const list = Array.isArray(items) ? items : [];
    setExpandedMenus((prev) => {
      const next = { ...prev };
      let changed = false;
      list.forEach((item) => {
        if (!item.submenu?.length) return;
        if (item.submenu.some((sub) => pathActive(sub.path)) && !next[item.name]) {
          next[item.name] = true;
          changed = true;
        }
      });
      return changed ? next : prev;
    });
  }, [location.pathname, user?.role, enabledModules]);

  const clearFlyoutSoon = () => {
    if (flyoutTimerRef.current) clearTimeout(flyoutTimerRef.current);
    flyoutTimerRef.current = setTimeout(() => setFlyoutMenu(null), 180);
  };

  const openFlyout = (item, anchorEl) => {
    if (flyoutTimerRef.current) clearTimeout(flyoutTimerRef.current);
    if (!anchorEl) return;
    const rect = anchorEl.getBoundingClientRect();
    setFlyoutMenu({
      item,
      top: rect.top,
      left: rect.right + 8,
    });
  };

  const MenuItem = ({ item }) => {
    const hasSubmenu = item.submenu && item.submenu.length > 0;
    const isExpanded = expandedMenus[item.name];
    const active = hasSubmenu
      ? isActive(item.path) || item.submenu.some((sub) => isActive(sub.path))
      : isActive(item.path);

    if (hasSubmenu) {
      if (railMode) {
        return (
          <div className="relative mb-1">
            <button
              type="button"
              title={item.name}
              onClick={(e) => openFlyout(item, e.currentTarget)}
              onMouseEnter={(e) => openFlyout(item, e.currentTarget)}
              onMouseLeave={clearFlyoutSoon}
              className={`flex w-full items-center justify-center rounded-xl px-2 py-2.5 transition-all duration-200 ${
                active
                  ? 'bg-gradient-to-r from-blue-50 to-indigo-50 text-blue-600 shadow-md dark:from-blue-950/40 dark:to-indigo-950/40 dark:text-blue-400'
                  : 'text-gray-700 hover:bg-gray-50 dark:text-slate-300 dark:hover:bg-slate-800'
              }`}
              aria-label={item.name}
            >
              <MenuIcon iconName={item.icon} active={active} />
            </button>
          </div>
        );
      }

      return (
        <div className="mb-1">
          <button
            type="button"
            onClick={() => toggleMenu(item.name)}
            className={`flex w-full items-center justify-between gap-2 rounded-xl px-3 py-2.5 transition-all duration-200 sm:px-4 sm:py-3 ${
              active
                ? 'border-l-4 border-blue-600 bg-gradient-to-r from-blue-50 to-indigo-50 font-semibold text-blue-600 shadow-md dark:from-blue-950/40 dark:to-indigo-950/40 dark:text-blue-400'
                : 'font-medium text-gray-700 hover:border-l-4 hover:border-gray-300 hover:bg-gray-50 dark:text-slate-300 dark:hover:border-slate-600 dark:hover:bg-slate-800'
            }`}
          >
            <div className="flex min-w-0 flex-1 items-center space-x-2 overflow-hidden sm:space-x-3">
              <MenuIcon iconName={item.icon} active={active} />
              {showLabels ? (
                <span
                  className={`whitespace-nowrap text-sm sm:text-base ${
                    active ? 'font-semibold' : 'font-medium'
                  }`}
                >
                  {item.name}
                </span>
              ) : null}
            </div>
            {showLabels ? (
              <div
                className={`flex-shrink-0 ${
                  active ? 'text-blue-600 dark:text-blue-400' : 'text-gray-400 dark:text-slate-500'
                }`}
              >
                {isExpanded ? (
                  <FiChevronDown className="transition-transform duration-200" size={16} />
                ) : (
                  <FiChevronRight className="transition-transform duration-200" size={16} />
                )}
              </div>
            ) : null}
          </button>

          {isExpanded && showLabels ? (
            <div className="mb-2 ml-6 mt-1.5 space-y-1 animate-fadeIn sm:ml-8">
              {item.submenu.map((subItem) => {
                const subActive = subItem.exactEnd
                  ? isActive(subItem.path, { exact: true })
                  : isActive(subItem.path);
                return (
                  <Link
                    key={subItem.path}
                    to={subItem.path}
                    onClick={() => setMobileMenuOpen(false)}
                    className={`block rounded-xl px-3 py-2 text-sm transition-all duration-200 sm:px-4 sm:py-2.5 sm:text-base ${
                      subActive
                        ? 'border-l-4 border-blue-600 bg-gradient-to-r from-blue-50 to-indigo-50 font-semibold text-blue-600 shadow-sm dark:from-blue-950/40 dark:to-indigo-950/40 dark:text-blue-400'
                        : 'font-medium text-gray-600 hover:border-l-4 hover:border-gray-300 hover:bg-gray-50 hover:text-gray-900 dark:text-slate-400 dark:hover:border-slate-600 dark:hover:bg-slate-800 dark:hover:text-slate-100'
                    }`}
                  >
                    {subItem.name}
                  </Link>
                );
              })}
            </div>
          ) : null}
        </div>
      );
    }

    if (railMode) {
      return (
        <div className="mb-1">
          <Link
            to={item.path}
            onClick={() => setMobileMenuOpen(false)}
            onMouseEnter={(e) => openFlyout(item, e.currentTarget)}
            onMouseLeave={clearFlyoutSoon}
            onFocus={(e) => openFlyout(item, e.currentTarget)}
            onBlur={clearFlyoutSoon}
            className={`flex items-center justify-center rounded-xl px-2 py-2.5 transition-all duration-200 ${
              active
                ? 'bg-gradient-to-r from-blue-50 to-indigo-50 text-blue-600 shadow-md dark:from-blue-950/40 dark:to-indigo-950/40 dark:text-blue-400'
                : 'text-gray-700 hover:bg-gray-50 dark:text-slate-300 dark:hover:bg-slate-800'
            }`}
            aria-label={item.name}
          >
            <MenuIcon iconName={item.icon} active={active} />
          </Link>
        </div>
      );
    }

    return (
      <Link
        to={item.path}
        onClick={() => setMobileMenuOpen(false)}
        className={`flex items-center space-x-2 rounded-xl px-3 py-2.5 transition-all duration-200 sm:space-x-3 sm:px-4 sm:py-3 ${
          active
            ? 'border-l-4 border-blue-600 bg-gradient-to-r from-blue-50 to-indigo-50 font-semibold text-blue-600 shadow-md dark:from-blue-950/40 dark:to-indigo-950/40 dark:text-blue-400'
            : 'font-medium text-gray-700 hover:border-l-4 hover:border-gray-300 hover:bg-gray-50 dark:text-slate-300 dark:hover:border-slate-600 dark:hover:bg-slate-800'
        }`}
      >
        <MenuIcon iconName={item.icon} active={active} />
        {showLabels ? (
          <span
            className={`whitespace-nowrap text-sm sm:text-base ${
              active ? 'font-semibold' : 'font-medium'
            }`}
          >
            {item.name}
          </span>
        ) : null}
      </Link>
    );
  };

  const widthClass = railMode ? SIDEBAR_RAIL_WIDTH_CLASS : SIDEBAR_EXPANDED_WIDTH_CLASS;

  return (
    <>
      {mobileMenuOpen && (
        <div
          className={`fixed inset-x-0 bottom-0 z-40 bg-black/50 transition-opacity duration-300 lg:hidden ${HEADER_OFFSET_CLASS}`}
          onClick={() => setMobileMenuOpen(false)}
        />
      )}

      <aside
        className={`fixed left-0 z-40 w-64 transform border-r border-gray-200 bg-white transition-[width,transform] duration-300 ease-in-out dark:border-slate-700 dark:bg-slate-900 ${HEADER_OFFSET_CLASS} bottom-0 ${widthClass} ${
          mobileMenuOpen ? 'translate-x-0' : '-translate-x-full lg:translate-x-0'
        }`}
        onMouseLeave={clearFlyoutSoon}
      >
        <div className="relative flex h-full flex-col overflow-hidden">
          {/* Mobile drawer chrome only — logo stays in Header, never in the rail */}
          <div className="flex flex-shrink-0 items-center justify-end border-b border-gray-200 px-3 py-2.5 dark:border-slate-700 lg:hidden">
            <button
              type="button"
              onClick={() => setMobileMenuOpen(false)}
              className="inline-flex h-10 w-10 shrink-0 items-center justify-center rounded-lg text-gray-600 transition-colors hover:bg-gray-100 focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-500 dark:text-slate-400 dark:hover:bg-slate-800"
              aria-label="Close menu"
            >
              <FiX size={20} />
            </button>
          </div>

          <nav
            ref={menuNavRef}
            className={`flex-1 overflow-y-auto overflow-x-hidden scroll-smooth pb-2 pt-3 ${
              railMode ? 'px-1.5' : 'px-3 sm:px-4'
            }`}
            style={{ scrollPaddingTop: 0 }}
          >
            <div className="min-h-0 space-y-1.5">
              {menuItems.length > 0 ? (
                menuItems.map((item, index) => (
                  <div key={`${item.name}-${index}`} className="first:pt-0">
                    <MenuItem item={item} />
                  </div>
                ))
              ) : (
                <div className="px-3 py-2 text-sm text-gray-500 dark:text-slate-400">
                  No menu items available
                </div>
              )}
            </div>
          </nav>

          {/* Desktop-only hide/pin — bottom of sidebar (no profile block) */}
          <div
            className={`hidden flex-shrink-0 border-t border-gray-200 dark:border-slate-700 lg:block ${
              railMode ? 'px-1.5 py-3' : 'px-3 py-3 sm:px-4'
            }`}
          >
            <button
              type="button"
              onClick={() => onCollapsedChange(!collapsed)}
              className={`flex w-full items-center rounded-lg px-2 py-2.5 text-xs font-semibold text-slate-600 transition-colors hover:bg-slate-100 dark:text-slate-300 dark:hover:bg-slate-800 ${
                railMode ? 'justify-center' : 'justify-between gap-2'
              }`}
              title={collapsed ? 'Show panel' : 'Hide panel'}
              aria-label={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}
            >
              {railMode ? (
                <FiSidebar size={18} />
              ) : (
                <>
                  <span className="inline-flex items-center gap-2">
                    <FiSidebar size={16} />
                    Hide panel
                  </span>
                  <FiChevronLeft size={16} />
                </>
              )}
            </button>
          </div>
        </div>
      </aside>

      {railMode && flyoutMenu?.item ? (
        <div
          className="fixed z-[60] min-w-[10rem] max-w-[16rem] animate-fadeIn rounded-xl border border-slate-200 bg-white py-1.5 shadow-xl dark:border-slate-700 dark:bg-slate-900"
          style={{ top: flyoutMenu.top, left: flyoutMenu.left }}
          onMouseEnter={() => {
            if (flyoutTimerRef.current) clearTimeout(flyoutTimerRef.current);
          }}
          onMouseLeave={clearFlyoutSoon}
        >
          {flyoutMenu.item.submenu?.length ? (
            <>
              <p className="px-3 pb-1 pt-1 text-[10px] font-semibold uppercase tracking-wider text-slate-400">
                {flyoutMenu.item.name}
              </p>
              {flyoutMenu.item.submenu.map((subItem) => {
                const subActive = subItem.exactEnd
                  ? isActive(subItem.path, { exact: true })
                  : isActive(subItem.path);
                return (
                  <Link
                    key={subItem.path}
                    to={subItem.path}
                    onClick={() => {
                      setFlyoutMenu(null);
                      setMobileMenuOpen(false);
                    }}
                    className={`block px-3 py-2 text-sm transition-colors ${
                      subActive
                        ? 'bg-blue-50 font-semibold text-blue-600 dark:bg-blue-950/40 dark:text-blue-400'
                        : 'text-slate-700 hover:bg-slate-50 dark:text-slate-300 dark:hover:bg-slate-800'
                    }`}
                  >
                    {subItem.name}
                  </Link>
                );
              })}
            </>
          ) : (
            <Link
              to={flyoutMenu.item.path}
              onClick={() => {
                setFlyoutMenu(null);
                setMobileMenuOpen(false);
              }}
              className="block px-3 py-2 text-sm font-semibold text-slate-800 hover:bg-slate-50 dark:text-slate-100 dark:hover:bg-slate-800"
            >
              {flyoutMenu.item.name}
            </Link>
          )}
        </div>
      ) : null}
    </>
  );
};

export default Sidebar;
