import React from 'react';

const LoadingSpinner = ({ size = 'md', fullScreen = false, text = 'Loading...', className = '' }) => {
  const sizeClasses = {
    sm: 'h-4 w-4',
    md: 'h-8 w-8',
    lg: 'h-12 w-12',
    xl: 'h-16 w-16',
  };

  const spinner = (
    <div className={`flex flex-col items-center justify-center ${className}`}>
      <div
        className={`
          animate-spin rounded-full border-b-2 border-blue-600
          ${sizeClasses[size]}
        `}
      ></div>
      {text && (
        <p className={`mt-4 text-gray-600 ${size === 'sm' ? 'text-xs' : size === 'lg' || size === 'xl' ? 'text-base' : 'text-sm'}`}>
          {text}
        </p>
      )}
    </div>
  );

  if (fullScreen) {
    return (
      <div className="fixed inset-0 z-50 flex items-center justify-center bg-white bg-opacity-75">
        {spinner}
      </div>
    );
  }

  return spinner;
};

export default LoadingSpinner;
