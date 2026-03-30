import React, { useState } from 'react';
import { Link } from 'react-router-dom';
import { useAuth } from '../../context/AuthContext';
import { FaUser, FaRightFromBracket } from 'react-icons/fa6';
import NotificationBell from '../dashboard/NotificationBell';

const LOGO_SRC = `${process.env.PUBLIC_URL || ''}/images/logo.svg`;

const Header = () => {
  const { user, logout } = useAuth();
  const [showProfileMenu, setShowProfileMenu] = useState(false);

  return (
    <header className="bg-white shadow-sm border-b border-gray-200 sticky top-0 z-40">
      <div className="px-3 sm:px-4 md:px-6 lg:px-8 py-3 sm:py-4">
        <div className="relative flex min-h-12 items-center sm:min-h-14">
          {/* Mobile / tablet: brand centered in header (lg+ uses sidebar logo only) */}
          <div className="pointer-events-none absolute inset-0 flex items-center justify-center px-14 sm:px-16 lg:hidden">
            <Link
              to="/dashboard"
              className="pointer-events-auto inline-flex max-w-full items-center justify-center rounded-xl py-1 transition-opacity hover:opacity-90 focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-500 focus-visible:ring-offset-2"
              aria-label="mPayhub home"
            >
              <img
                src={LOGO_SRC}
                alt="mPayhub"
                className="h-12 w-auto max-w-full object-contain object-center sm:h-[3.25rem] md:h-14"
                draggable={false}
              />
            </Link>
          </div>

          {/* Right: keep clear of fixed hamburger (≈48px); sit above centered logo for hit targets */}
          <div className="relative z-10 ml-auto flex w-full items-center justify-end space-x-2 pl-12 sm:space-x-4 lg:pl-0">
            {/* Notification Bell */}
            <NotificationBell />

            {/* Profile Dropdown */}
            <div className="relative">
              <button
                onClick={() => setShowProfileMenu(!showProfileMenu)}
                className="flex items-center space-x-1 sm:space-x-2 px-2 sm:px-3 py-2 rounded-lg hover:bg-gray-100 transition-colors"
              >
                <div className="w-7 h-7 sm:w-8 sm:h-8 bg-blue-600 rounded-full flex items-center justify-center text-white font-semibold text-xs sm:text-sm">
                  {user?.name?.charAt(0).toUpperCase() || 'U'}
                </div>
                <span className="hidden max-w-[10rem] truncate sm:block text-sm font-medium text-gray-700">
                  {user?.name || 'User'}
                </span>
                <FaUser className="text-gray-600 hidden sm:block" size={18} />
              </button>

              {/* Profile Dropdown Menu */}
              {showProfileMenu && (
                <>
                  <div
                    className="fixed inset-0 z-10"
                    onClick={() => setShowProfileMenu(false)}
                  ></div>
                  <div className="absolute right-0 mt-2 w-48 sm:w-56 bg-white rounded-lg shadow-lg border border-gray-200 py-2 z-20">
                    <div className="px-4 py-2 border-b border-gray-200">
                      <p className="text-sm font-medium text-gray-900">{user?.name}</p>
                      <p className="text-xs text-gray-500">{user?.userId || user?.user_id || '—'}</p>
                      <p className="text-xs text-gray-500">{user?.role}</p>
                    </div>
                    <button
                      onClick={() => {
                        setShowProfileMenu(false);
                        logout();
                      }}
                      className="w-full flex items-center space-x-2 px-4 py-2 text-sm text-gray-700 hover:bg-gray-100 transition-colors"
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
