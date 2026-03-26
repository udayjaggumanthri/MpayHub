import React from 'react';
import { FiCheckCircle, FiXCircle, FiAlertCircle, FiInfo } from 'react-icons/fi';

const Badge = ({ variant = 'default', children, icon, size = 'md', className = '' }) => {
  const variants = {
    default: 'bg-gray-100 text-gray-800 border-gray-200',
    success: 'bg-green-50 text-green-800 border-green-200',
    warning: 'bg-yellow-50 text-yellow-800 border-yellow-200',
    error: 'bg-red-50 text-red-800 border-red-200',
    info: 'bg-blue-50 text-blue-800 border-blue-200',
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
