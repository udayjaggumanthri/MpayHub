import React, { useState, useEffect, useRef } from 'react';
import { Link, useLocation } from 'react-router-dom';
import { useAuth } from '../../context/AuthContext';
import { getMenuForRole } from '../../utils/rolePermissions';
import { shouldBlockPathForUser } from '../../utils/userAccess';
import {
  FiX,
  FiChevronDown,
  FiChevronRight,
} from 'react-icons/fi';
import { 
  HiHomeModern, 
  HiUsers, 
  HiChartBar, 
  HiCog6Tooth,
  HiBanknotes,
  HiQrCode,
  HiBell,
} from 'react-icons/hi2';
import bMnemonicPrimary from '../../assets/bbps/b-mnemonic-primary.svg';
import { useBranding } from '../../context/AppearanceContext';
import BrandingLogo from './BrandingLogo';

const BBPS_MENU_ICON = 'bbps-mnemonic';

const Sidebar = ({ mobileMenuOpen = false, setMobileMenuOpen = () => {} }) => {
  const { user } = useAuth();
  const { siteTitle } = useBranding();
  const location = useLocation();
  const [expandedMenus, setExpandedMenus] = useState({});
  const menuNavRef = useRef(null);

  const menu = getMenuForRole(user?.role || 'Retailer');
  const rawMenuItems = Array.isArray(menu) ? menu : [];

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

  // Scroll to top when mobile menu opens to ensure Dashboard is visible
  useEffect(() => {
    if (mobileMenuOpen && menuNavRef.current) {
      // Immediate scroll to top
      menuNavRef.current.scrollTop = 0;
      // Also try after a small delay to ensure it works
      const timer = setTimeout(() => {
        if (menuNavRef.current) {
          menuNavRef.current.scrollTop = 0;
        }
      }, 50);
      return () => clearTimeout(timer);
    }
  }, [mobileMenuOpen]);

  const getIcon = (iconName) => {
    const icons = {
      dashboard: HiHomeModern,
      users: HiUsers,
      reports: HiChartBar,
      profile: HiCog6Tooth,
      payin: HiBanknotes,
      qr: HiQrCode,
      notifications: HiBell,
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
          className="flex-shrink-0 h-10 w-10 object-contain object-center"
          draggable={false}
        />
      );
    }
    const Icon = getIcon(iconName);
    return (
      <div
        className={`flex-shrink-0 p-1.5 rounded-lg ${
          active ? 'bg-blue-100 dark:bg-blue-900/40' : 'bg-gray-100 dark:bg-slate-800'
        } transition-colors`}
      >
        <Icon size={18} className={active ? 'text-blue-600 dark:text-blue-400' : 'text-gray-600 dark:text-slate-400'} />
      </div>
    );
  };

  const toggleMenu = (menuName) => {
    setExpandedMenus((prev) => ({
      ...prev,
      [menuName]: !prev[menuName],
    }));
  };

  const isActive = (path) => {
    return location.pathname === path || location.pathname.startsWith(path + '/');
  };

  // Expand submenus when the current route matches a child (e.g. /admin/pay-in-packages under Gateways & pay-in).
  useEffect(() => {
    const path = location.pathname;
    const pathActive = (p) => path === p || path.startsWith(p + '/');
    const items = getMenuForRole(user?.role || 'Retailer');
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
  }, [location.pathname, user?.role]);

  const MenuItem = ({ item, level = 0 }) => {
    const hasSubmenu = item.submenu && item.submenu.length > 0;
    const isExpanded = expandedMenus[item.name];
    const active = hasSubmenu
      ? isActive(item.path) || item.submenu.some((sub) => isActive(sub.path))
      : isActive(item.path);

    if (hasSubmenu) {
      return (
        <div className="mb-1">
          <button
            onClick={() => toggleMenu(item.name)}
            className={`w-full flex items-center justify-between gap-2 px-3 sm:px-4 py-2.5 sm:py-3 rounded-xl transition-all duration-200 ${
              active
                ? 'bg-gradient-to-r from-blue-50 dark:from-blue-950/40 to-indigo-50 dark:to-indigo-950/40 text-blue-600 dark:text-blue-400 font-semibold shadow-md border-l-4 border-blue-600'
                : 'text-gray-700 dark:text-slate-300 hover:bg-gray-50 dark:hover:bg-slate-800 hover:border-l-4 hover:border-gray-300 dark:hover:border-slate-600 font-medium'
            }`}
          >
            <div className="flex items-center space-x-2 sm:space-x-3 flex-1 min-w-0 overflow-hidden">
              <MenuIcon iconName={item.icon} active={active} />
              <span className={`text-sm sm:text-base whitespace-nowrap ${active ? 'font-semibold' : 'font-medium'}`}>{item.name}</span>
            </div>
            <div className={`flex-shrink-0 ${active ? 'text-blue-600 dark:text-blue-400' : 'text-gray-400 dark:text-slate-500'} transition-colors`}>
              {isExpanded ? (
                <FiChevronDown className="transition-transform duration-200" size={16} />
              ) : (
                <FiChevronRight className="transition-transform duration-200" size={16} />
              )}
            </div>
          </button>

          {isExpanded && (
            <div className="ml-6 sm:ml-8 mt-1.5 mb-2 space-y-1 animate-fadeIn">
              {item.submenu.map((subItem) => {
                const subActive = isActive(subItem.path);
                return (
                  <Link
                    key={subItem.path}
                    to={subItem.path}
                    onClick={() => {
                      setMobileMenuOpen(false);
                    }}
                    className={`block px-3 sm:px-4 py-2 sm:py-2.5 rounded-xl transition-all duration-200 text-sm sm:text-base ${
                      subActive
                        ? 'bg-gradient-to-r from-blue-50 dark:from-blue-950/40 to-indigo-50 dark:to-indigo-950/40 text-blue-600 dark:text-blue-400 font-semibold shadow-sm border-l-4 border-blue-600'
                        : 'text-gray-600 dark:text-slate-400 hover:bg-gray-50 dark:hover:bg-slate-800 hover:text-gray-900 dark:hover:text-slate-100 hover:border-l-4 hover:border-gray-300 dark:hover:border-slate-600 font-medium'
                    }`}
                  >
                    {subItem.name}
                  </Link>
                );
              })}
            </div>
          )}
        </div>
      );
    }

    return (
      <Link
        to={item.path}
        onClick={() => setMobileMenuOpen(false)}
        className={`flex items-center space-x-2 sm:space-x-3 px-3 sm:px-4 py-2.5 sm:py-3 rounded-xl transition-all duration-200 ${
          active
            ? 'bg-gradient-to-r from-blue-50 dark:from-blue-950/40 to-indigo-50 dark:to-indigo-950/40 text-blue-600 dark:text-blue-400 font-semibold shadow-md border-l-4 border-blue-600'
            : 'text-gray-700 dark:text-slate-300 hover:bg-gray-50 dark:hover:bg-slate-800 hover:border-l-4 hover:border-gray-300 dark:hover:border-slate-600 font-medium'
        }`}
      >
        <MenuIcon iconName={item.icon} active={active} />
        <span className={`text-sm sm:text-base whitespace-nowrap ${active ? 'font-semibold' : 'font-medium'}`}>{item.name}</span>
      </Link>
    );
  };

  return (
    <>
      {/* Overlay for mobile - Behind sidebar but covers content */}
      {mobileMenuOpen && (
        <div
          className="fixed inset-0 bg-black/50 z-40 lg:hidden transition-opacity duration-300"
          onClick={() => setMobileMenuOpen(false)}
        ></div>
      )}

      {/* Sidebar — above the sticky header (z-40) so the drawer is not clipped by it on mobile */}
      <aside
        className={`fixed inset-y-0 left-0 z-50 w-64 transform border-r border-gray-200 bg-white transition-transform duration-300 ease-in-out dark:border-slate-700 dark:bg-slate-900 ${
          mobileMenuOpen ? 'translate-x-0' : '-translate-x-full lg:translate-x-0'
        }`}
      >
        <div className="h-full flex flex-col relative overflow-hidden">
          {/* Brand — same rail as nav; no rule between (single chrome column) */}
          <div className="hidden lg:flex flex-col items-stretch justify-center flex-shrink-0 px-3 sm:px-4 pt-5 pb-1">
            <Link
              to="/dashboard"
              className="flex w-full items-center justify-center rounded-xl py-1 transition-opacity hover:opacity-90 focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-500 focus-visible:ring-offset-2"
              aria-label={`${siteTitle} home`}
            >
              <BrandingLogo
                className="max-h-14 w-auto max-w-[min(100%,13.5rem)] object-contain object-center"
                draggable={false}
              />
            </Link>
          </div>
          
          {/* Mobile drawer header: brand plus an explicit close control */}
          <div className="flex flex-shrink-0 items-center justify-between gap-2 border-b border-gray-200 px-3 py-2.5 dark:border-slate-700 lg:hidden">
            <Link
              to="/dashboard"
              onClick={() => setMobileMenuOpen(false)}
              className="flex min-w-0 items-center rounded-xl transition-opacity hover:opacity-90 focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-500"
              aria-label={`${siteTitle} home`}
            >
              <BrandingLogo
                className="h-11 w-auto max-w-full object-contain object-left"
                draggable={false}
              />
            </Link>
            <button
              type="button"
              onClick={() => setMobileMenuOpen(false)}
              className="inline-flex h-10 w-10 shrink-0 items-center justify-center rounded-lg text-gray-600 transition-colors hover:bg-gray-100 focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-500 dark:text-slate-400 dark:hover:bg-slate-800"
              aria-label="Close menu"
            >
              <FiX size={20} />
            </button>
          </div>

          {/* Menu Items - Scrollable area - Dashboard always visible at top */}
          <nav 
            ref={menuNavRef}
            className="flex-1 overflow-y-auto overflow-x-hidden px-3 sm:px-4 pt-3 lg:pt-0 pb-2 scroll-smooth" 
            style={{ scrollPaddingTop: 0 }}
          >
            <div className="space-y-1.5 min-h-0">
              {menuItems.length > 0 ? (
                menuItems.map((item, index) => (
                  <div key={`${item.name}-${index}`} className="first:pt-0">
                    <MenuItem item={item} />
                  </div>
                ))
              ) : (
                <div className="px-3 py-2 text-sm text-gray-500 dark:text-slate-400">No menu items available</div>
              )}
            </div>
          </nav>

          {/* User Info - Mobile & Desktop */}
          {user && (
            <div className="px-3 sm:px-4 py-3 sm:py-4 border-t border-gray-200 dark:border-slate-700 flex-shrink-0 bg-gray-50 dark:bg-slate-800/50">
              <div className="flex items-center space-x-2 sm:space-x-3">
                <div className="w-9 h-9 sm:w-10 sm:h-10 bg-blue-600 rounded-full flex items-center justify-center text-white font-semibold text-xs sm:text-sm flex-shrink-0">
                  {user.name?.charAt(0).toUpperCase() || 'U'}
                </div>
                <div className="min-w-0 flex-1">
                  <p className="text-xs sm:text-sm font-medium text-gray-900 dark:text-slate-100 truncate">{user.name}</p>
                  <p className="text-xs text-gray-500 dark:text-slate-400 truncate">
                    {user.displayCode || user.userId || user.user_id || user.memberId}
                  </p>
                </div>
              </div>
            </div>
          )}
        </div>
      </aside>
    </>
  );
};

export default Sidebar;
