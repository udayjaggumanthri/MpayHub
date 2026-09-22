import React from 'react';
import { FaWallet } from 'react-icons/fa6';
import { HiArrowRight, HiPaperAirplane, HiPlus } from 'react-icons/hi2';

/**
 * High-contrast brand gradients — mid/dark stops only so white copy stays readable
 * on light & dark themes (avoids washed sky/lime ends).
 */
const ACTION_STYLES = {
  'load-money': {
    shell:
      'bg-gradient-to-br from-[#1e40af] via-[#2563eb] to-[#1d4ed8] shadow-[0_10px_28px_-8px_rgba(37,99,235,0.55)] hover:shadow-[0_14px_32px_-8px_rgba(37,99,235,0.65)] focus-visible:ring-blue-600 dark:from-[#1e3a8a] dark:via-[#1d4ed8] dark:to-[#2563eb]',
    band: 'from-white/15 via-transparent to-black/10',
    plusFg: 'text-[#1d4ed8]',
  },
  payout: {
    shell:
      'bg-gradient-to-br from-[#065f46] via-[#059669] to-[#047857] shadow-[0_10px_28px_-8px_rgba(5,150,105,0.55)] hover:shadow-[0_14px_32px_-8px_rgba(5,150,105,0.65)] focus-visible:ring-emerald-600 dark:from-[#064e3b] dark:via-[#047857] dark:to-[#059669]',
    band: 'from-white/12 via-transparent to-black/10',
    plusFg: 'text-emerald-700',
  },
  'admin-qr-ops': {
    shell:
      'bg-gradient-to-br from-[#b45309] via-[#d97706] to-[#c2410c] shadow-amber-700/35 hover:shadow-amber-700/50 focus-visible:ring-amber-600',
    band: 'from-white/12 via-transparent to-black/10',
    plusFg: 'text-amber-700',
  },
  'admin-payin-report': {
    shell:
      'bg-gradient-to-br from-[#3730a3] via-[#4f46e5] to-[#4338ca] shadow-indigo-700/35 hover:shadow-indigo-700/50 focus-visible:ring-indigo-600',
    band: 'from-white/12 via-transparent to-black/10',
    plusFg: 'text-indigo-700',
  },
};

function ActionIcon({ actionId, Icon, iconImage, plusFg }) {
  if (iconImage) {
    return <img src={iconImage} alt="" className="h-6 w-6 object-contain brightness-0 invert" aria-hidden />;
  }
  if (actionId === 'load-money') {
    return (
      <span className="relative inline-flex h-6 w-6 items-center justify-center">
        <FaWallet className="h-5 w-5 text-white drop-shadow-sm" aria-hidden />
        <span
          className={`absolute -bottom-0.5 -right-1 inline-flex h-3.5 w-3.5 items-center justify-center rounded-full bg-white shadow-sm ${plusFg || 'text-blue-700'}`}
        >
          <HiPlus className="h-2.5 w-2.5 stroke-[3]" aria-hidden />
        </span>
      </span>
    );
  }
  if (actionId === 'payout') {
    return <HiPaperAirplane className="h-6 w-6 -rotate-45 text-white drop-shadow-sm" aria-hidden />;
  }
  if (Icon) {
    return <Icon className="h-6 w-6 text-white drop-shadow-sm" aria-hidden />;
  }
  return null;
}

/**
 * Load Money / Payout — high-contrast theme cards with shine / float motion.
 */
const PrimaryActionButtons = ({ actions = [] }) => {
  if (!actions.length) return null;

  return (
    <div
      className="grid grid-cols-2 gap-2 sm:gap-3 lg:contents"
      role="group"
      aria-label="Wallet actions"
    >
      {actions.map((action, index) => {
        const Icon = action.icon;
        const style = ACTION_STYLES[action.id] || ACTION_STYLES['load-money'];
        const subtitle = action.disabled
          ? action.note || 'Unavailable'
          : action.description || action.shortLabel || '';
        const riseDelay =
          index === 0 ? 'mpay-rise-in-delay-2' : index === 1 ? 'mpay-rise-in-delay-3' : '';

        return (
          <button
            key={action.id}
            type="button"
            onClick={action.disabled ? undefined : action.onClick}
            disabled={action.disabled}
            title={action.disabled ? action.note || 'Unavailable' : action.description}
            className={`group relative flex min-h-[88px] items-center gap-2 overflow-hidden rounded-2xl p-3 text-left text-white transition duration-300 ease-out focus:outline-none focus-visible:ring-2 focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-70 disabled:saturate-75 motion-safe:mpay-rise-in motion-safe:hover:-translate-y-1 motion-safe:hover:scale-[1.015] motion-safe:active:scale-[0.985] sm:min-h-[104px] sm:gap-3 sm:p-4 lg:min-h-[120px] lg:p-4 ${style.shell} ${riseDelay}`}
          >
            {/* Depth band — keeps highlight without washing white text */}
            <span
              className={`pointer-events-none absolute inset-0 bg-gradient-to-br ${style.band}`}
              aria-hidden
            />
            {/* Text-side scrim for WCAG contrast on description */}
            <span
              className="pointer-events-none absolute inset-y-0 left-0 w-[72%] bg-gradient-to-r from-black/25 via-black/10 to-transparent"
              aria-hidden
            />
            <span className="mpay-action-shine" aria-hidden />

            <span className="relative z-10 flex min-w-0 flex-1 flex-col gap-2 sm:gap-2.5">
              <span className="mpay-icon-float inline-flex h-10 w-10 items-center justify-center rounded-full bg-white/25 shadow-md ring-1 ring-white/40 backdrop-blur-sm transition duration-300 motion-safe:group-hover:scale-110 motion-safe:group-hover:bg-white/35 sm:h-11 sm:w-11">
                <ActionIcon
                  actionId={action.id}
                  Icon={Icon}
                  iconImage={action.iconImage}
                  plusFg={style.plusFg}
                />
              </span>

              <span className="min-w-0 pr-1 drop-shadow-sm">
                <span className="block text-[13px] font-bold leading-tight tracking-tight text-white sm:text-base lg:text-lg">
                  {action.title}
                </span>
                <span className="mt-0.5 block text-[10px] font-medium leading-snug text-white/95 line-clamp-2 sm:mt-1 sm:text-xs lg:text-[13px]">
                  {subtitle}
                </span>
              </span>
            </span>

            <span className="relative z-10 inline-flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-white/25 text-white ring-1 ring-white/40 transition duration-300 motion-safe:group-hover:bg-white/40 motion-safe:group-hover:shadow-md sm:h-9 sm:w-9">
              {action.badge != null ? (
                <span className="text-[11px] font-bold tabular-nums">{action.badge}</span>
              ) : (
                <HiArrowRight className="mpay-chevron-nudge h-4 w-4 drop-shadow-sm" aria-hidden />
              )}
            </span>
          </button>
        );
      })}
    </div>
  );
};

export default PrimaryActionButtons;
