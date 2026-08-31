import React from 'react';
import { FiCheckCircle, FiXCircle, FiAlertCircle, FiInfo } from 'react-icons/fi';

const Badge = ({ variant = 'default', children, icon, size = 'md', className = '' }) => {
  const variants = {
    default: 'bg-gray-100 dark:bg-slate-800 text-gray-800 dark:text-slate-200 border-gray-200 dark:border-slate-700',
    success: 'bg-green-50 dark:bg-green-950/40 text-green-800 dark:text-green-300 border-green-200 dark:border-green-800',
    warning: 'bg-yellow-50 dark:bg-yellow-950/40 text-yellow-800 dark:text-yellow-300 border-yellow-200 dark:border-yellow-800',
    error: 'bg-red-50 dark:bg-red-950/40 text-red-800 dark:text-red-300 border-red-200 dark:border-red-800',
    info: 'bg-blue-50 dark:bg-blue-950/40 text-blue-800 dark:text-blue-300 border-blue-200 dark:border-blue-800',
  };

  const iconMap = {
    success: FiCheckCircle,
    error: FiXCircle,
    warning: FiAlertCircle,
    info: FiInfo,
  };

  const sizeClasses = {
    sm: 'px-2 py-0.5 text-xs',
    md: 'px-3 py-1 text-sm',
    lg: 'px-4 py-1.5 text-base',
  };

  const Icon = icon || iconMap[variant];

  return (
    <span
      className={`
        inline-flex items-center gap-1.5
        font-semibold rounded-full border
        ${variants[variant]}
        ${sizeClasses[size]}
        ${className}
      `}
    >
      {Icon && <Icon size={size === 'sm' ? 12 : size === 'md' ? 14 : 16} />}
      {children}
    </span>
  );
};

export default Badge;
