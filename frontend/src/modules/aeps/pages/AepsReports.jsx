import React, { useCallback, useEffect, useMemo, useState } from 'react';
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
import aepsAPI from '../services/aepsApi';
import AepsTransactionReceiptView from '../receipts/AepsTransactionReceiptView';
import {
  aepsAckAllowed,
  aepsBankLabel,
  aepsNeedsStatusCheck,
  aepsProductLabel,
  aepsStatusTone,
  formatAepsAmount,
  formatAepsDateTime,
} from '../receipts/aepsReceiptFields';

const EMPTY_FILTERS = {
  product: '',
  status: '',
  search: '',
  date_from: '',
  date_to: '',
  days: 30,
};

const Metric = ({ label, value }) => (
  <div className="rounded-xl border border-slate-200 bg-white px-3 py-2.5 shadow-sm dark:border-slate-700 dark:bg-slate-900">
    <p className="text-[10px] font-semibold uppercase tracking-wide text-slate-500 dark:text-slate-400">{label}</p>
    <p className="mt-0.5 text-lg font-bold tabular-nums text-slate-900 dark:text-slate-100 sm:text-xl">{value}</p>
  </div>
);

const StatusChip = ({ status }) => {
  const tone = aepsStatusTone(status);
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

const rowKey = (r) => String(r?.merchant_tran_id || r?.id || '');

const AepsReports = () => {
  const { user } = useAuth();
  const isAdmin = isAdminUser(user);
  const [summary, setSummary] = useState(null);
  const [rows, setRows] = useState([]);
  const [total, setTotal] = useState(0);
  const [detail, setDetail] = useState(null);
  const [exportBusy, setExportBusy] = useState(false);
  const [rowBusyId, setRowBusyId] = useState(null);
  const [loading, setLoading] = useState(false);
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(25);
  const [filters, setFilters] = useState(EMPTY_FILTERS);
  const [applied, setApplied] = useState(EMPTY_FILTERS);

  const scopeParams = useMemo(() => (isAdmin ? { scope: 'all' } : {}), [isAdmin]);

  const dateParams = (f) => {
    if (f.date_from || f.date_to) {
      return {
        date_from: f.date_from || undefined,
        date_to: f.date_to || undefined,
      };
    }
    return { days: f.days || 30 };
  };

  const load = useCallback(async () => {
    setLoading(true);
    const shared = {
      ...scopeParams,
      product: applied.product || undefined,
      status: applied.status || undefined,
      ...dateParams(applied),
    };
    const [sum, tx] = await Promise.all([
      aepsAPI.reportsSummary(shared),
      aepsAPI.transactions({
        ...scopeParams,
        product: applied.product || undefined,
        status: applied.status || undefined,
        search: applied.search || undefined,
        limit: pageSize,
        offset: (page - 1) * pageSize,
        ...(applied.date_from || applied.date_to
          ? {
              date_from: applied.date_from || undefined,
              date_to: applied.date_to || undefined,
            }
          : (() => {
              const end = new Date();
              const start = new Date();
              start.setDate(end.getDate() - (applied.days || 30));
              const iso = (d) => d.toISOString().slice(0, 10);
              return { date_from: iso(start), date_to: iso(end) };
            })()),
      }),
    ]);
    if (sum.success) setSummary(sum.data);
    if (tx.success) {
      setRows(tx.data?.results || []);
      setTotal(tx.data?.total || 0);
    }
    setLoading(false);
  }, [applied, page, pageSize, scopeParams]);

  useEffect(() => {
    load();
  }, [load]);

  const applyFilters = () => {
    setPage(1);
    setApplied({ ...filters });
  };

  const resetFilters = () => {
    setFilters(EMPTY_FILTERS);
    setApplied(EMPTY_FILTERS);
    setPage(1);
  };

  const exportCsv = async () => {
    setExportBusy(true);
    const end = new Date();
    const start = new Date();
    start.setDate(end.getDate() - (applied.days || 30));
    const iso = (d) => d.toISOString().slice(0, 10);
    const res = await aepsAPI.exportTransactionsCsv({
      ...scopeParams,
      product: applied.product || undefined,
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
      a.download = `aeps-reports-${Date.now()}.csv`;
      a.click();
      URL.revokeObjectURL(url);
    }
    setExportBusy(false);
  };

  const statusCheck = async (r) => {
    const id = rowKey(r);
    setRowBusyId(id);
    const st = await aepsAPI.statusCheck(r.merchant_tran_id, {
      otp_mode: Boolean(r.cd_otp_mode) || r.product === 'CD_OTP',
    });
    if (st.success) {
      const next = st.data?.transaction || st.data;
      setDetail(next);
      setRows((prev) =>
        prev.map((row) => (rowKey(row) === id ? { ...row, ...next } : row))
      );
      // Refresh summary quietly without spinning every action button
      load();
    }
    setRowBusyId(null);
  };

  const acknowledge = async (r) => {
    if (!aepsAckAllowed(r)) return;
    const id = rowKey(r);
    setRowBusyId(id);
    const ack = await aepsAPI.acknowledge(r.merchant_tran_id, {
      otp_mode: Boolean(r.cd_otp_mode) || r.product === 'CD_OTP',
    });
    if (ack.success) {
      const next = ack.data?.transaction || ack.data;
      setDetail(next);
      setRows((prev) =>
        prev.map((row) => (rowKey(row) === id ? { ...row, ...next } : row))
      );
      load();
    }
    setRowBusyId(null);
  };

  const activeFilterCount = countActiveReportFilters({
    product: applied.product,
    status: applied.status,
    search: applied.search,
    date_from: applied.date_from,
    date_to: applied.date_to,
    days: applied.days !== 30 ? applied.days : '',
  });

  const detailBusy = detail ? rowBusyId === rowKey(detail) : false;

  const ActionButtons = ({ r, compact = false }) => {
    const id = rowKey(r);
    const isBusy = rowBusyId === id;
    const showCheck = aepsNeedsStatusCheck(r);
    const showAck = aepsAckAllowed(r);
    return (
      <div className={`flex flex-wrap gap-1.5 ${compact ? '' : 'justify-end'}`}>
        <Button size="sm" variant="secondary" onClick={() => setDetail(r)} disabled={Boolean(rowBusyId) && !isBusy}>
          Receipt
        </Button>
        {showCheck ? (
          <Button size="sm" variant="secondary" loading={isBusy} onClick={() => statusCheck(r)}>
            Check
          </Button>
        ) : null}
        {showAck ? (
          <Button size="sm" loading={isBusy} onClick={() => acknowledge(r)}>
            Ack
          </Button>
        ) : null}
      </div>
    );
  };

  return (
    <div className="mx-auto w-full max-w-7xl space-y-4 px-0 sm:space-y-5">
      <header className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
        <div className="min-w-0">
          <h2 className="text-xl font-bold text-slate-900 dark:text-slate-100">AEPS reports</h2>
          <p className="mt-0.5 text-sm text-slate-500 dark:text-slate-400">
            Ledger, receipts, status check &amp; acknowledge{isAdmin ? ' · all users' : ''}.
          </p>
        </div>
        <Button size="sm" variant="secondary" loading={exportBusy} onClick={exportCsv} className="shrink-0 self-start sm:self-auto">
          Export CSV
        </Button>
      </header>

      <CollapsibleReportFilters
        activeCount={activeFilterCount}
        defaultOpen={false}
        onApply={applyFilters}
        onClear={resetFilters}
      >
        <ReportFilterGrid>
          <ReportFilterField label="Period">
            <select
              className={FILTER_SELECT_CLASS}
              value={filters.days}
              onChange={(e) =>
                setFilters({
                  ...filters,
                  days: Number(e.target.value),
                  date_from: '',
                  date_to: '',
                })
              }
            >
              {[7, 30, 90].map((d) => (
                <option key={d} value={d}>
                  Last {d} days
                </option>
              ))}
            </select>
          </ReportFilterField>
          <ReportFilterField label="Product">
            <select
              className={FILTER_SELECT_CLASS}
              value={filters.product}
              onChange={(e) => setFilters({ ...filters, product: e.target.value })}
            >
              <option value="">All products</option>
              {['CW', 'BE', 'MS', 'AP', 'CD'].map((p) => (
                <option key={p} value={p}>
                  {aepsProductLabel(p)}
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
              {['success', 'failed', 'pending', 'timeout'].map((s) => (
                <option key={s} value={s}>
                  {s}
                </option>
              ))}
            </select>
          </ReportFilterField>
          <ReportFilterField label="Search RRN / txn id" span={2}>
            <input
              className={FILTER_INPUT_CLASS}
              value={filters.search}
              onChange={(e) => setFilters({ ...filters, search: e.target.value })}
              placeholder="RRN or merchant txn id"
            />
          </ReportFilterField>
          <ReportFilterField label="Custom dates (optional)" span={2}>
            <ReportDateRange
              idPrefix="aeps-reports"
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
        <Metric label="Pending" value={summary?.pending ?? '—'} />
        <Metric label="Volume" value={summary?.volume != null ? `₹${summary.volume}` : '—'} />
      </div>

      {summary?.by_product?.length ? (
        <div className="flex flex-wrap gap-1.5">
          {summary.by_product.map((row) => (
            <span
              key={row.product}
              className="inline-flex items-center gap-1.5 rounded-full border border-slate-200 bg-slate-50 px-2.5 py-1 text-xs dark:border-slate-700 dark:bg-slate-800/60"
            >
              <span className="font-semibold text-slate-800 dark:text-slate-100">
                {row.label || aepsProductLabel(row.product)}
              </span>
              <span className="tabular-nums text-slate-500 dark:text-slate-400">{row.count}</span>
            </span>
          ))}
        </div>
      ) : null}

      <Card
        title="Transactions"
        shadow="sm"
        className="overflow-hidden"
        subtitle="RRN · product · amount · status · when · actions"
      >
        {/* Mobile / narrow: stacked cards */}
        <div className="space-y-3 md:hidden">
          {loading ? (
            <p className="py-8 text-center text-sm text-slate-500">Loading…</p>
          ) : rows.length === 0 ? (
            <p className="py-8 text-center text-sm text-slate-500">No transactions in this window.</p>
          ) : (
            rows.map((r) => (
              <div
                key={rowKey(r)}
                className="rounded-xl border border-slate-200 bg-white p-3 dark:border-slate-700 dark:bg-slate-900"
              >
                <div className="flex items-start justify-between gap-2">
                  <div className="min-w-0">
                    <p className="font-mono text-xs font-semibold text-slate-800 dark:text-slate-100 break-all">
                      {r.bank_rrn || '—'}
                    </p>
                    <p className="mt-0.5 text-sm font-medium text-slate-700 dark:text-slate-200">
                      {r.product_label || aepsProductLabel(r.product)}
                    </p>
                  </div>
                  <StatusChip status={r.status} />
                </div>
                <div className="mt-2 grid grid-cols-2 gap-2 text-xs text-slate-600 dark:text-slate-400">
                  <div>
                    <span className="block uppercase tracking-wide text-[10px] text-slate-400">Amount</span>
                    <span className="tabular-nums text-sm font-semibold text-slate-900 dark:text-slate-100">
                      {formatAepsAmount(r.amount)}
                    </span>
                  </div>
                  <div>
                    <span className="block uppercase tracking-wide text-[10px] text-slate-400">When</span>
                    <span className="text-sm text-slate-800 dark:text-slate-200">{formatAepsDateTime(r.created_at)}</span>
                  </div>
                  {(r.bank_name || r.bank_iin) && (
                    <div className="col-span-2">
                      <span className="block uppercase tracking-wide text-[10px] text-slate-400">Bank</span>
                      <span className="text-sm text-slate-800 dark:text-slate-200">{aepsBankLabel(r)}</span>
                    </div>
                  )}
                </div>
                <div className="mt-3 border-t border-slate-100 pt-2 dark:border-slate-800">
                  <ActionButtons r={r} compact />
                </div>
              </div>
            ))
          )}
        </div>

        {/* Desktop table: RRN → Product → Amount → Status → When → Actions */}
        <div className="hidden overflow-x-auto md:block">
          <table className="min-w-full text-left text-sm">
            <thead className="bg-slate-50 text-xs uppercase tracking-wide text-slate-500 dark:bg-slate-800/50 dark:text-slate-400">
              <tr>
                <th className="whitespace-nowrap px-3 py-2.5">RRN</th>
                <th className="whitespace-nowrap px-3 py-2.5">Product</th>
                <th className="whitespace-nowrap px-3 py-2.5">Amount</th>
                <th className="whitespace-nowrap px-3 py-2.5">Status</th>
                <th className="whitespace-nowrap px-3 py-2.5">When</th>
                <th className="whitespace-nowrap px-3 py-2.5 text-right">Actions</th>
              </tr>
            </thead>
            <tbody>
              {loading ? (
                <tr>
                  <td colSpan={6} className="px-3 py-8 text-center text-slate-500">
                    Loading…
                  </td>
                </tr>
              ) : rows.length === 0 ? (
                <tr>
                  <td colSpan={6} className="px-3 py-8 text-center text-slate-500">
                    No transactions in this window.
                  </td>
                </tr>
              ) : (
                rows.map((r) => (
                  <tr
                    key={rowKey(r)}
                    className="border-t border-slate-100 align-middle dark:border-slate-800 hover:bg-slate-50/70 dark:hover:bg-slate-800/30"
                  >
                    <td className="px-3 py-2.5 font-mono text-xs font-medium text-slate-800 dark:text-slate-100">
                      {r.bank_rrn || '—'}
                    </td>
                    <td className="px-3 py-2.5">
                      <div className="font-medium text-slate-900 dark:text-slate-100">
                        {r.product_label || aepsProductLabel(r.product)}
                      </div>
                      {(r.bank_name || r.bank_iin) && (
                        <div className="mt-0.5 text-xs text-slate-500 dark:text-slate-400">{aepsBankLabel(r)}</div>
                      )}
                    </td>
                    <td className="px-3 py-2.5 tabular-nums font-medium">{formatAepsAmount(r.amount)}</td>
                    <td className="px-3 py-2.5">
                      <StatusChip status={r.status} />
                    </td>
                    <td className="px-3 py-2.5 whitespace-nowrap text-slate-600 dark:text-slate-300">
                      {formatAepsDateTime(r.created_at)}
                    </td>
                    <td className="px-3 py-2.5">
                      <ActionButtons r={r} />
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
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
          <div className="max-h-[92vh] w-full max-w-2xl overflow-y-auto rounded-2xl bg-white p-4 shadow-2xl dark:bg-slate-900 sm:p-5">
            <div className="mb-3 flex items-center justify-between gap-2">
              <h3 className="text-lg font-bold text-slate-900 dark:text-slate-100">Transaction receipt</h3>
              <Button size="sm" variant="secondary" onClick={() => setDetail(null)}>
                Close
              </Button>
            </div>
            <AepsTransactionReceiptView
              result={detail}
              busy={detailBusy}
              showActions
              onStatusCheck={statusCheck}
              onAck={acknowledge}
            />
          </div>
        </div>
      ) : null}
    </div>
  );
};

export default AepsReports;
