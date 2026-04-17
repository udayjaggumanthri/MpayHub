import React from 'react';
import { formatCurrency } from '../../utils/formatters';
import { FiArrowRight } from 'react-icons/fi';
import { FaWallet, FaChartLine, FaReceipt, FaBuildingColumns } from 'react-icons/fa6';

const WalletCard = ({ type, amount, onClick }) => {
  const config = {
    main: {
      title: 'Main Wallet',
      icon: FaWallet,
      iconBg: 'bg-gradient-to-br from-blue-500 via-blue-600 to-indigo-600',
      gradient: 'from-blue-50 via-blue-50 to-indigo-50',
      borderColor: 'border-blue-300',
      textColor: 'text-blue-700',
      amountColor: 'text-blue-900',
      hoverBg: 'hover:from-blue-100 hover:via-blue-100 hover:to-indigo-100',
      shadow: 'shadow-blue-200',
    },
    commission: {
      title: 'Commission Wallet',
      icon: FaChartLine,
      iconBg: 'bg-gradient-to-br from-blue-500 via-blue-600 to-indigo-600',
      gradient: 'from-blue-50 via-blue-50 to-indigo-50',
      borderColor: 'border-blue-300',
      textColor: 'text-blue-700',
      amountColor: 'text-blue-900',
      hoverBg: 'hover:from-blue-100 hover:via-blue-100 hover:to-indigo-100',
      shadow: 'shadow-blue-200',
    },
    bbps: {
      title: 'BBPS Wallet',
      icon: FaReceipt,
      iconBg: 'bg-gradient-to-br from-blue-500 via-blue-600 to-indigo-600',
      gradient: 'from-blue-50 via-blue-50 to-indigo-50',
      borderColor: 'border-blue-300',
      textColor: 'text-blue-700',
      amountColor: 'text-blue-900',
      hoverBg: 'hover:from-blue-100 hover:via-blue-100 hover:to-indigo-100',
      shadow: 'shadow-blue-200',
    },
    profit: {
      title: 'Profit Wallet',
      icon: FaBuildingColumns,
      iconBg: 'bg-gradient-to-br from-blue-500 via-blue-600 to-indigo-600',
      gradient: 'from-blue-50 via-blue-50 to-indigo-50',
      borderColor: 'border-blue-300',
      textColor: 'text-blue-700',
      amountColor: 'text-blue-900',
      hoverBg: 'hover:from-blue-100 hover:via-blue-100 hover:to-indigo-100',
      shadow: 'shadow-blue-200',
    },
  };

  const cardConfig = config[type] || config.main;
  const Icon = cardConfig.icon;

  return (
    <div
      onClick={onClick}
      className={`
        relative overflow-hidden
        bg-gradient-to-br ${cardConfig.gradient}
        ${cardConfig.borderColor} border-2
        rounded-2xl p-6
        transition-all duration-300
        ${onClick ? 'cursor-pointer hover:shadow-xl hover:scale-[1.02] ' + cardConfig.hoverBg : ''}
      `}
    >
      {/* Decorative Background Pattern */}
      <div className="absolute top-0 right-0 -mt-4 -mr-4 w-24 h-24 opacity-10">
        <div className={`w-full h-full ${cardConfig.iconBg} rounded-full blur-2xl`}></div>
      </div>

      <div className="relative z-10">
        {/* Header */}
        <div className="flex items-center justify-between mb-6">
          <div className={`${cardConfig.iconBg} p-4 rounded-2xl shadow-lg transform hover:scale-110 transition-transform`}>
            <Icon className="text-white" size={28} />
          </div>
          {onClick && (
            <div className={`${cardConfig.textColor} opacity-60 hover:opacity-100 transition-opacity`}>
              <FiArrowRight size={22} />
            </div>
          )}
        </div>

        {/* Content */}
        <div>
          <p className={`text-sm font-semibold ${cardConfig.textColor} mb-2 uppercase tracking-wide`}>
            {cardConfig.title}
          </p>
          <p className={`text-3xl font-bold ${cardConfig.amountColor}`}>
            {formatCurrency(amount)}
          </p>
        </div>

        {/* Bottom Accent */}
        <div className={`mt-4 h-1 ${cardConfig.iconBg} rounded-full opacity-50`}></div>
      </div>
    </div>
  );
};

export default WalletCard;
