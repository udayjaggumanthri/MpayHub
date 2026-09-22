import React from 'react';
import ActionTile from './ActionTile';

/**
 * Dense grid of service entry points. Renders nothing when the role has no
 * tiles, so the dashboard never shows an empty heading.
 *
 * @param {{
 *   id: string,
 *   title: string,
 *   tiles: Array<object>,
 *   headerAction?: React.ReactNode,
 *   columnsClass?: string,
 * }} props
 */
const ServicesGrid = ({
  id,
  title,
  tiles = [],
  headerAction = null,
  columnsClass = 'grid-cols-2 sm:grid-cols-3 lg:grid-cols-4',
}) => {
  if (!tiles.length) return null;

  return (
    <section aria-labelledby={id}>
      <div className="mb-2.5 flex items-center justify-between gap-2">
        <h2
          id={id}
          className="text-[12px] font-semibold uppercase tracking-[0.12em] text-slate-500 dark:text-slate-400"
        >
          {title}
        </h2>
        {headerAction}
      </div>
      <div className={`grid gap-3 ${columnsClass}`}>
        {tiles.map((tile) => (
          <ActionTile key={tile.id} size="compact" {...tile} />
        ))}
      </div>
    </section>
  );
};

export default ServicesGrid;
