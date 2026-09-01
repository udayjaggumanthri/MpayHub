import React from 'react';
import { FaMagnifyingGlass } from 'react-icons/fa6';
import Button from '../../common/Button';
import LoadingSpinner from '../../common/LoadingSpinner';

const PAGE_SIZES = [25, 50, 100];

const REASON_LABELS = {
  admin_disabled: 'Admin disabled',
  cash_only_policy: 'Cash-only policy',
  no_agt_channel: 'No AGT channel',
  no_cash_mode: 'No Cash mode',
  no_payment_modes: 'No payment modes',
  inactive_status: 'Inactive status',
  stale_mdm: 'Stale MDM',
  provider_policy: 'Provider policy',
  soft_deleted: 'Soft deleted',
};

export const formatHiddenReason = (code) => REASON_LABELS[code] || code;

const BbpsAdminTable = ({
  rows,
  columns,
  loading,
  pagination,
  onPageChange,
  pageSize,
  onPageSizeChange,
  qInput,
  onSearchChange,
  searchPlaceholder = 'Search biller name or ID…',
  filters = null,
  emptyMessage = 'No billers match your filters.',
  toolbar = null,
}) => {
  const totalPages = pagination?.total_pages || 1;
  const page = pagination?.page || 1;

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center gap-2 rounded-xl border border-slate-200 bg-white px-3 py-2.5 shadow-sm dark:border-slate-700 dark:bg-slate-900">
        <div className="relative min-w-[220px] flex-1">
          <FaMagnifyingGlass className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" size={13} />
          <input
            type="text"
            value={qInput}
            onChange={(e) => onSearchChange(e.target.value)}
            placeholder={searchPlaceholder}
            className="w-full rounded-lg border border-slate-200 py-2 pl-9 pr-3 text-sm focus:border-blue-400 focus:outline-none focus:ring-2 focus:ring-blue-100 dark:border-slate-700 dark:bg-slate-950"
          />
        </div>
        {filters}
        <select
          value={pageSize}
          onChange={(e) => onPageSizeChange(Number(e.target.value))}
          className="rounded-lg border border-slate-200 px-3 py-2 text-sm dark:border-slate-700 dark:bg-slate-950"
        >
          {PAGE_SIZES.map((s) => (
            <option key={s} value={s}>
              {s} / page
            </option>
          ))}
        </select>
      </div>

      {toolbar}

      <div className="overflow-auto rounded-xl border border-slate-200 bg-white shadow-sm dark:border-slate-700 dark:bg-slate-900">
        {loading ? (
          <div className="flex justify-center py-16">
            <LoadingSpinner />
          </div>
        ) : rows.length === 0 ? (
          <p className="px-4 py-12 text-center text-sm text-slate-500 dark:text-slate-400">{emptyMessage}</p>
        ) : (
          <table className="w-full min-w-[720px] text-sm">
            <thead className="bg-slate-50 text-left text-xs font-semibold uppercase tracking-wide text-slate-500 dark:bg-slate-800/80">
              <tr>
                {columns.map((col) => (
                  <th key={col.key} className="px-3 py-2.5">
                    {col.label}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {rows.map((row) => (
                <tr key={row.id || row.biller_id} className="border-t border-slate-100 dark:border-slate-800">
                  {columns.map((col) => (
                    <td key={col.key} className="px-3 py-2.5 align-top text-slate-700 dark:text-slate-300">
                      {col.render ? col.render(row) : row[col.key]}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {pagination ? (
        <div className="flex flex-wrap items-center justify-between gap-2 text-sm text-slate-600 dark:text-slate-400">
          <span>
            Page {page} / {totalPages} · Showing {rows.length} · Total {pagination.total ?? 0}
          </span>
          <div className="flex gap-2">
            <Button size="sm" variant="outline" disabled={page <= 1} onClick={() => onPageChange(page - 1)}>
              Prev
            </Button>
            <Button size="sm" variant="outline" disabled={page >= totalPages} onClick={() => onPageChange(page + 1)}>
              Next
            </Button>
          </div>
        </div>
      ) : null}
    </div>
  );
};

export default BbpsAdminTable;
