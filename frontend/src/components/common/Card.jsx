import React from 'react';

const Card = ({
  children,
  title,
  subtitle,
  headerAction,
  footer,
  className = '',
  padding = 'lg',
  shadow = 'md',
  border = true,
  hover = false,
}) => {
  const paddingClasses = {
    none: '',
    sm: 'p-3 sm:p-4',
    md: 'p-4 sm:p-5',
    lg: 'p-4 sm:p-6',
    xl: 'p-6 sm:p-8',
  };

  const shadowClasses = {
    none: '',
    sm: 'shadow-sm',
    md: 'shadow-md',
    lg: 'shadow-lg',
    xl: 'shadow-xl',
  };

  const baseClasses = `
    bg-white rounded-xl
    ${border ? 'border border-gray-200' : ''}
    ${shadowClasses[shadow]}
    ${hover ? 'transition-all duration-200 hover:shadow-lg hover:scale-[1.01]' : ''}
    ${paddingClasses[padding]}
    ${className}
  `;

  return (
    <div className={baseClasses}>
      {(title || subtitle || headerAction) && (
        <div className="mb-4 sm:mb-6 pb-3 sm:pb-4 border-b border-gray-200 flex flex-col sm:flex-row sm:items-start sm:justify-between gap-3">
          <div>
            {title && (
              <h3 className="text-lg sm:text-xl font-bold text-gray-900">{title}</h3>
            )}
            {subtitle && (
              <p className="mt-1 text-xs sm:text-sm text-gray-600">{subtitle}</p>
            )}
          </div>
          {headerAction && <div className="sm:ml-4">{headerAction}</div>}
        </div>
      )}
      <div>{children}</div>
      {footer && (
        <div className="mt-6 pt-4 border-t border-gray-200">{footer}</div>
      )}
    </div>
  );
};

export default Card;
