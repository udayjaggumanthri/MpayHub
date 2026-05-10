import React from 'react';
import { Outlet } from 'react-router-dom';

/**
 * Lavender shell for complaint hub sub-routes (reference-aligned layout).
 */
const BbpsComplaintsModule = () => (
  <div className="min-h-[calc(100vh-8rem)] bg-violet-50/80 rounded-xl border border-violet-100/80 p-4 md:p-6">
    <Outlet />
  </div>
);

export default BbpsComplaintsModule;
