import React, { useCallback, useEffect, useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { adminAPI } from '../../services/api';
import Card from '../common/Card';
import Input from '../common/Input';
import Button from '../common/Button';
import Badge from '../common/Badge';
import LoadingSpinner from '../common/LoadingSpinner';
import ReportDateRange from '../common/ReportDateRange';
import GatewayFlowStepper from './GatewayFlowStepper';
import {
  CollapsibleReportFilters,
  FILTER_INPUT_CLASS,
  FILTER_SELECT_CLASS,
  ReportFilterDateRow,
  ReportFilterField,
  ReportFilterGrid,
} from '../common/ReportFilterPanel';
import { countActiveReportFilters } from '../../utils/reportFilters';
import { formatCurrency } from '../../utils/formatters';
import { downloadFromUrl } from '../../utils/downloadFile';
import { payinQrReceiptApiUrl } from '../../utils/mediaUrl';
import AuthenticatedImage from '../common/AuthenticatedImage';
import { FaCheck, FaXmark, FaDownload, FaQrcode, FaArrowRight, FaFileExcel } from 'react-icons/fa6';

const REJECT_REASONS = [
  { value: 'duplicate_utr', label: 'Duplicate UTR' },
  { value: 'amount_mismatch', label: 'Amount mismatch' },
  { value: 'invalid_screenshot', label: 'Invalid or unclear screenshot' },
  { value: 'payment_not_found', label: 'Payment not found in bank' },
  { value: 'other', label: 'Other' },
];

const emptyFilters = (status = 'PENDING_REVIEW') => ({
  status,
  q: '',
  utr: '',
  date_from: '',
  date_to: '',
});

function formatWhen(iso) {
  if (!iso) return '—';
  try {
    return new Date(iso).toLocaleString('en-IN');
  } catch {
    return iso;
  }
}

const PayInQrOperations = () => {
  const [searchParams] = useSearchParams();
  const initialStatus = searchParams.get('status') || 'PENDING_REVIEW';

  const [filters, setFilters] = useState(() => emptyFilters(initialStatus));
  const [applied, setApplied] = useState(() => emptyFilters(initialStatus));
  const [rows, setRows] = useState([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(false);
  const [loadError, setLoadError] = useState('');
  const [stats, setStats] = useState(null);
  const [detail, setDetail] = useState(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [approveAmount, setApproveAmount] = useState('');
  const [internalNote, setInternalNote] = useState('');
  const [rejectCode, setRejectCode] = useState('amount_mismatch');
  const [rejectText, setRejectText] = useState('');
  const [releaseNote, setReleaseNote] = useState('');
  const [showReleaseUtr, setShowReleaseUtr] = useState(false);
  const [actionType, setActionType] = useState(null);
  const [showFilters, setShowFilters] = useState(false);
  const [downloadError, setDownloadError] = useState('');

  const actionBusy = actionType !== null;

  const loadStats = useCallback(async () => {
    const res = await adminAPI.getQrOperationsStats();
    if (res.success) setStats(res.data);
  }, []);

  const loadRows = useCallback(async () => {
    setLoading(true);
    setLoadError('');
    const params = { page, page_size: 25 };
    if (applied.status) params.status = applied.status;
    if (applied.q.trim()) params.q = applied.q.trim();
    if (applied.utr.trim()) params.utr = applied.utr.trim();
    if (applied.date_from) params.date_from = applied.date_from;
    if (applied.date_to) params.date_to = applied.date_to;
    const res = await adminAPI.listQrOperations(params);
    setLoading(false);
    if (res.success) {
      setRows(res.data?.results || []);
      setTotal(res.data?.total || 0);
    } else {
      setRows([]);
      setTotal(0);
      setLoadError(res.message || 'Could not load QR operations. Ensure backend migration 0014 is applied.');
    }
  }, [page, applied]);

  useEffect(() => {
    loadStats();
  }, [loadStats]);

  useEffect(() => {
    loadRows();
  }, [loadRows]);

  const buildExportParams = () => {
    const params = {};
    if (applied.status) params.status = applied.status;
    if (applied.q.trim()) params.q = applied.q.trim();
    if (applied.utr.trim()) params.utr = applied.utr.trim();
    if (applied.date_from) params.date_from = applied.date_from;
    if (applied.date_to) params.date_to = applied.date_to;
    return params;
  };

  const downloadBlob = (res, filename) => {
    if (res?.data) {
      const url = window.URL.createObjectURL(new Blob([res.data]));
      const a = document.createElement('a');
      a.href = url;
      a.download = filename;
      a.click();
      window.URL.revokeObjectURL(url);
    }
  };

  const exportCsv = async () => {
    const res = await adminAPI.exportQrOperationsCsv(buildExportParams());
    downloadBlob(res, 'qr-operations.csv');
  };

  const exportXlsx = async () => {
    const res = await adminAPI.exportQrOperationsXlsx(buildExportParams());
    downloadBlob(res, 'qr-operations.xlsx');
  };

  const handleDownloadReceipt = async () => {
    if (!detail?.transaction_id) return;
    setDownloadError('');
    const filename = `receipt-${detail.transaction_id}.jpg`;
    try {
      await downloadFromUrl(payinQrReceiptApiUrl(detail.transaction_id, { download: true }), filename);
    } catch {
      setDownloadError('Could not download receipt. Please try again.');
    }
  };

  const openDetail = async (id) => {
    setDownloadError('');
    setDetailLoading(true);
    setDetail({ id });
    setShowReleaseUtr(false);
    setReleaseNote('');
    const res = await adminAPI.getQrOperationDetail(id);
    setDetailLoading(false);
    if (res.success) {
      setDetail(res.data);
      const sub = res.data?.submitted_amount ?? res.data?.amount;
      setApproveAmount(sub != null ? String(sub) : '');
      setInternalNote('');
      setRejectText('');
    } else {
      alert(res.message || 'Could not load detail');
      setDetail(null);
    }
  };

  const handleApprove = async () => {
    if (!detail?.id || actionBusy) return;
    setActionType('approve');
    const res = await adminAPI.approveQrOperation(detail.id, {
      approvedAmount: approveAmount,
      internalNote,
    });
    setActionType(null);
    if (!res.success) {
      alert(res.message || 'Approve failed');
      return;
    }
    setDetail(null);
    loadRows();
    loadStats();
  };

  const handleReject = async () => {
    if (!detail?.id || actionBusy) return;
    setActionType('reject');
    const res = await adminAPI.rejectQrOperation(detail.id, {
      reasonCode: rejectCode,
      reasonText: rejectText,
      internalNote,
    });
    setActionType(null);
    if (!res.success) {
      alert(res.message || 'Reject failed');
      return;
    }
    setDetail(null);
    loadRows();
    loadStats();
  };

  const handleReleaseUtr = async () => {
    if (!detail?.id || actionBusy) return;
    if (!window.confirm('Release this UTR so the retailer can submit it again? This cannot be undone.')) {
      return;
    }
    setActionType('release_utr');
    const res = await adminAPI.releaseQrOperationUtr(detail.id, { internalNote: releaseNote });
    setActionType(null);
    if (!res.success) {
      alert(res.message || 'Could not release UTR');
      return;
    }
    setDetail(null);
    loadRows();
    loadStats();
  };

  const totalPages = Math.max(1, Math.ceil(total / 25));

  return (
    <div className="min-h-[calc(100vh-6rem)] bg-gradient-to-b from-slate-50 dark:from-slate-900 via-white dark:via-slate-900 to-slate-50/80 dark:to-slate-900/80">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-8">
        <GatewayFlowStepper
          currentStep="qr-operations"
          subtitle="Review pending QR submissions, approve with amount edits, or reject with a reason."
        />

        <header className="relative overflow-hidden rounded-2xl border border-slate-200/80 dark:border-slate-700/80 bg-white dark:bg-slate-900 shadow-sm">
          <div className="absolute inset-0 bg-gradient-to-br from-amber-500/[0.06] via-transparent to-emerald-500/[0.06] pointer-events-none" />
          <div className="relative px-6 py-8 sm:px-8 sm:py-9 flex flex-col lg:flex-row lg:items-center lg:justify-between gap-6">
            <div>
              <p className="text-xs font-semibold uppercase tracking-widest text-amber-700 dark:text-amber-300 mb-2">
                Admin · Manual QR pay-in
              </p>
              <h1 className="text-2xl sm:text-3xl font-bold text-slate-900 dark:text-slate-100 tracking-tight flex items-center gap-2">
                <FaQrcode className="text-emerald-600 dark:text-emerald-400" />
                QR pay-in operations
              </h1>
              <p className="mt-2 text-sm sm:text-base text-slate-600 dark:text-slate-400 max-w-xl leading-relaxed">
                Approve or reject retailer UTR submissions. Approved pay-ins credit wallets via the same settlement path as Razorpay.
              </p>
            </div>
            <Link
              to="/admin/pay-in-qr-accounts"
              className="inline-flex items-center gap-2 self-start rounded-xl border border-emerald-200 dark:border-emerald-800 bg-emerald-50/50 dark:bg-emerald-950/40 px-4 py-3 text-sm font-semibold text-emerald-800 dark:text-emerald-300 shadow-sm hover:border-emerald-300 dark:hover:border-emerald-700 transition-colors"
            >
              QR collection accounts
              <FaArrowRight size={14} />
            </Link>
          </div>
        </header>

        {stats && (
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
            <Card padding="md" className="bg-amber-50 dark:bg-amber-950/40 border-amber-200 dark:border-amber-800">
              <p className="text-xs text-gray-600 dark:text-slate-400">Pending review</p>
              <p className="text-2xl font-bold text-amber-700 dark:text-amber-300">{stats.pending_count ?? 0}</p>
            </Card>
            <Card padding="md" className="bg-green-50 dark:bg-green-950/40 border-green-200 dark:border-green-800">
              <p className="text-xs text-gray-600 dark:text-slate-400">Approved today</p>
              <p className="text-2xl font-bold text-green-700 dark:text-green-300">{stats.approved_today ?? 0}</p>
            </Card>
            <Card padding="md" className="bg-red-50 dark:bg-red-950/40 border-red-200 dark:border-red-800">
              <p className="text-xs text-gray-600 dark:text-slate-400">Rejected today</p>
              <p className="text-2xl font-bold text-red-700 dark:text-red-300">{stats.rejected_today ?? 0}</p>
            </Card>
            <Card padding="md">
              <p className="text-xs text-gray-600 dark:text-slate-400">Volume approved today</p>
              <p className="text-2xl font-bold text-gray-900 dark:text-slate-100">{formatCurrency(parseFloat(stats.volume_today || 0))}</p>
            </Card>
          </div>
        )}

        <section className="rounded-2xl border border-slate-200/90 dark:border-slate-700/90 bg-white dark:bg-slate-900 shadow-sm overflow-hidden">
          <div className="px-5 py-4 sm:px-6 border-b border-slate-100 dark:border-slate-800 bg-slate-50/80 dark:bg-slate-800/50">
            <h2 className="text-lg font-bold text-slate-900 dark:text-slate-100">Submission queue</h2>
            <p className="text-sm text-slate-600 dark:text-slate-400 mt-0.5">Default filter: pending review</p>
          </div>

          <div className="px-5 py-3 sm:px-6 border-b border-slate-100 dark:border-slate-800">
            <CollapsibleReportFilters
              open={showFilters}
              onOpenChange={setShowFilters}
              activeCount={countActiveReportFilters(applied, {
                statusKey: 'status',
                ignoreStatus: ['ALL', 'all', ''],
              })}
              applying={loading}
              onApply={() => {
                setPage(1);
                setApplied({ ...filters });
              }}
              onClear={() => {
                const cleared = emptyFilters();
                setFilters(cleared);
                setPage(1);
                setApplied(cleared);
              }}
              actions={
                <>
                  <Button onClick={exportCsv} variant="outline" icon={FaDownload} size="sm">
                    Export CSV
                  </Button>
                  <Button onClick={exportXlsx} variant="outline" icon={FaFileExcel} size="sm">
                    Export Excel
                  </Button>
                </>
              }
            >
              <ReportFilterGrid>
                <ReportFilterField label="Status" htmlFor="qr-ops-status">
                  <select
                    id="qr-ops-status"
                    value={filters.status}
                    onChange={(e) => setFilters({ ...filters, status: e.target.value })}
                    className={FILTER_SELECT_CLASS}
                  >
                    <option value="">All</option>
                    <option value="PENDING_REVIEW">Pending review</option>
                    <option value="SUCCESS">Approved</option>
                    <option value="FAILED">Rejected</option>
                  </select>
                </ReportFilterField>
                <ReportFilterField label="Search" htmlFor="qr-ops-search" span={2}>
                  <input
                    id="qr-ops-search"
                    type="text"
                    value={filters.q}
                    onChange={(e) => setFilters({ ...filters, q: e.target.value })}
                    placeholder="Txn, user, phone…"
                    className={FILTER_INPUT_CLASS}
                  />
                </ReportFilterField>
                <ReportFilterField label="UTR" htmlFor="qr-ops-utr">
                  <input
                    id="qr-ops-utr"
                    type="text"
                    value={filters.utr}
                    onChange={(e) => setFilters({ ...filters, utr: e.target.value })}
                    placeholder="UTR number"
                    className={FILTER_INPUT_CLASS}
                  />
                </ReportFilterField>
              </ReportFilterGrid>
              <ReportFilterDateRow>
                <ReportDateRange
                  idPrefix="qr-ops"
                  dateFrom={filters.date_from}
                  dateTo={filters.date_to}
                  fromLabel="From date"
                  toLabel="To date"
                  compact
                  onChange={({ dateFrom, dateTo }) =>
                    setFilters({ ...filters, date_from: dateFrom, date_to: dateTo })
                  }
                />
              </ReportFilterDateRow>
            </CollapsibleReportFilters>
          </div>

          {loadError ? (
            <div className="mx-6 my-6 rounded-lg border border-red-200 dark:border-red-800 bg-red-50 dark:bg-red-950/40 px-4 py-3 text-sm text-red-800 dark:text-red-300">
              {loadError}
            </div>
          ) : null}

          {loading ? (
            <div className="py-16">
              <LoadingSpinner text="Loading operations…" />
            </div>
          ) : rows.length === 0 ? (
            <div className="px-6 py-16 text-center text-gray-500 dark:text-slate-400">
              <FaQrcode className="mx-auto text-slate-300 mb-3" size={40} />
              <p className="font-medium text-slate-700 dark:text-slate-300">No QR submissions match your filters</p>
              <p className="text-sm mt-1">Submissions appear here after retailers use Load Money → QR payment method.</p>
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full min-w-[960px] text-sm">
                <thead>
                  <tr className="border-b bg-gray-50 dark:bg-slate-800/50 text-left text-xs uppercase text-gray-600 dark:text-slate-400">
                    <th className="px-5 py-3">Txn ID</th>
                    <th className="px-3 py-3">User</th>
                    <th className="px-3 py-3">QR account</th>
                    <th className="px-3 py-3">UTR</th>
                    <th className="px-3 py-3">Submitted</th>
                    <th className="px-3 py-3">Status</th>
                    <th className="px-3 py-3">Date</th>
                    <th className="px-3 py-3" />
                  </tr>
                </thead>
                <tbody>
                  {rows.map((row) => (
                    <tr key={row.id} className="border-b hover:bg-gray-50 dark:hover:bg-slate-800">
                      <td className="px-5 py-3 font-mono text-xs">{row.transaction_id}</td>
                      <td className="px-3 py-3">
                        <div>{row.user_name || '—'}</div>
                        <div className="text-xs text-gray-500 dark:text-slate-400">{row.user_code}</div>
                      </td>
                      <td className="px-3 py-3">{row.qr_account_name || '—'}</td>
                      <td className="px-3 py-3 font-mono text-xs">{row.utr || '—'}</td>
                      <td className="px-3 py-3">{formatCurrency(parseFloat(row.submitted_amount || 0))}</td>
                      <td className="px-3 py-3">
                        <Badge variant={row.status === 'SUCCESS' ? 'success' : row.status === 'FAILED' ? 'error' : 'warning'}>
                          {row.status}
                        </Badge>
                      </td>
                      <td className="px-3 py-3 text-xs">{formatWhen(row.created_at)}</td>
                      <td className="px-3 py-3">
                        <Button size="sm" variant="outline" onClick={() => openDetail(row.id)}>
                          Review
                        </Button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          {totalPages > 1 && (
            <div className="flex justify-center gap-2 py-4 border-t border-slate-100 dark:border-slate-800">
              <Button disabled={page <= 1} onClick={() => setPage((p) => p - 1)} variant="outline" size="sm">
                Prev
              </Button>
              <span className="text-sm self-center">Page {page} / {totalPages}</span>
              <Button disabled={page >= totalPages} onClick={() => setPage((p) => p + 1)} variant="outline" size="sm">
                Next
              </Button>
            </div>
          )}
        </section>
      </div>

      {detail && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4">
          <Card className="w-full max-w-2xl max-h-[90vh] overflow-y-auto" padding="lg">
            <div className="flex justify-between mb-4">
              <h2 className="text-xl font-bold">Review submission</h2>
              <button type="button" onClick={() => setDetail(null)} className="text-gray-400 dark:text-slate-500 hover:text-gray-600 dark:hover:text-slate-400" disabled={actionBusy}>
                <FaXmark size={22} />
              </button>
            </div>
            {detailLoading ? (
              <LoadingSpinner text="Loading detail…" />
            ) : (
              <div className="space-y-5">
                <div className="grid grid-cols-2 gap-3 text-sm">
                  <div><span className="text-gray-500 dark:text-slate-400">Txn:</span> {detail.transaction_id}</div>
                  <div><span className="text-gray-500 dark:text-slate-400">User:</span> {detail.user_name} ({detail.user_code})</div>
                  <div><span className="text-gray-500 dark:text-slate-400">UTR:</span> {detail.utr || '—'}</div>
                  <div><span className="text-gray-500 dark:text-slate-400">Submitted:</span> {formatCurrency(parseFloat(detail.submitted_amount || 0))}</div>
                  <div><span className="text-gray-500 dark:text-slate-400">Payment date:</span> {detail.payment_date || '—'}</div>
                  <div><span className="text-gray-500 dark:text-slate-400">Status:</span> {detail.status}</div>
                </div>
                {(detail.receipt_url || detail.transaction_id) ? (
                  <div className="space-y-3">
                    <AuthenticatedImage
                      src={detail.receipt_url || payinQrReceiptApiUrl(detail.transaction_id)}
                      alt="Receipt"
                      className="max-h-64 rounded border mx-auto object-contain bg-white"
                    />
                    <div className="flex flex-col items-center gap-2">
                      <Button
                        type="button"
                        variant="secondary"
                        size="sm"
                        icon={FaDownload}
                        onClick={handleDownloadReceipt}
                        disabled={actionBusy}
                      >
                        Download receipt
                      </Button>
                      {downloadError ? (
                        <p className="text-xs text-red-600 dark:text-red-400">{downloadError}</p>
                      ) : null}
                    </div>
                  </div>
                ) : null}

                {detail.status === 'PENDING_REVIEW' && (
                  <>
                    <div className="rounded-lg border border-emerald-200 dark:border-emerald-800 bg-emerald-50/50 dark:bg-emerald-950/40 p-4 space-y-3">
                      <h3 className="text-sm font-semibold text-emerald-900 dark:text-emerald-300">Approve & credit wallet</h3>
                      <Input
                        label="Approved amount (INR)"
                        type="number"
                        value={approveAmount}
                        onChange={(e) => setApproveAmount(e.target.value)}
                        disabled={actionBusy}
                      />
                      <Input
                        label="Internal note (optional)"
                        value={internalNote}
                        onChange={(e) => setInternalNote(e.target.value)}
                        disabled={actionBusy}
                      />
                      <Button
                        onClick={handleApprove}
                        loading={actionType === 'approve'}
                        disabled={actionBusy && actionType !== 'approve'}
                        variant="primary"
                        icon={FaCheck}
                        fullWidth
                      >
                        Approve & credit wallet
                      </Button>
                    </div>

                    <div className="rounded-lg border border-red-200 dark:border-red-800 bg-red-50/30 dark:bg-red-950/40 p-4 space-y-3">
                      <h3 className="text-sm font-semibold text-red-900 dark:text-red-300">Reject submission</h3>
                      <div>
                        <label className="block text-sm font-medium mb-1">Reject reason</label>
                        <select
                          value={rejectCode}
                          onChange={(e) => setRejectCode(e.target.value)}
                          className="w-full border rounded-lg px-3 py-2 mb-2"
                          disabled={actionBusy}
                        >
                          {REJECT_REASONS.map((r) => (
                            <option key={r.value} value={r.value}>{r.label}</option>
                          ))}
                        </select>
                        <Input
                          value={rejectText}
                          onChange={(e) => setRejectText(e.target.value)}
                          placeholder="Message to user (optional)"
                          disabled={actionBusy}
                        />
                      </div>
                      <Button
                        onClick={handleReject}
                        loading={actionType === 'reject'}
                        disabled={actionBusy && actionType !== 'reject'}
                        variant="outline"
                        icon={FaXmark}
                        fullWidth
                        className="text-red-700 dark:text-red-300 border-red-300 dark:border-red-800 hover:bg-red-50 dark:hover:bg-red-950/60"
                      >
                        Reject
                      </Button>
                    </div>
                  </>
                )}

                {detail.status === 'FAILED' && detail.utr ? (
                  <div className="rounded-lg border border-slate-200 dark:border-slate-700 bg-slate-50 dark:bg-slate-800/50 p-4 space-y-3">
                    <button
                      type="button"
                      className="text-sm font-semibold text-slate-700 dark:text-slate-300 hover:text-slate-900 dark:hover:text-slate-100"
                      onClick={() => setShowReleaseUtr((v) => !v)}
                    >
                      {showReleaseUtr ? '▼' : '▶'} Release UTR for reuse
                    </button>
                    {showReleaseUtr ? (
                      <>
                        <p className="text-xs text-slate-600 dark:text-slate-400">
                          Clears UTR <span className="font-mono font-semibold">{detail.utr}</span> so the retailer can submit again. Requires audit note.
                        </p>
                        <Input
                          label="Internal reason (min 10 characters)"
                          value={releaseNote}
                          onChange={(e) => setReleaseNote(e.target.value)}
                          disabled={actionBusy}
                        />
                        <Button
                          onClick={handleReleaseUtr}
                          loading={actionType === 'release_utr'}
                          disabled={actionBusy && actionType !== 'release_utr'}
                          variant="outline"
                          fullWidth
                        >
                          Release UTR
                        </Button>
                      </>
                    ) : null}
                  </div>
                ) : null}
              </div>
            )}
          </Card>
        </div>
      )}
    </div>
  );
};

export default PayInQrOperations;
