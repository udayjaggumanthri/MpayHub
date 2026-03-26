import React from 'react';
import { inputVariants } from '../../design/DesignSystem';
import { FiAlertCircle } from 'react-icons/fi';

const Input = ({
  label,
  type = 'text',
  placeholder,
  value,
  onChange,
  error,
  helperText,
  icon: Icon,
  iconPosition = 'left',
  rightIcon: RightIcon,
  onRightIconClick,
  required = false,
  disabled = false,
  fullWidth = true,
  size = 'md',
  className = '',
  ...props
}) => {
  const sizeClasses = {
    sm: 'px-3 py-2 text-sm',
    md: 'px-4 py-2.5 text-base',
    lg: 'px-5 py-3 text-lg',
  };

  const baseClasses = `
    block border rounded-lg
    transition-all duration-200
    focus:outline-none focus:ring-2 focus:ring-offset-1
    disabled:bg-gray-50 disabled:text-gray-500 disabled:cursor-not-allowed
    ${sizeClasses[size]}
    ${fullWidth ? 'w-full' : ''}
    ${Icon && iconPosition === 'left' ? 'pl-11' : ''}
    ${RightIcon || error ? 'pr-11' : ''}
    ${error ? inputVariants.error : inputVariants.default}
    ${className}
  `;

  return (
    <div className={fullWidth ? 'w-full' : ''}>
      {label && (
        <label className="block text-sm font-medium text-gray-700 mb-2">
          {label}
          {required && <span className="text-red-500 ml-1">*</span>}
        </label>
      )}
      <div className="relative">
        {Icon && iconPosition === 'left' && (
          <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
            <Icon className="text-gray-400" size={20} />
          </div>
        )}
        <input
          type={type}
          value={value}
          onChange={onChange}
          placeholder={placeholder}
          disabled={disabled}
          className={baseClasses}
          {...props}
        />
        {error && !RightIcon && (
          <div className="absolute inset-y-0 right-0 pr-3 flex items-center pointer-events-none">
            <FiAlertCircle className="text-red-500" size={20} />
          </div>
        )}
        {RightIcon && !error && (
          <button
            type="button"
            onClick={onRightIconClick}
            className="absolute inset-y-0 right-0 pr-3 flex items-center text-gray-500 hover:text-gray-700 transition-colors"
          >
            <RightIcon size={20} />
          </button>
        )}
      </div>
      {error && (
        <p className="mt-1.5 text-sm text-red-600 flex items-center">
          <FiAlertCircle className="mr-1" size={14} />
          {error}
        </p>
      )}
      {helperText && !error && (
        <p className="mt-1.5 text-sm text-gray-500">{helperText}</p>
      )}
    </div>
  );
};

export default Input;
