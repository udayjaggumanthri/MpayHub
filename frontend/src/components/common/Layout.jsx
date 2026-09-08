import React, { useEffect, useState } from 'react';
import Sidebar, {
  SIDEBAR_STORAGE_KEY,
  SIDEBAR_RAIL_MARGIN_CLASS,
  SIDEBAR_EXPANDED_MARGIN_CLASS,
} from './Sidebar';
import Header from './Header';
import AccessBlockedAlert from './AccessBlockedAlert';

const readCollapsedPreference = () => {
  try {
    return localStorage.getItem(SIDEBAR_STORAGE_KEY) === '1';
  } catch {
    return false;
  }
};

const Layout = ({ children }) => {
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const [sidebarCollapsed, setSidebarCollapsed] = useState(readCollapsedPreference);

  useEffect(() => {
    try {
      localStorage.setItem(SIDEBAR_STORAGE_KEY, sidebarCollapsed ? '1' : '0');
    } catch {
      /* ignore */
    }
  }, [sidebarCollapsed]);

  const contentOffsetClass = sidebarCollapsed
    ? SIDEBAR_RAIL_MARGIN_CLASS
    : SIDEBAR_EXPANDED_MARGIN_CLASS;

  return (
    <div className="flex min-h-screen flex-col bg-gray-50 dark:bg-slate-950">
      {/* Full-width top bar owns the logo; sidebar starts below */}
      <Header
        mobileMenuOpen={mobileMenuOpen}
        onToggleMobileMenu={() => setMobileMenuOpen((open) => !open)}
      />

      <div className="relative flex min-h-0 flex-1">
        <Sidebar
          mobileMenuOpen={mobileMenuOpen}
          setMobileMenuOpen={setMobileMenuOpen}
          collapsed={sidebarCollapsed}
          onCollapsedChange={setSidebarCollapsed}
        />
        <div
          className={`min-w-0 flex-1 transition-[margin] duration-300 ease-in-out ${contentOffsetClass}`}
        >
          <main className="p-3 pb-6 sm:p-4 sm:pb-8 md:p-6 lg:p-8">
            <AccessBlockedAlert />
            {children}
          </main>
        </div>
      </div>
    </div>
  );
};

export default Layout;
