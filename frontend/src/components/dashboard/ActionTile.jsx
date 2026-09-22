import React from 'react';
import { FiChevronRight } from 'react-icons/fi';

/** Icon chip colours — one entry per tone used by the dashboard catalog. */
const TONE_CLASSES = {
  blue: 'from-blue-600 to-indigo-700',
  sky: 'from-sky-500 to-blue-700',
  indigo: 'from-indigo-600 to-violet-700',
  violet: 'from-violet-600 to-fuchsia-700',
  emerald: 'from-emerald-600 to-teal-700',
  amber: 'from-amber-500 to-orange-600',
  rose: 'from-rose-500 to-pink-600',
  slate: 'from-slate-600 to-slate-800',
};

/**
 * Shared dashboard tile.
 *
 * `primary` is the wide row used for money actions; `compact` is the dense
 * services grid cell. Disabled tiles stay in place with a reason chip so the
 * grid does not reflow when a module is paused.
 */
const ActionTile = ({
  title,
  description,
  icon: Icon,
  iconImage,
  tone = 'blue',
  size = 'compact',
  badge = null,
  note = '',
  disabled = false,
  onClick,
}) => {
  const gradient = TONE_CLASSES[tone] || TONE_CLASSES.blue;
  const isPrimary = size === 'primary';

  const base =
    'group relative flex w-full rounded-xl border bg-white text-left shadow-sm transition dark:bg-slate-900 focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-500 focus-visible:ring-offset-2 dark:focus-visible:ring-offset-slate-950';
  const interactive = disabled
    ? 'cursor-not-allowed border-slate-200 opacity-70 dark:border-slate-800'
    : 'border-slate-200/90 hover:border-slate-300 hover:shadow-md motion-safe:hover:-translate-y-0.5 dark:border-slate-700/90 dark:hover:border-slate-600';

  const iconChip = iconImage ? (
    <img
      src={iconImage}
      alt=""
      aria-hidden
      className={isPrimary ? 'h-10 w-10 object-contain' : 'h-8 w-8 object-contain'}
    />
  ) : Icon ? (
    <span
      className={`inline-flex shrink-0 items-center justify-center rounded-xl bg-gradient-to-br shadow-sm ${gradient} ${
        isPrimary ? 'h-12 w-12' : 'h-9 w-9'
      }`}
    >
      <Icon className={isPrimary ? 'h-6 w-6 text-white' : 'h-5 w-5 text-white'} aria-hidden />
    </span>
  ) : null;

  return (
    <button
      type="button"
      onClick={disabled ? undefined : onClick}
      disabled={disabled}
      aria-label={note ? `${title} — ${note}` : title}
      className={`${base} ${interactive} ${
        isPrimary ? 'items-center gap-3 p-4' : 'flex-col items-start gap-2 p-3 sm:p-3.5'
      }`}
    >
      <span className={isPrimary ? 'flex items-center gap-3' : 'flex w-full items-start justify-between gap-2'}>
        {iconChip}
        {!isPrimary && badge ? (
          <span className="inline-flex min-w-[1.25rem] items-center justify-center rounded-full bg-amber-500 px-1.5 py-0.5 text-[11px] font-bold text-white">
            {badge}
          </span>
        ) : null}
      </span>

      <span className="min-w-0 flex-1">
        <span className="flex items-center gap-2">
          <span
            className={`block truncate font-semibold text-slate-900 dark:text-slate-100 ${
              isPrimary ? 'text-base' : 'text-sm'
            }`}
          >
            {title}
          </span>
          {isPrimary && badge ? (
            <span className="inline-flex min-w-[1.25rem] items-center justify-center rounded-full bg-amber-500 px-1.5 py-0.5 text-[11px] font-bold text-white">
              {badge}
            </span>
          ) : null}
        </span>
        {description ? (
          <span
            className={`mt-0.5 block text-slate-500 dark:text-slate-400 ${
              isPrimary ? 'text-sm' : 'line-clamp-2 text-[11px] leading-snug'
            }`}
          >
            {description}
          </span>
        ) : null}
        {note ? (
          <span className="mt-1.5 inline-flex items-center rounded-full bg-slate-100 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-slate-600 dark:bg-slate-800 dark:text-slate-300">
            {note}
          </span>
        ) : null}
      </span>

      {isPrimary && !disabled ? (
        <FiChevronRight
          className="h-5 w-5 shrink-0 text-slate-300 transition motion-safe:group-hover:translate-x-0.5 group-hover:text-slate-500 dark:text-slate-600"
          aria-hidden
        />
      ) : null}
    </button>
  );
};

export default ActionTile;
