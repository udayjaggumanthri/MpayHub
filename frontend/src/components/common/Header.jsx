import React, { useState } from 'react';
import { useAuth } from '../../context/AuthContext';
import { FaUser, FaRightFromBracket } from 'react-icons/fa6';
import NotificationBell from '../dashboard/NotificationBell';

const Header = () => {
  const { user, logout } = useAuth();
  const [showProfileMenu, setShowProfileMenu] = useState(false);

  return (
    <header className="bg-white shadow-sm border-b border-gray-200 sticky top-0 z-40">
      <div className="px-3 sm:px-4 md:px-6 lg:px-8 py-3 sm:py-4">
        <div className="flex items-center justify-between">
          {/* Left side - Logo (always visible, with space for hamburger on mobile) */}
          <div className="flex items-center ml-12 lg:ml-0">
            <h1 className="text-lg sm:text-xl lg:text-2xl font-bold text-blue-600">mPayhub</h1>
          </div>

          {/* Right side - Notifications and Profile */}
          <div className="flex items-center space-x-2 sm:space-x-4">
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
                <span className="hidden sm:block text-sm font-medium text-gray-700">
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
                      <p className="text-xs text-gray-500">{user?.userId}</p>
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
