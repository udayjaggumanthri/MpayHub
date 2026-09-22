import React, { useCallback, useEffect, useState } from 'react';
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
};

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

const AepsHistory = () => {
  const [rows, setRows] = useState([]);
  const [total, setTotal] = useState(0);
  const [detail, setDetail] = useState(null);
  const [busy, setBusy] = useState(false);
  const [loading, setLoading] = useState(false);
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(25);
  const [filters, setFilters] = useState(EMPTY_FILTERS);
  const [applied, setApplied] = useState(EMPTY_FILTERS);

  const load = useCallback(async () => {
    setLoading(true);
    const res = await aepsAPI.transactions({
      product: applied.product || undefined,
      status: applied.status || undefined,
      search: applied.search || undefined,
      date_from: applied.date_from || undefined,
      date_to: applied.date_to || undefined,
      limit: pageSize,
      offset: (page - 1) * pageSize,
    });
    if (res.success) {
      setRows(res.data?.results || []);
      setTotal(res.data?.total || 0);
    }
    setLoading(false);
  }, [applied, page, pageSize]);

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
    setBusy(true);
    const res = await aepsAPI.exportTransactionsCsv({
      product: applied.product || undefined,
      status: applied.status || undefined,
      search: applied.search || undefined,
      date_from: applied.date_from || undefined,
      date_to: applied.date_to || undefined,
      limit: 5000,
    });
    if (res.success && res.data) {
      const url = URL.createObjectURL(res.data);
      const a = document.createElement('a');
      a.href = url;
      a.download = `aeps-history-${Date.now()}.csv`;
      a.click();
      URL.revokeObjectURL(url);
    }
    setBusy(false);
  };

  const statusCheck = async (r) => {
    setBusy(true);
    const st = await aepsAPI.statusCheck(r.merchant_tran_id, {
      otp_mode: Boolean(r.cd_otp_mode) || r.product === 'CD_OTP',
    });
    if (st.success) {
      setDetail(st.data?.transaction || st.data);
      await load();
    }
    setBusy(false);
  };

  const acknowledge = async (r) => {
    if (!aepsAckAllowed(r)) return;
    setBusy(true);
    const ack = await aepsAPI.acknowledge(r.merchant_tran_id, {
      otp_mode: Boolean(r.cd_otp_mode) || r.product === 'CD_OTP',
    });
    if (ack.success) {
      setDetail(ack.data?.transaction || ack.data);
      await load();
    }
    setBusy(false);
  };

  return (
    <div className="space-y-5">
      <header className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h2 className="text-xl font-bold text-slate-900 dark:text-slate-100">AEPS history</h2>
          <p className="text-sm text-slate-500 dark:text-slate-400">
            Your AEPS transactions with branded receipts and export.
          </p>
        </div>
        <Button size="sm" variant="secondary" loading={busy} onClick={exportCsv}>
          Export CSV
        </Button>
      </header>

      <CollapsibleReportFilters
        activeCount={countActiveReportFilters(applied)}
        defaultOpen
        onApply={applyFilters}
        onClear={resetFilters}
      >
        <ReportFilterGrid>
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
              {['success', 'failed', 'pending', 'timeout', 'initiated'].map((s) => (
                <option key={s} value={s}>
                  {s}
                </option>
              ))}
            </select>
          </ReportFilterField>
          <ReportFilterField label="Search RRN / Txn ID" span={2}>
            <input
              className={FILTER_INPUT_CLASS}
              value={filters.search}
              onChange={(e) => setFilters({ ...filters, search: e.target.value })}
              placeholder="RRN, merchant txn id, Fingpay id"
            />
          </ReportFilterField>
          <ReportFilterField label="Date range" span={2}>
            <ReportDateRange
              idPrefix="aeps-history"
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

      <Card shadow="sm" className="overflow-x-auto">
        <table className="min-w-full text-left text-sm">
          <thead className="bg-slate-50 text-xs uppercase text-slate-500 dark:bg-slate-800/50 dark:text-slate-400">
            <tr>
              <th className="px-3 py-2">When</th>
              <th className="px-3 py-2">Product</th>
              <th className="px-3 py-2">Amount</th>
              <th className="px-3 py-2">Status</th>
              <th className="px-3 py-2">RRN</th>
              <th className="px-3 py-2">Txn ID</th>
              <th className="px-3 py-2">Actions</th>
            </tr>
          </thead>
          <tbody>
            {loading ? (
              <tr>
                <td colSpan={7} className="px-3 py-6 text-center text-slate-500">
                  Loading…
                </td>
              </tr>
            ) : rows.length === 0 ? (
              <tr>
                <td colSpan={7} className="px-3 py-6 text-center text-slate-500">
                  No transactions for these filters.
                </td>
              </tr>
            ) : (
              rows.map((r) => (
                <tr key={r.merchant_tran_id} className="border-t border-slate-100 dark:border-slate-800">
                  <td className="px-3 py-2 whitespace-nowrap">{formatAepsDateTime(r.created_at)}</td>
                  <td className="px-3 py-2">{r.product_label || aepsProductLabel(r.product)}</td>
                  <td className="px-3 py-2 tabular-nums">{formatAepsAmount(r.amount)}</td>
                  <td className="px-3 py-2">
                    <StatusChip status={r.status} />
                  </td>
                  <td className="px-3 py-2 font-mono text-xs">{r.bank_rrn || '—'}</td>
                  <td className="px-3 py-2 font-mono text-xs">{r.merchant_tran_id}</td>
                  <td className="px-3 py-2">
                    <div className="flex flex-wrap gap-1">
                      <Button size="sm" variant="secondary" onClick={() => setDetail(r)}>
                        Receipt
                      </Button>
                      {aepsNeedsStatusCheck(r) ? (
                        <Button size="sm" variant="secondary" loading={busy} onClick={() => statusCheck(r)}>
                          Check
                        </Button>
                      ) : null}
                    </div>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
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
      </Card>

      {detail ? (
        <div className="fixed inset-0 z-50 flex items-end justify-center bg-black/40 p-4 sm:items-center">
          <div className="max-h-[90vh] w-full max-w-2xl overflow-y-auto rounded-2xl bg-white p-4 shadow-xl dark:bg-slate-900">
            <div className="mb-3 flex items-center justify-between gap-2">
              <h3 className="text-lg font-bold text-slate-900 dark:text-slate-100">Transaction receipt</h3>
              <Button size="sm" variant="secondary" onClick={() => setDetail(null)}>
                Close
              </Button>
            </div>
            <AepsTransactionReceiptView
              result={detail}
              busy={busy}
              onStatusCheck={statusCheck}
              onAck={aepsAckAllowed(detail) ? acknowledge : undefined}
            />
          </div>
        </div>
      ) : null}
    </div>
  );
};

export default AepsHistory;
