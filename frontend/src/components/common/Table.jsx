import React from 'react';
import { FiArrowUp, FiArrowDown } from 'react-icons/fi';

const Table = ({
  columns,
  data,
  loading = false,
  emptyMessage = 'No data available',
  onSort,
  sortColumn,
  sortDirection,
  rowClassName,
  onRowClick,
  className = '',
}) => {
  const handleSort = (column) => {
    if (onSort && column.sortable !== false) {
      onSort(column.key);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center py-12">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto"></div>
          <p className="mt-4 text-gray-600 dark:text-slate-400">Loading...</p>
        </div>
      </div>
    );
  }

  if (!data || data.length === 0) {
    return (
      <div className="text-center py-12 text-gray-500 dark:text-slate-400">
        <p>{emptyMessage}</p>
      </div>
    );
  }

  return (
    <div className={`overflow-x-auto rounded-lg border border-gray-200 dark:border-slate-700 ${className}`}>
      <table className="min-w-full divide-y divide-gray-200 dark:divide-slate-700 bg-white dark:bg-slate-900">
        <thead className="bg-gray-50 dark:bg-slate-800/50">
          <tr>
            {columns.map((column, index) => (
              <th
                key={column.key || index}
                className={`
                  px-3 sm:px-4 md:px-6 py-3 text-left text-xs font-semibold text-gray-700 dark:text-slate-300 uppercase tracking-wider
                  ${column.sortable !== false && onSort ? 'cursor-pointer hover:bg-gray-100 dark:hover:bg-slate-700' : ''}
                  ${column.align === 'right' ? 'text-right' : column.align === 'center' ? 'text-center' : 'text-left'}
                  ${column.className || ''}
                `}
                onClick={() => handleSort(column)}
              >
                <div className={`flex items-center ${column.align === 'right' ? 'justify-end' : column.align === 'center' ? 'justify-center' : 'justify-start'}`}>
                  {column.icon && <column.icon className="mr-2" size={16} />}
                  <span>{column.label}</span>
                  {column.sortable !== false && onSort && (
                    <span className="ml-2 flex flex-col">
                      <FiArrowUp
                        className={`h-3 w-3 ${
                          sortColumn === column.key && sortDirection === 'asc'
                            ? 'text-blue-600 dark:text-blue-400'
                            : 'text-gray-400 dark:text-slate-500'
                        }`}
                      />
                      <FiArrowDown
                        className={`h-3 w-3 -mt-1 ${
                          sortColumn === column.key && sortDirection === 'desc'
                            ? 'text-blue-600 dark:text-blue-400'
                            : 'text-gray-400 dark:text-slate-500'
                        }`}
                      />
                    </span>
                  )}
                </div>
              </th>
            ))}
          </tr>
        </thead>
        <tbody className="bg-white dark:bg-slate-900 divide-y divide-gray-200 dark:divide-slate-700">
          {data.map((row, rowIndex) => (
            <tr
              key={row.id || rowIndex}
              className={`
                hover:bg-gray-50 dark:hover:bg-slate-800 transition-colors
                ${onRowClick ? 'cursor-pointer' : ''}
                ${rowClassName ? rowClassName(row, rowIndex) : ''}
              `}
              onClick={() => onRowClick && onRowClick(row, rowIndex)}
            >
              {columns.map((column, colIndex) => (
                <td
                  key={column.key || colIndex}
                  className={`
                    px-3 sm:px-4 md:px-6 py-3 sm:py-4 text-xs sm:text-sm
                    ${column.mobileHidden ? 'hidden sm:table-cell' : ''}
                    ${column.desktopOnly ? 'hidden md:table-cell' : ''}
                    ${!column.mobileHidden && !column.desktopOnly ? 'whitespace-nowrap' : ''}
                    ${column.align === 'right' ? 'text-right' : column.align === 'center' ? 'text-center' : 'text-left'}
                    ${column.cellClassName ? column.cellClassName(row, rowIndex) : ''}
                  `}
                >
                  {column.render
                    ? column.render(row[column.key], row, rowIndex)
                    : row[column.key]}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
};

export default Table;
