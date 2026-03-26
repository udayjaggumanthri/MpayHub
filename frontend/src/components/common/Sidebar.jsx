import React, { useState, useEffect, useRef } from 'react';
import { Link, useLocation } from 'react-router-dom';
import { useAuth } from '../../context/AuthContext';
import { getMenuForRole } from '../../utils/rolePermissions';
import {
  FiMenu,
  FiX,
  FiChevronDown,
  FiChevronRight,
} from 'react-icons/fi';
import { 
  HiHomeModern, 
  HiDocumentText, 
  HiUsers, 
  HiChartBar, 
  HiCog6Tooth 
} from 'react-icons/hi2';

const Sidebar = () => {
  const { user } = useAuth();
  const location = useLocation();
  const [expandedMenus, setExpandedMenus] = useState({});
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const menuNavRef = useRef(null);

  const menu = getMenuForRole(user?.role || 'Retailer');

  // Ensure menu is an array and has items
  const menuItems = Array.isArray(menu) ? menu : [];

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
  }, [mobileMenuOpen, menuItems]);

  const getIcon = (iconName) => {
    const icons = {
      dashboard: HiHomeModern,
      bills: HiDocumentText,
      users: HiUsers,
      reports: HiChartBar,
      profile: HiCog6Tooth,
    };
    return icons[iconName] || HiHomeModern;
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

  const MenuItem = ({ item, level = 0 }) => {
    const Icon = getIcon(item.icon);
    const hasSubmenu = item.submenu && item.submenu.length > 0;
    const isExpanded = expandedMenus[item.name];
    const active = isActive(item.path);

    if (hasSubmenu) {
      return (
        <div className="mb-1">
          <button
            onClick={() => toggleMenu(item.name)}
            className={`w-full flex items-center justify-between gap-2 px-3 sm:px-4 py-2.5 sm:py-3 rounded-xl transition-all duration-200 ${
              active
                ? 'bg-gradient-to-r from-blue-50 to-indigo-50 text-blue-600 font-semibold shadow-md border-l-4 border-blue-600'
                : 'text-gray-700 hover:bg-gray-50 hover:border-l-4 hover:border-gray-300 font-medium'
            }`}
          >
            <div className="flex items-center space-x-2 sm:space-x-3 flex-1 min-w-0 overflow-hidden">
              <div className={`flex-shrink-0 p-1.5 rounded-lg ${active ? 'bg-blue-100' : 'bg-gray-100'} transition-colors`}>
                <Icon size={18} className={active ? 'text-blue-600' : 'text-gray-600'} />
              </div>
              <span className={`text-sm sm:text-base whitespace-nowrap ${active ? 'font-semibold' : 'font-medium'}`}>{item.name}</span>
            </div>
            <div className={`flex-shrink-0 ${active ? 'text-blue-600' : 'text-gray-400'} transition-colors`}>
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
                        ? 'bg-gradient-to-r from-blue-50 to-indigo-50 text-blue-600 font-semibold shadow-sm border-l-4 border-blue-600'
                        : 'text-gray-600 hover:bg-gray-50 hover:text-gray-900 hover:border-l-4 hover:border-gray-300 font-medium'
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
            ? 'bg-gradient-to-r from-blue-50 to-indigo-50 text-blue-600 font-semibold shadow-md border-l-4 border-blue-600'
            : 'text-gray-700 hover:bg-gray-50 hover:border-l-4 hover:border-gray-300 font-medium'
        }`}
      >
        <div className={`flex-shrink-0 p-1.5 rounded-lg ${active ? 'bg-blue-100' : 'bg-gray-100'} transition-colors`}>
          <Icon size={18} className={active ? 'text-blue-600' : 'text-gray-600'} />
        </div>
        <span className={`text-sm sm:text-base whitespace-nowrap ${active ? 'font-semibold' : 'font-medium'}`}>{item.name}</span>
      </Link>
    );
  };

  return (
    <>
      {/* Mobile Menu Button - Top Left (Fixed position) */}
      <button
        onClick={() => {
          setMobileMenuOpen(!mobileMenuOpen);
          // Scroll to top immediately when opening
          if (!mobileMenuOpen && menuNavRef.current) {
            setTimeout(() => {
              if (menuNavRef.current) {
                menuNavRef.current.scrollTop = 0;
              }
            }, 10);
          }
        }}
        className="lg:hidden fixed top-3 left-3 z-50 p-2.5 bg-white rounded-lg shadow-lg border border-gray-200 hover:bg-gray-50 transition-colors"
        aria-label="Toggle menu"
      >
        {mobileMenuOpen ? <FiX size={22} className="text-gray-700" /> : <FiMenu size={22} className="text-gray-700" />}
      </button>

      {/* Overlay for mobile - Behind sidebar but covers content */}
      {mobileMenuOpen && (
        <div
          className="fixed inset-0 bg-black bg-opacity-50 z-30 lg:hidden transition-opacity duration-300"
          onClick={() => setMobileMenuOpen(false)}
        ></div>
      )}

      {/* Sidebar */}
      <aside
        className={`fixed inset-y-0 left-0 z-40 w-64 bg-white border-r border-gray-200 transform transition-transform duration-300 ease-in-out ${
          mobileMenuOpen ? 'translate-x-0' : '-translate-x-full lg:translate-x-0'
        }`}
      >
        <div className="h-full flex flex-col relative overflow-hidden">
          {/* Logo - Desktop only (mobile logo is in header) */}
          <div className="hidden lg:block px-4 py-4 border-b border-gray-200 flex-shrink-0">
            <h1 className="text-xl font-bold text-blue-600">mPayhub</h1>
          </div>
          
          {/* Mobile: No border or padding - Dashboard starts immediately */}
          <div className="lg:hidden flex-shrink-0 h-0"></div>

          {/* Menu Items - Scrollable area - Dashboard always visible at top */}
          <nav 
            ref={menuNavRef}
            className="flex-1 overflow-y-auto overflow-x-hidden px-3 sm:px-4 pt-[68px] lg:pt-2 pb-2 scroll-smooth" 
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
                <div className="px-3 py-2 text-sm text-gray-500">No menu items available</div>
              )}
            </div>
          </nav>

          {/* User Info - Mobile & Desktop */}
          {user && (
            <div className="px-3 sm:px-4 py-3 sm:py-4 border-t border-gray-200 flex-shrink-0 bg-gray-50">
              <div className="flex items-center space-x-2 sm:space-x-3">
                <div className="w-9 h-9 sm:w-10 sm:h-10 bg-blue-600 rounded-full flex items-center justify-center text-white font-semibold text-xs sm:text-sm flex-shrink-0">
                  {user.name?.charAt(0).toUpperCase() || 'U'}
                </div>
                <div className="min-w-0 flex-1">
                  <p className="text-xs sm:text-sm font-medium text-gray-900 truncate">{user.name}</p>
                  <p className="text-xs text-gray-500 truncate">{user.userId}</p>
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
