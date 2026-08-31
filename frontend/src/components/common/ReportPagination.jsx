import React from 'react';
import Button from './Button';

const PAGE_SIZE_OPTIONS = [10, 25, 50, 100];

/**
 * Shared pagination footer for report tables.
 */
const ReportPagination = ({
  page = 1,
  pageSize = 25,
  total = 0,
  onPageChange,
  onPageSizeChange,
  loading = false,
  pageSizeOptions = PAGE_SIZE_OPTIONS,
}) => {
  const totalPages = Math.max(1, Math.ceil(total / pageSize) || 1);
  const safePage = Math.min(Math.max(1, page), totalPages);
  const start = total === 0 ? 0 : (safePage - 1) * pageSize + 1;
  const end = Math.min(safePage * pageSize, total);

  return (
    <div className="flex flex-wrap items-center justify-between gap-3 border-t border-gray-200 dark:border-slate-700 px-1 py-3 mt-2">
      <div className="flex flex-wrap items-center gap-3 text-sm text-gray-600 dark:text-slate-400">
        <span>
          {total === 0
            ? 'No records'
            : `Showing ${start}–${end} of ${total.toLocaleString()}`}
        </span>
        {onPageSizeChange ? (
          <label className="inline-flex items-center gap-2">
            <span className="text-gray-500 dark:text-slate-400">Rows</span>
            <select
              value={pageSize}
              onChange={(e) => onPageSizeChange(Number(e.target.value))}
              disabled={loading}
              className="rounded-lg border border-gray-300 dark:border-slate-600 px-2 py-1 text-sm bg-white dark:bg-slate-900"
            >
              {pageSizeOptions.map((size) => (
                <option key={size} value={size}>
                  {size}
                </option>
              ))}
            </select>
          </label>
        ) : null}
      </div>
      <div className="flex items-center gap-2">
        <span className="text-sm text-gray-500 dark:text-slate-400">
          Page {safePage} of {totalPages}
        </span>
        <Button
          size="sm"
          variant="outline"
          disabled={safePage <= 1 || loading}
          onClick={() => onPageChange?.(safePage - 1)}
        >
          Previous
        </Button>
        <Button
          size="sm"
          variant="outline"
          disabled={safePage >= totalPages || loading}
          onClick={() => onPageChange?.(safePage + 1)}
        >
          Next
        </Button>
      </div>
    </div>
  );
};

export default ReportPagination;
