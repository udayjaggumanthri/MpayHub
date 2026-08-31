import React, { useState } from 'react';
import { Link } from 'react-router-dom';
import { useAuth } from '../../context/AuthContext';
import { useBranding } from '../../context/AppearanceContext';
import { FaUser, FaRightFromBracket, FaClipboardList, FaGear, FaBars, FaXmark } from 'react-icons/fa6';
import NotificationBell from '../dashboard/NotificationBell';
import BrandingLogo from './BrandingLogo';
import ThemeToggle from './ThemeToggle';

const Header = ({ mobileMenuOpen = false, onToggleMobileMenu }) => {
  const { user, logout } = useAuth();
  const { siteTitle } = useBranding();
  const [showProfileMenu, setShowProfileMenu] = useState(false);

  return (
    <header className="sticky top-0 z-40 border-b border-gray-200 bg-white shadow-sm dark:border-slate-700 dark:bg-slate-900">
      <div className="px-3 sm:px-4 md:px-6 lg:px-8 py-2.5 sm:py-3">
        <div className="flex min-h-14 items-center gap-2 sm:gap-3 sm:min-h-16">
          {/* Mobile / tablet: menu control lives in the bar so the three zones align */}
          <button
            type="button"
            onClick={onToggleMobileMenu}
            className="inline-flex h-10 w-10 shrink-0 items-center justify-center rounded-lg border border-gray-200 text-gray-700 transition-colors hover:bg-gray-100 focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-500 dark:border-slate-700 dark:text-slate-300 dark:hover:bg-slate-800 lg:hidden"
            aria-label={mobileMenuOpen ? 'Close menu' : 'Open menu'}
            aria-expanded={mobileMenuOpen}
          >
            {mobileMenuOpen ? <FaXmark size={18} /> : <FaBars size={18} />}
          </button>

          {/* Mobile / tablet brand (lg+ uses the sidebar logo only) */}
          <Link
            to="/dashboard"
            className="flex min-w-0 flex-1 items-center justify-start rounded-xl transition-opacity hover:opacity-90 focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-500 lg:hidden"
            aria-label={`${siteTitle} home`}
          >
            <BrandingLogo
              className="h-12 w-auto max-w-full object-contain object-left sm:h-14"
              draggable={false}
            />
          </Link>

          <div className="ml-auto flex shrink-0 items-center gap-1 sm:gap-2">
            <ThemeToggle />
            <NotificationBell />

            <div className="relative">
              <button
                onClick={() => setShowProfileMenu(!showProfileMenu)}
                className="flex items-center gap-1.5 sm:gap-2 px-1.5 sm:px-3 py-2 rounded-lg hover:bg-gray-100 transition-colors dark:hover:bg-slate-800"
              >
                <div className="w-7 h-7 sm:w-8 sm:h-8 bg-blue-600 rounded-full flex items-center justify-center text-white font-semibold text-xs sm:text-sm">
                  {user?.name?.charAt(0).toUpperCase() || 'U'}
                </div>
                <span className="hidden max-w-[10rem] truncate sm:block text-sm font-medium text-gray-700 dark:text-slate-200">
                  {user?.name || 'User'}
                </span>
                <FaUser className="text-gray-600 dark:text-slate-400 hidden sm:block" size={18} />
              </button>

              {showProfileMenu && (
                <>
                  <div
                    className="fixed inset-0 z-10"
                    onClick={() => setShowProfileMenu(false)}
                  ></div>
                  <div className="absolute right-0 mt-2 w-48 sm:w-56 bg-white rounded-lg shadow-lg border border-gray-200 py-2 z-20 dark:bg-slate-800 dark:border-slate-700">
                    <div className="px-4 py-2 border-b border-gray-200 dark:border-slate-700">
                      <p className="text-sm font-medium text-gray-900 dark:text-slate-100">{user?.name}</p>
                      <p className="text-xs text-gray-500 dark:text-slate-400">
                        {user?.displayCode || user?.userId || user?.user_id || user?.memberId || '—'}
                      </p>
                      <p className="text-xs text-gray-500 dark:text-slate-400">{user?.role}</p>
                    </div>
                    <Link
                      to="/profile"
                      onClick={() => setShowProfileMenu(false)}
                      className="flex w-full items-center space-x-2 px-4 py-2 text-sm text-gray-700 dark:text-slate-300 hover:bg-gray-100 dark:hover:bg-slate-700 transition-colors"
                    >
                      <FaGear size={14} />
                      <span>Profile &amp; settings</span>
                    </Link>
                    <Link
                      to="/audit-logs"
                      onClick={() => setShowProfileMenu(false)}
                      className="flex w-full items-center space-x-2 px-4 py-2 text-sm text-gray-700 dark:text-slate-300 hover:bg-gray-100 dark:hover:bg-slate-700 transition-colors"
                    >
                      <FaClipboardList size={14} />
                      <span>Audit logs</span>
                    </Link>
                    <button
                      onClick={() => {
                        setShowProfileMenu(false);
                        logout();
                      }}
                      className="w-full flex items-center space-x-2 px-4 py-2 text-sm text-gray-700 dark:text-slate-300 hover:bg-gray-100 dark:hover:bg-slate-700 transition-colors"
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
      </div>
    </header>
  );
};

export default Header;
