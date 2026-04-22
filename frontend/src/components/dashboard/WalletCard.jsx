import React from 'react';
import { formatCurrency } from '../../utils/formatters';
import { FiArrowRight } from 'react-icons/fi';
import { FaWallet, FaChartLine, FaReceipt, FaBuildingColumns } from 'react-icons/fa6';

const WalletCard = ({ type, amount, onClick }) => {
  const config = {
    main: {
      title: 'Main Wallet',
      subtitle: 'Available balance',
      icon: FaWallet,
      iconBg: 'bg-gradient-to-br from-blue-600 to-indigo-700',
      gradient: 'from-slate-50 via-white to-blue-50/90',
      borderColor: 'border-slate-200/90',
      ring: 'ring-1 ring-blue-100/80',
      textColor: 'text-slate-600',
      amountColor: 'text-slate-900',
      accent: 'bg-blue-600',
      hoverBg: 'hover:shadow-lg hover:ring-blue-200/60',
    },
    commission: {
      title: 'Commission',
      subtitle: 'Earnings from your network',
      icon: FaChartLine,
      iconBg: 'bg-gradient-to-br from-emerald-600 to-teal-700',
      gradient: 'from-emerald-50/90 via-white to-teal-50/70',
      borderColor: 'border-emerald-200/80',
      ring: 'ring-1 ring-emerald-100/80',
      textColor: 'text-emerald-800/90',
      amountColor: 'text-emerald-950',
      accent: 'bg-emerald-500',
      hoverBg: 'hover:shadow-lg hover:ring-emerald-200/60',
    },
    bbps: {
      title: 'BBPS Wallet',
      subtitle: 'Bill payment balance',
      icon: FaReceipt,
      iconBg: 'bg-gradient-to-br from-violet-600 to-purple-700',
      gradient: 'from-violet-50/80 via-white to-purple-50/70',
      borderColor: 'border-violet-200/80',
      ring: 'ring-1 ring-violet-100/80',
      textColor: 'text-violet-900/85',
      amountColor: 'text-violet-950',
      accent: 'bg-violet-500',
      hoverBg: 'hover:shadow-lg hover:ring-violet-200/60',
    },
    profit: {
      title: 'Profit Wallet',
      subtitle: 'Platform & gateway share',
      icon: FaBuildingColumns,
      iconBg: 'bg-gradient-to-br from-amber-600 to-orange-700',
      gradient: 'from-amber-50/90 via-white to-orange-50/60',
      borderColor: 'border-amber-200/90',
      ring: 'ring-1 ring-amber-100/80',
      textColor: 'text-amber-950/90',
      amountColor: 'text-amber-950',
      accent: 'bg-amber-500',
      hoverBg: 'hover:shadow-lg hover:ring-amber-200/60',
    },
  };

  const cardConfig = config[type] || config.main;
  const Icon = cardConfig.icon;

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
        relative overflow-hidden
        bg-gradient-to-br ${cardConfig.gradient}
        ${cardConfig.borderColor} border ${cardConfig.ring}
        rounded-2xl p-6
        transition-all duration-300
        ${onClick ? `cursor-pointer ${cardConfig.hoverBg} hover:-translate-y-0.5` : ''}
      `}
    >
      <div className="pointer-events-none absolute -right-8 -top-8 h-32 w-32 rounded-full bg-gradient-to-br from-white/40 to-transparent blur-2xl" />

      <div className="relative z-10">
        <div className="mb-5 flex items-start justify-between gap-3">
          <div className={`${cardConfig.iconBg} rounded-xl p-3.5 shadow-md`}>
            <Icon className="text-white" size={24} />
          </div>
          {onClick && (
            <span
              className={`inline-flex items-center gap-1 rounded-full bg-white/80 px-2 py-1 text-xs font-medium text-slate-600 shadow-sm ${cardConfig.textColor}`}
            >
              Ledger
              <FiArrowRight size={14} />
            </span>
          )}
        </div>

        <div>
          <p className={`text-xs font-semibold uppercase tracking-wider ${cardConfig.textColor}`}>
            {cardConfig.title}
          </p>
          <p className="mt-0.5 text-[11px] text-slate-500">{cardConfig.subtitle}</p>
          <p className={`mt-3 text-3xl font-bold tabular-nums tracking-tight ${cardConfig.amountColor}`}>
            {formatCurrency(amount)}
          </p>
        </div>

        <div className={`mt-5 h-1 rounded-full ${cardConfig.accent} opacity-80`} />
      </div>
    </div>
  );
};

export default WalletCard;
