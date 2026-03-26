import React from 'react';
import { FiInbox, FiSearch, FiFileText } from 'react-icons/fi';

const EmptyState = ({
  icon: Icon = FiInbox,
  title = 'No data found',
  description,
  action,
  className = '',
}) => {
  return (
    <div className={`text-center py-12 px-4 ${className}`}>
      <div className="flex justify-center mb-4">
        <div className="rounded-full bg-gray-100 p-4">
          <Icon className="text-gray-400" size={48} />
        </div>
      </div>
      <h3 className="text-lg font-semibold text-gray-900 mb-2">{title}</h3>
      {description && (
        <p className="text-sm text-gray-500 mb-6 max-w-md mx-auto">{description}</p>
      )}
      {action && <div>{action}</div>}
    </div>
  );
};

export default EmptyState;
