import React from 'react';
import { formatCurrency } from '../../utils/formatters';
import { FiArrowRight } from 'react-icons/fi';
import { FaWallet, FaChartLine, FaNetworkWired } from 'react-icons/fa6';
import { PERIOD_LABELS } from '../../context/WalletContext';

const WalletCard = ({
  type,
  amount,
  onClick,
  subtitle,
  period,
  onPeriodChange,
  refreshing = false,
  /** Compact layout for operator dashboards (less vertical space). */
  compact = false,
}) => {
  const config = {
    main: {
      title: 'Main Wallet',
      subtitle: 'Available balance',
      icon: FaWallet,
      iconBg: 'bg-gradient-to-br from-blue-600 to-indigo-700',
      gradient: 'from-slate-50 dark:from-slate-900 via-white dark:via-slate-900 to-blue-50/90 dark:to-blue-950/40',
      borderColor: 'border-slate-200/90 dark:border-slate-700/90',
      ring: 'ring-1 ring-blue-100/80 dark:ring-blue-900/80',
      textColor: 'text-slate-600 dark:text-slate-400',
      amountColor: 'text-slate-900 dark:text-slate-100',
      accent: 'bg-blue-600',
      hoverBg: 'hover:shadow-lg hover:ring-blue-200/60 dark:hover:ring-blue-800/60',
      glow: 'group-hover:opacity-100 group-hover:scale-110',
    },
    distributed: {
      title: 'Distributed Balance',
      subtitle: "All users' main wallets",
      icon: FaNetworkWired,
      iconBg: 'bg-gradient-to-br from-cyan-600 to-sky-700',
      gradient: 'from-cyan-50/90 dark:from-cyan-950/40 via-white dark:via-slate-900 to-sky-50/70 dark:to-sky-950/40',
      borderColor: 'border-cyan-200/80 dark:border-cyan-800/80',
      ring: 'ring-1 ring-cyan-100/80 dark:ring-cyan-900/80',
      textColor: 'text-cyan-900/85 dark:text-cyan-300/85',
      amountColor: 'text-cyan-950 dark:text-cyan-200',
      accent: 'bg-cyan-500',
      hoverBg: 'hover:shadow-lg hover:ring-cyan-200/60 dark:hover:ring-cyan-800/60',
      glow: 'group-hover:opacity-100 group-hover:scale-110',
    },
    commission: {
      title: 'Commission',
      subtitle: 'Credited to your main wallet',
      icon: FaChartLine,
      iconBg: 'bg-gradient-to-br from-emerald-600 to-teal-700',
      gradient: 'from-emerald-50/90 dark:from-emerald-950/40 via-white dark:via-slate-900 to-teal-50/70 dark:to-teal-950/40',
      borderColor: 'border-emerald-200/80 dark:border-emerald-800/80',
      ring: 'ring-1 ring-emerald-100/80 dark:ring-emerald-900/80',
      textColor: 'text-emerald-800/90 dark:text-emerald-300/90',
      amountColor: 'text-emerald-950 dark:text-emerald-200',
      accent: 'bg-emerald-500',
      hoverBg: 'hover:shadow-lg hover:ring-emerald-200/60 dark:hover:ring-emerald-800/60',
      glow: 'group-hover:opacity-100 group-hover:scale-110',
    },
  };

  const resolvedType = type === 'earnings' ? 'commission' : type;
  const cardConfig = config[resolvedType] || config.main;
  const Icon = cardConfig.icon;
  const displaySubtitle =
    subtitle ||
    (resolvedType === 'commission' && period
      ? PERIOD_LABELS[period] || cardConfig.subtitle
      : cardConfig.subtitle);
  const showPeriod = resolvedType === 'commission' && typeof onPeriodChange === 'function';

  if (compact) {
    return (
      <div
        onClick={onClick}
        role={onClick ? 'button' : undefined}
        tabIndex={onClick ? 0 : undefined}
        onKeyDown={
          onClick
            ? (e) => {
                if (e.key === 'Enter' || e.key === ' ') {
                  e.preventDefault();
                  onClick();
                }
              }
            : undefined
        }
          className={`
          group relative flex h-full flex-col overflow-hidden
          bg-gradient-to-br ${cardConfig.gradient}
          ${cardConfig.borderColor} border ${cardConfig.ring}
          rounded-2xl px-2.5 py-2.5 sm:px-3.5 sm:py-3
          transition-all duration-300 ease-out
          ${onClick ? `cursor-pointer ${cardConfig.hoverBg} motion-safe:hover:-translate-y-1 motion-safe:hover:scale-[1.01]` : ''}
        `}
      >
        <div
          className={`pointer-events-none absolute -right-6 -top-6 h-20 w-20 rounded-full bg-gradient-to-br from-white/50 to-transparent opacity-60 blur-xl transition duration-500 dark:from-white/10 ${cardConfig.glow}`}
        />
        <div className={`absolute bottom-0 left-0 h-0.5 w-full origin-left scale-x-0 transition-transform duration-500 ${cardConfig.accent} group-hover:scale-x-100`} />

        <div className="relative z-10 flex min-h-0 flex-1 items-start gap-2 sm:gap-2.5">
          <div
            className={`${cardConfig.iconBg} shrink-0 rounded-lg p-1.5 shadow-md transition duration-300 motion-safe:group-hover:rotate-3 motion-safe:group-hover:scale-105 sm:p-2`}
          >
            <Icon className="text-white" size={14} />
          </div>
          <div className="min-w-0 flex-1">
            <div className="flex items-center justify-between gap-1">
              <p className={`text-[10px] font-bold uppercase tracking-wider ${cardConfig.textColor}`}>
                {cardConfig.title}
              </p>
              {onClick ? (
                <span className="inline-flex items-center gap-0.5 text-[10px] font-semibold text-slate-500 opacity-70 transition group-hover:opacity-100 dark:text-slate-400">
                  <FiArrowRight size={10} className="transition group-hover:translate-x-0.5" />
                </span>
              ) : null}
            </div>
            <p
              className={`mt-0.5 text-base font-bold tabular-nums tracking-tight sm:text-lg ${cardConfig.amountColor} ${
                refreshing ? 'opacity-60' : ''
              }`}
            >
              {formatCurrency(amount)}
            </p>
            {displaySubtitle ? (
              <p className={`mt-0.5 truncate text-[10px] leading-tight sm:text-[11px] ${cardConfig.textColor}`}>
                {displaySubtitle}
              </p>
            ) : null}
            {showPeriod ? (
              <div
                className="mt-1.5 flex flex-wrap gap-1"
                onClick={(e) => e.stopPropagation()}
                onKeyDown={(e) => e.stopPropagation()}
                role="group"
                aria-label="Commission period"
              >
                {['day', 'month', 'year'].map((p) => (
                  <button
                    key={p}
                    type="button"
                    onClick={(e) => {
                      e.stopPropagation();
                      onPeriodChange(p);
                    }}
                    className={`rounded-full px-1.5 py-0.5 text-[9px] font-semibold transition sm:px-2 sm:text-[10px] ${
                      period === p
                        ? 'bg-emerald-600 text-white shadow-sm'
                        : 'bg-white/80 text-emerald-900 ring-1 ring-emerald-200/80 hover:bg-emerald-50 dark:bg-slate-800/80 dark:text-emerald-200 dark:ring-emerald-800'
                    }`}
                  >
                    {p === 'day' ? 'Day' : p === 'month' ? 'Month' : 'Year'}
                  </button>
                ))}
              </div>
            ) : null}
          </div>
        </div>
      </div>
    );
  }

  return (
    <div
      onClick={onClick}
      role={onClick ? 'button' : undefined}
      tabIndex={onClick ? 0 : undefined}
      onKeyDown={
        onClick
          ? (e) => {
              if (e.key === 'Enter' || e.key === ' ') {
                e.preventDefault();
                onClick();
              }
            }
          : undefined
      }
      className={`
        group relative overflow-hidden
        bg-gradient-to-br ${cardConfig.gradient}
        ${cardConfig.borderColor} border ${cardConfig.ring}
        rounded-2xl p-4 sm:p-5
        transition-all duration-300
        ${onClick ? `cursor-pointer ${cardConfig.hoverBg} motion-safe:hover:-translate-y-0.5` : ''}
      `}
    >
      <div className="pointer-events-none absolute -right-8 -top-8 h-32 w-32 rounded-full bg-gradient-to-br from-white/40 dark:from-slate-900/40 to-transparent blur-2xl" />

      <div className="relative z-10">
        <div className="mb-3 flex items-start justify-between gap-3">
          <div className={`${cardConfig.iconBg} rounded-xl p-2.5 shadow-md sm:p-3`}>
            <Icon className="text-white" size={20} />
          </div>
          {onClick ? (
            <span className="inline-flex items-center gap-1 rounded-full bg-white/70 px-2.5 py-1 text-[11px] font-semibold text-slate-600 shadow-sm ring-1 ring-slate-200/80 dark:bg-slate-800/70 dark:text-slate-300 dark:ring-slate-700">
              Ledger
              <FiArrowRight size={12} />
            </span>
          ) : null}
        </div>

        <p className={`text-[11px] font-bold uppercase tracking-wider ${cardConfig.textColor}`}>
          {cardConfig.title}
        </p>
        <p
          className={`mt-1.5 text-xl font-bold tabular-nums tracking-tight sm:text-2xl ${cardConfig.amountColor} ${
            refreshing ? 'opacity-60' : ''
          }`}
        >
          {formatCurrency(amount)}
        </p>
        {displaySubtitle ? (
          <p className={`mt-1.5 text-xs ${cardConfig.textColor}`}>{displaySubtitle}</p>
        ) : null}

        {showPeriod ? (
          <div
            className="mt-3 flex gap-1"
            onClick={(e) => e.stopPropagation()}
            onKeyDown={(e) => e.stopPropagation()}
            role="group"
            aria-label="Commission period"
          >
            {['day', 'month', 'year'].map((p) => (
              <button
                key={p}
                type="button"
                onClick={(e) => {
                  e.stopPropagation();
                  onPeriodChange(p);
                }}
                className={`rounded-full px-2.5 py-1 text-[11px] font-semibold transition ${
                  period === p
                    ? 'bg-emerald-600 text-white shadow-sm'
                    : 'bg-white/80 text-emerald-900 ring-1 ring-emerald-200/80 hover:bg-emerald-50 dark:bg-slate-800/80 dark:text-emerald-200 dark:ring-emerald-800'
                }`}
              >
                {p === 'day' ? 'Day' : p === 'month' ? 'Month' : 'Year'}
              </button>
            ))}
          </div>
        ) : null}
      </div>

      <div className={`absolute bottom-0 left-0 right-0 h-1 ${cardConfig.accent}`} />
    </div>
  );
};

export default WalletCard;
