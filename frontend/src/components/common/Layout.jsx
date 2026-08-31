import React, { useState } from 'react';
import Sidebar from './Sidebar';
import Header from './Header';
import AccessBlockedAlert from './AccessBlockedAlert';

const Layout = ({ children }) => {
  // Owned here so the mobile menu button can sit inside the header bar rather
  // than floating over the page as a detached control.
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);

  return (
    <div className="min-h-screen bg-gray-50 dark:bg-slate-950">
      <Sidebar mobileMenuOpen={mobileMenuOpen} setMobileMenuOpen={setMobileMenuOpen} />
      <div className="lg:ml-64">
        <Header
          mobileMenuOpen={mobileMenuOpen}
          onToggleMobileMenu={() => setMobileMenuOpen((open) => !open)}
        />
        <main className="p-3 sm:p-4 md:p-6 lg:p-8 pb-6 sm:pb-8">
          <AccessBlockedAlert />
          {children}
        </main>
      </div>
    </div>
  );
};

export default Layout;
