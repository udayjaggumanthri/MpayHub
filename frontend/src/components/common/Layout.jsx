import React from 'react';
import Sidebar from './Sidebar';
import Header from './Header';

const Layout = ({ children }) => {
  return (
    <div className="min-h-screen bg-gray-50">
      <Sidebar />
      <div className="lg:ml-64">
        <Header />
        <main className="p-3 sm:p-4 md:p-6 lg:p-8 pb-6 sm:pb-8">
          {children}
        </main>
      </div>
    </div>
  );
};

export default Layout;
