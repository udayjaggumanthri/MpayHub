import React, { useCallback, useEffect, useState } from 'react';
import { useAuth } from '../../../context/AuthContext';
import { isAdminUser } from '../../../utils/rolePermissions';
import Card from '../../../components/common/Card';
import Button from '../../../components/common/Button';
import ReportDateRange from '../../../components/common/ReportDateRange';
import ReportPagination from '../../../components/common/ReportPagination';
import {
  CollapsibleReportFilters,
  ReportFilterField,
  ReportFilterGrid,
  FILTER_INPUT_CLASS,
  FILTER_SELECT_CLASS,
} from '../../../components/common/ReportFilterPanel';
import { countActiveReportFilters } from '../../../utils/reportFilters';
import cmsAPI from '../services/cmsApi';
import CmsReceiptView from '../receipts/CmsReceiptView';
import { cmsStatusTone, formatCmsAmount, formatCmsDateTime } from '../utils/cmsUserCopy';

const EMPTY = { status: '', search: '', date_from: '', date_to: '', days: 30 };

const StatusChip = ({ status }) => {
  const tone = cmsStatusTone(status);
  const cls =
    tone === 'success'
      ? 'bg-emerald-100 text-emerald-800 dark:bg-emerald-900/40 dark:text-emerald-200'
      : tone === 'danger'
        ? 'bg-red-100 text-red-800 dark:bg-red-900/40 dark:text-red-200'
        : tone === 'pending'
          ? 'bg-amber-100 text-amber-900 dark:bg-amber-900/40 dark:text-amber-200'
          : 'bg-slate-100 text-slate-700 dark:bg-slate-800 dark:text-slate-300';
  return (
    <span className={`inline-flex rounded-full px-2 py-0.5 text-[11px] font-bold uppercase ${cls}`}>
      {status || '—'}
    </span>
  );
};

const Metric = ({ label, value }) => (
  <div className="rounded-xl border border-slate-200 bg-white px-3 py-2.5 shadow-sm dark:border-slate-700 dark:bg-slate-900">
    <p className="text-[10px] font-semibold uppercase tracking-wide text-slate-500">{label}</p>
    <p className="mt-0.5 text-lg font-bold tabular-nums sm:text-xl">{value}</p>
  </div>
);

const CmsReports = () => {
  const { user } = useAuth();
  const isAdmin = isAdminUser(user);
  const [summary, setSummary] = useState(null);
  const [rows, setRows] = useState([]);
  const [total, setTotal] = useState(0);
  const [detail, setDetail] = useState(null);
  const [loading, setLoading] = useState(false);
  const [exportBusy, setExportBusy] = useState(false);
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(25);
  const [filters, setFilters] = useState(EMPTY);
  const [applied, setApplied] = useState(EMPTY);

  const scopeParams = isAdmin ? { scope: 'all' } : {};

  const load = useCallback(async () => {
    setLoading(true);
    const end = new Date();
    const start = new Date();
    start.setDate(end.getDate() - (applied.days || 30));
    const iso = (d) => d.toISOString().slice(0, 10);
    const dateParams =
      applied.date_from || applied.date_to
        ? { date_from: applied.date_from || undefined, date_to: applied.date_to || undefined }
        : { date_from: iso(start), date_to: iso(end) };
    const shared = {
      ...scopeParams,
      status: applied.status || undefined,
      ...dateParams,
      days: applied.days,
    };
    const [sum, tx] = await Promise.all([
      cmsAPI.reportsSummary(shared),
      cmsAPI.transactions({
        ...scopeParams,
        status: applied.status || undefined,
        search: applied.search || undefined,
        ...dateParams,
        limit: pageSize,
        offset: (page - 1) * pageSize,
      }),
    ]);
    if (sum.success) setSummary(sum.data);
    if (tx.success) {
      setRows(tx.data?.results || []);
      setTotal(tx.data?.total || 0);
    }
    setLoading(false);
  }, [applied, page, pageSize, isAdmin]);

  useEffect(() => {
    load();
  }, [load]);

  const exportCsv = async () => {
    setExportBusy(true);
    const end = new Date();
    const start = new Date();
    start.setDate(end.getDate() - (applied.days || 30));
    const iso = (d) => d.toISOString().slice(0, 10);
    const res = await cmsAPI.exportCsv({
      ...scopeParams,
      status: applied.status || undefined,
      search: applied.search || undefined,
      date_from: applied.date_from || iso(start),
      date_to: applied.date_to || iso(end),
      limit: 5000,
    });
    if (res.success && res.data) {
      const url = URL.createObjectURL(res.data);
      const a = document.createElement('a');
      a.href = url;
      a.download = `cms-reports-${Date.now()}.csv`;
      a.click();
      URL.revokeObjectURL(url);
    }
    setExportBusy(false);
  };

  return (
    <div className="mx-auto w-full max-w-7xl space-y-4">
      <header className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <h2 className="text-xl font-bold text-slate-900 dark:text-slate-100">CMS reports</h2>
          <p className="text-sm text-slate-500">
            Cash collection ledger with filters, summary, CSV, and receipts
            {isAdmin ? ' · all users' : ''}.
          </p>
        </div>
        <Button size="sm" variant="secondary" loading={exportBusy} onClick={exportCsv}>
          Export CSV
        </Button>
      </header>

      <CollapsibleReportFilters
        activeCount={countActiveReportFilters({
          status: applied.status,
          search: applied.search,
          date_from: applied.date_from,
          date_to: applied.date_to,
        })}
        defaultOpen={false}
        onApply={() => {
          setPage(1);
          setApplied({ ...filters });
        }}
        onClear={() => {
          setFilters(EMPTY);
          setApplied(EMPTY);
          setPage(1);
        }}
      >
        <ReportFilterGrid>
          <ReportFilterField label="Period">
            <select
              className={FILTER_SELECT_CLASS}
              value={filters.days}
              onChange={(e) =>
                setFilters({ ...filters, days: Number(e.target.value), date_from: '', date_to: '' })
              }
            >
              {[7, 30, 90].map((d) => (
                <option key={d} value={d}>
                  Last {d} days
                </option>
              ))}
            </select>
          </ReportFilterField>
          <ReportFilterField label="Status">
            <select
              className={FILTER_SELECT_CLASS}
              value={filters.status}
              onChange={(e) => setFilters({ ...filters, status: e.target.value })}
            >
              <option value="">All statuses</option>
              {['success', 'failed', 'initiated', 'expired'].map((s) => (
                <option key={s} value={s}>
                  {s}
                </option>
              ))}
            </select>
          </ReportFilterField>
          <ReportFilterField label="Search" span={2}>
            <input
              className={FILTER_INPUT_CLASS}
              value={filters.search}
              onChange={(e) => setFilters({ ...filters, search: e.target.value })}
              placeholder="FP txn / our txn / BC login"
            />
          </ReportFilterField>
          <ReportFilterField label="Custom dates" span={2}>
            <ReportDateRange
              idPrefix="cms-reports"
              dateFrom={filters.date_from}
              dateTo={filters.date_to}
              compact
              onChange={({ dateFrom, dateTo }) =>
                setFilters({ ...filters, date_from: dateFrom || '', date_to: dateTo || '' })
              }
            />
          </ReportFilterField>
        </ReportFilterGrid>
      </CollapsibleReportFilters>

      <div className="grid grid-cols-2 gap-2 sm:grid-cols-3 lg:grid-cols-5">
        <Metric label="Total" value={summary?.total ?? '—'} />
        <Metric label="Success" value={summary?.success ?? '—'} />
        <Metric label="Failed" value={summary?.failed ?? '—'} />
        <Metric label="Initiated" value={summary?.initiated ?? '—'} />
        <Metric label="Volume" value={summary?.volume != null ? `₹${summary.volume}` : '—'} />
      </div>

      <Card title="Transactions" shadow="sm" className="overflow-hidden" subtitle="Network txn · amount · status · when · actions">
        <div className="hidden overflow-x-auto md:block">
          <table className="min-w-full text-left text-sm">
            <thead className="bg-slate-50 text-xs uppercase text-slate-500 dark:bg-slate-800/50">
              <tr>
                <th className="px-3 py-2.5">Network txn</th>
                <th className="px-3 py-2.5">Amount</th>
                <th className="px-3 py-2.5">Status</th>
                <th className="px-3 py-2.5">When</th>
                <th className="px-3 py-2.5 text-right">Actions</th>
              </tr>
            </thead>
            <tbody>
              {loading ? (
                <tr>
                  <td colSpan={5} className="px-3 py-8 text-center text-slate-500">
                    Loading…
                  </td>
                </tr>
              ) : rows.length === 0 ? (
                <tr>
                  <td colSpan={5} className="px-3 py-8 text-center text-slate-500">
                    No transactions in this window.
                  </td>
                </tr>
              ) : (
                rows.map((r) => (
                  <tr key={r.merchant_transaction_id} className="border-t border-slate-100 dark:border-slate-800">
                    <td className="px-3 py-2.5 font-mono text-xs">{r.fp_transaction_id || '—'}</td>
                    <td className="px-3 py-2.5 tabular-nums font-medium">{formatCmsAmount(r.amount)}</td>
                    <td className="px-3 py-2.5">
                      <StatusChip status={r.status} />
                    </td>
                    <td className="px-3 py-2.5 whitespace-nowrap">{formatCmsDateTime(r.created_at)}</td>
                    <td className="px-3 py-2.5 text-right">
                      <Button size="sm" variant="secondary" onClick={() => setDetail(r)}>
                        Receipt
                      </Button>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>

        <div className="space-y-3 md:hidden">
          {rows.map((r) => (
            <div key={r.merchant_transaction_id} className="rounded-xl border border-slate-200 p-3 dark:border-slate-700">
              <div className="flex justify-between gap-2">
                <p className="font-mono text-xs break-all">{r.fp_transaction_id || '—'}</p>
                <StatusChip status={r.status} />
              </div>
              <p className="mt-1 font-semibold tabular-nums">{formatCmsAmount(r.amount)}</p>
              <p className="text-xs text-slate-500">{formatCmsDateTime(r.created_at)}</p>
              <Button size="sm" variant="secondary" className="mt-2" onClick={() => setDetail(r)}>
                Receipt
              </Button>
            </div>
          ))}
        </div>

        <div className="mt-3 border-t border-slate-100 pt-3 dark:border-slate-800">
          <ReportPagination
            page={page}
            pageSize={pageSize}
            total={total}
            loading={loading}
            onPageChange={setPage}
            onPageSizeChange={(size) => {
              setPageSize(size);
              setPage(1);
            }}
          />
        </div>
      </Card>

      {detail ? (
        <div className="fixed inset-0 z-50 flex items-end justify-center bg-black/45 p-3 sm:items-center sm:p-6">
          <div className="max-h-[92vh] w-full max-w-2xl overflow-y-auto rounded-2xl bg-white p-4 shadow-2xl dark:bg-slate-900">
            <CmsReceiptView txn={detail} onClose={() => setDetail(null)} />
          </div>
        </div>
      ) : null}
    </div>
  );
};

export default CmsReports;
