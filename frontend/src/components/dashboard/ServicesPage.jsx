import React, { useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../../context/AuthContext';
import { isAdminOperationalIsolationRole } from '../../utils/rolePermissions';
import ServicesGrid from './ServicesGrid';
import ActionTile from './ActionTile';
import { buildAllProductServices, buildServiceTiles } from './dashboardCatalog';

/**
 * Dedicated services hub — opened from "View All" / mobile Services tab.
 * Channel roles see money products; Admin sees platform ops shortcuts.
 */
const ServicesPage = () => {
  const { user, maintenance } = useAuth();
  const navigate = useNavigate();
  const adminOps = isAdminOperationalIsolationRole(user?.role);

  const tiles = useMemo(() => {
    if (adminOps) {
      return buildServiceTiles({ user, maintenance, navigate, qrStats: null });
    }
    return buildAllProductServices({ user, maintenance, navigate });
  }, [user, maintenance, navigate, adminOps]);

  return (
    <div className="mx-auto max-w-5xl space-y-5 pb-8 sm:space-y-6">
      <header className="space-y-1">
        <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-500 dark:text-slate-400">
          Catalogue
        </p>
        <h1 className="text-2xl font-bold tracking-tight text-slate-900 dark:text-slate-100">
          {adminOps ? 'Administration' : 'Services'}
        </h1>
        <p className="max-w-xl text-sm text-slate-500 dark:text-slate-400">
          {adminOps
            ? 'Jump into platform tools for pay-in, packages, and announcements.'
            : 'Load money, payout, bill payments, AEPS and CMS — everything in one place.'}
        </p>
      </header>

      {tiles.length === 0 ? (
        <div className="rounded-2xl border border-dashed border-slate-200 bg-white p-8 text-center text-sm text-slate-500 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-400">
          No services are available for your account right now.
        </div>
      ) : adminOps ? (
        <ServicesGrid
          id="services-page-heading"
          title="Platform tools"
          tiles={tiles}
          columnsClass="grid-cols-2 sm:grid-cols-3 lg:grid-cols-3"
        />
      ) : (
        <section aria-labelledby="services-page-heading">
          <h2 id="services-page-heading" className="sr-only">
            All services
          </h2>
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {tiles.map((tile) => (
              <ActionTile key={tile.id} size="primary" {...tile} />
            ))}
          </div>
        </section>
      )}
    </div>
  );
};

export default ServicesPage;
