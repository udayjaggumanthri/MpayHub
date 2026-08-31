import React, { useEffect } from 'react';
import { FiX } from 'react-icons/fi';
import { useAuth } from '../../context/AuthContext';
import { formatCurrency, formatReportDateTime } from '../../utils/formatters';
import { isAdminUser } from '../../utils/rolePermissions';

function DetailField({ label, value }) {
  return (
    <div className="min-w-0">
      <p className="text-xs font-medium uppercase tracking-wide text-gray-500 dark:text-slate-400">{label}</p>
      <p className="mt-1 break-all text-sm font-semibold text-gray-900 dark:text-slate-100">{value ?? '—'}</p>
    </div>
  );
}

function formatPctDisplay(pctRaw) {
  if (pctRaw == null || pctRaw === '') return '—';
  const n = parseFloat(String(pctRaw));
  if (Number.isNaN(n)) return String(pctRaw);
  return `${n.toFixed(4)}%`;
}

/** Human-readable pay-in fee snapshot (replaces raw JSON for operators). */
function FeeBreakdownPanel({ snapshot }) {
  if (!snapshot || typeof snapshot !== 'object') return null;

  if (snapshot.legacy) {
    return (
      <div className="mt-2 space-y-0 rounded-lg border border-gray-200 dark:border-slate-700 bg-white dark:bg-slate-900 text-sm shadow-sm">
        <div className="flex justify-between border-b border-gray-100 dark:border-slate-800 px-3 py-2.5">
          <span className="text-gray-600 dark:text-slate-400">Gross amount</span>
          <span className="font-semibold tabular-nums text-gray-900 dark:text-slate-100">
            {formatCurrency(parseFloat(snapshot.gross) || 0)}
          </span>
        </div>
        <div className="flex justify-between border-b border-gray-100 dark:border-slate-800 px-3 py-2.5">
          <span className="text-gray-600 dark:text-slate-400">Service charge</span>
          <span className="font-semibold tabular-nums text-amber-800 dark:text-amber-300">
            {formatCurrency(parseFloat(snapshot.charge) || 0)}
          </span>
        </div>
        <div className="flex justify-between px-3 py-2.5">
          <span className="text-gray-600 dark:text-slate-400">Net credit</span>
          <span className="font-semibold tabular-nums text-emerald-800 dark:text-emerald-300">
            {formatCurrency(parseFloat(snapshot.net_credit) || 0)}
          </span>
        </div>
      </div>
    );
  }

  const lines = Array.isArray(snapshot.lines) ? snapshot.lines : [];
  const gross = parseFloat(snapshot.gross) || 0;
  const totalDed = parseFloat(snapshot.total_deduction) || 0;
  const netCredit = parseFloat(snapshot.net_credit) || 0;

  if (lines.length === 0) {
    return (
      <div className="mt-2 rounded-lg border border-gray-200 dark:border-slate-700 bg-white dark:bg-slate-900 px-3 py-3 text-sm text-gray-600 dark:text-slate-400">
        <div className="flex justify-between py-1">
          <span>Gross</span>
          <span className="font-semibold tabular-nums">{formatCurrency(gross)}</span>
        </div>
        <div className="flex justify-between py-1">
          <span>Total deductions</span>
          <span className="font-semibold tabular-nums text-amber-800 dark:text-amber-300">{formatCurrency(totalDed)}</span>
        </div>
        <div className="flex justify-between border-t border-gray-100 dark:border-slate-800 pt-2 font-semibold text-emerald-900 dark:text-emerald-300">
          <span>Net credit</span>
          <span className="tabular-nums">{formatCurrency(netCredit)}</span>
        </div>
      </div>
    );
  }

  return (
    <div className="mt-2 overflow-hidden rounded-lg border border-gray-200 dark:border-slate-700 bg-white dark:bg-slate-900 text-sm shadow-sm">
      <div className="grid grid-cols-[1fr_auto_auto] gap-x-3 gap-y-0 border-b border-gray-200 dark:border-slate-700 bg-slate-50 dark:bg-slate-800/50 px-3 py-2 text-xs font-semibold uppercase tracking-wide text-gray-600 dark:text-slate-400">
        <span>Component</span>
        <span className="text-right">Rate</span>
        <span className="text-right">Amount</span>
      </div>
      {lines.map((line, i) => (
        <div key={line.key || `line-${i}`} className="border-b border-gray-100 dark:border-slate-800 last:border-b-0">
          <div className="grid grid-cols-[1fr_auto_auto] items-start gap-x-3 px-3 py-2.5">
            <span className="font-medium leading-snug text-gray-900 dark:text-slate-100">{line.label || line.key || '—'}</span>
            <span className="text-right tabular-nums text-gray-600 dark:text-slate-400">{formatPctDisplay(line.pct)}</span>
            <span className="text-right font-semibold tabular-nums text-gray-900 dark:text-slate-100">
              {formatCurrency(parseFloat(line.amount) || 0)}
            </span>
          </div>
          {line.note ? (
            <p className="border-t border-amber-100/80 dark:border-amber-900/80 bg-amber-50/60 dark:bg-amber-950/40 px-3 py-2 text-xs leading-relaxed text-amber-950 dark:text-amber-200">
              {line.note}
            </p>
          ) : null}
        </div>
      ))}
      <div className="flex justify-between border-t border-gray-200 dark:border-slate-700 bg-gray-50 dark:bg-slate-800/50 px-3 py-2 text-xs font-semibold text-gray-700 dark:text-slate-300">
        <span>Gross principal</span>
        <span className="tabular-nums">{formatCurrency(gross)}</span>
      </div>
      <div className="flex justify-between px-3 py-2 text-sm text-gray-700 dark:text-slate-300">
        <span>Total deductions</span>
        <span className="font-semibold tabular-nums text-amber-900 dark:text-amber-300">{formatCurrency(totalDed)}</span>
      </div>
      <div className="flex justify-between border-t border-emerald-200 dark:border-emerald-800 bg-emerald-50 dark:bg-emerald-950/40 px-3 py-2.5 text-sm font-semibold text-emerald-900 dark:text-emerald-300">
        <span>Net credit to wallet</span>
        <span className="tabular-nums">{formatCurrency(netCredit)}</span>
      </div>
      {snapshot.hierarchy_adjusted ? (
        <p className="border-t border-amber-100 dark:border-amber-900 bg-amber-50/90 dark:bg-amber-950/40 px-3 py-2 text-xs leading-relaxed text-amber-950 dark:text-amber-200">
          Fee shares were adjusted because some upline roles were missing for this payer; rolled-up amounts appear in
          the Admin row where applicable.
        </p>
      ) : null}
    </div>
  );
}

function StatusBadge({ status }) {
  const s = (status || 'PENDING').toUpperCase();
  const map = {
    SUCCESS: 'bg-emerald-600 text-white border-emerald-700',
    PENDING: 'bg-amber-100 dark:bg-amber-900/40 text-amber-900 dark:text-amber-300 border-amber-200 dark:border-amber-800',
    PENDING_REVIEW: 'bg-amber-100 dark:bg-amber-900/40 text-amber-900 dark:text-amber-300 border-amber-200 dark:border-amber-800',
    FAILED: 'bg-red-100 dark:bg-red-900/40 text-red-800 dark:text-red-300 border-red-200 dark:border-red-800',
    FAILURE: 'bg-red-100 dark:bg-red-900/40 text-red-800 dark:text-red-300 border-red-200 dark:border-red-800',
  };
  const cls = map[s] || map.PENDING;
  return (
    <span className={`inline-flex rounded-full border px-4 py-1.5 text-xs font-bold ${cls}`}>{s}</span>
  );
}

/**
 * Pay In / Pay Out transaction detail — layout aligned with bill-payment reference.
 */
const ReportTransactionDetailModal = ({ open, onClose, variant, record }) => {
  const { user } = useAuth();
  useEffect(() => {
    if (!open) return undefined;
    const onKey = (e) => {
      if (e.key === 'Escape') onClose();
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [open, onClose]);

  if (!open || !record) return null;

  const isPayin = variant === 'payin';
  const showPayinFeeBreakdown =
    isPayin &&
    isAdminUser(user) &&
    record.detail?.feeSnapshot &&
    typeof record.detail.feeSnapshot === 'object';

  return (
    <div
      className="fixed inset-0 z-[70] flex items-center justify-center bg-black/50 p-4"
      role="presentation"
      onClick={onClose}
    >
      <div
        className="relative max-h-[90vh] w-full max-w-3xl overflow-y-auto rounded-2xl bg-white dark:bg-slate-900 shadow-2xl ring-1 ring-black/5"
        role="dialog"
        aria-modal="true"
        aria-labelledby="report-detail-title"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="sticky top-0 z-10 flex items-start justify-between border-b border-gray-100 dark:border-slate-800 bg-white dark:bg-slate-900 px-6 py-4">
          <h2 id="report-detail-title" className="text-lg font-bold text-gray-900 dark:text-slate-100 sm:text-xl">
            Transaction Details
          </h2>
          <button
            type="button"
            onClick={onClose}
            className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-red-500 text-white shadow-sm transition hover:bg-red-600"
            aria-label="Close"
          >
            <FiX className="h-5 w-5" strokeWidth={2.5} />
          </button>
        </div>

        <div className="space-y-6 p-6">
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
            <DetailField label="Transaction Id" value={record.transactionId} />
            <DetailField label="Request Id" value={record.requestId} />
            <DetailField label="Order Amount" value={formatCurrency(record.orderAmount)} />
          </div>
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
            <DetailField label="Bill Amount" value={formatCurrency(record.billAmount)} />
            <DetailField label="Charges" value={formatCurrency(record.charges)} />
            <DetailField label="Transaction Date" value={formatReportDateTime(record.date)} />
          </div>

          <div className="grid grid-cols-1 gap-6 border-t border-gray-100 dark:border-slate-800 pt-6 sm:grid-cols-2">
            <div>
              <h3 className="mb-3 text-sm font-bold text-gray-900 dark:text-slate-100">
                {isPayin ? 'Pay-in details' : 'Transfer details'}
              </h3>
              <dl className="space-y-3 text-sm">
                {isPayin ? (
                  <>
                    <div>
                      <dt className="text-gray-500 dark:text-slate-400">Package ID</dt>
                      <dd className="font-semibold text-gray-900 dark:text-slate-100">{record.detail?.packageId ?? '—'}</dd>
                    </div>
                    {record.detail?.packageDisplayName ? (
                      <div>
                        <dt className="text-gray-500 dark:text-slate-400">Package</dt>
                        <dd className="font-semibold text-gray-900 dark:text-slate-100">{record.detail.packageDisplayName}</dd>
                      </div>
                    ) : null}
                    <div>
                      <dt className="text-gray-500 dark:text-slate-400">Mode of payment</dt>
                      <dd className="font-semibold text-gray-900 dark:text-slate-100">{record.detail?.paymentModeDisplay || '—'}</dd>
                    </div>
                    <div>
                      <dt className="text-gray-500 dark:text-slate-400">Collection type</dt>
                      <dd className="font-semibold text-gray-900 dark:text-slate-100">
                        {record.detail?.railTypeLabel ||
                          (record.detail?.collectionRail === 'qr' ? 'Manual QR' : 'Payment Gateway')}
                      </dd>
                    </div>
                    <div>
                      <dt className="text-gray-500 dark:text-slate-400">
                        {record.detail?.collectionRail === 'qr' ? 'QR account' : 'Payment gateway'}
                      </dt>
                      <dd className="font-semibold text-gray-900 dark:text-slate-100">{record.detail?.paymentGatewayName || '—'}</dd>
                    </div>
                    {record.detail?.collectionRail === 'qr' ? (
                      <>
                        <div>
                          <dt className="text-gray-500 dark:text-slate-400">UTR</dt>
                          <dd className="break-all font-mono text-sm font-semibold text-gray-900 dark:text-slate-100">
                            {record.detail?.utr || '—'}
                          </dd>
                        </div>
                        {record.detail?.submittedAmount ? (
                          <div>
                            <dt className="text-gray-500 dark:text-slate-400">Submitted amount</dt>
                            <dd className="font-semibold text-gray-900 dark:text-slate-100">
                              {formatCurrency(parseFloat(record.detail.submittedAmount) || 0)}
                            </dd>
                          </div>
                        ) : null}
                        {record.detail?.proofReceiptUrl ? (
                          <div className="sm:col-span-2">
                            <dt className="text-gray-500 dark:text-slate-400">Payment proof</dt>
                            <dd className="mt-2">
                              <a href={record.detail.proofReceiptUrl} target="_blank" rel="noreferrer">
                                <img
                                  src={record.detail.proofReceiptUrl}
                                  alt="Payment proof"
                                  className="max-h-48 rounded border border-gray-200 dark:border-slate-700"
                                />
                              </a>
                            </dd>
                          </div>
                        ) : null}
                      </>
                    ) : null}
                    <div>
                      <dt className="text-gray-500 dark:text-slate-400">Opening balance (before pay-in)</dt>
                      <dd className="font-semibold text-gray-900 dark:text-slate-100">
                        {record.detail?.openingBalance != null && record.detail?.openingBalance !== ''
                          ? formatCurrency(parseFloat(record.detail.openingBalance) || 0)
                          : '—'}
                      </dd>
                    </div>
                    <div>
                      <dt className="text-gray-500 dark:text-slate-400">Closing balance (after pay-in)</dt>
                      <dd className="font-semibold text-gray-900 dark:text-slate-100">
                        {record.detail?.closingBalance != null && record.detail?.closingBalance !== ''
                          ? formatCurrency(parseFloat(record.detail.closingBalance) || 0)
                          : '—'}
                      </dd>
                    </div>
                    <div>
                      <dt className="text-gray-500 dark:text-slate-400">Package code</dt>
                      <dd className="font-semibold text-gray-900 dark:text-slate-100">{record.detail?.packageCode || '—'}</dd>
                    </div>
                    <div>
                      <dt className="text-gray-500 dark:text-slate-400">Customer name</dt>
                      <dd className="font-semibold text-gray-900 dark:text-slate-100">{record.detail?.customerName || '—'}</dd>
                    </div>
                    <div>
                      <dt className="text-gray-500 dark:text-slate-400">Email</dt>
                      <dd className="break-all font-semibold text-gray-900 dark:text-slate-100">{record.detail?.customerEmail || '—'}</dd>
                    </div>
                    <div>
                      <dt className="text-gray-500 dark:text-slate-400">Mobile number</dt>
                      <dd className="font-semibold text-gray-900 dark:text-slate-100">
                        {record.detail?.customerPhone || record.detail?.customerId || '—'}
                      </dd>
                    </div>
                    <div>
                      <dt className="text-gray-500 dark:text-slate-400">Card last 4</dt>
                      <dd className="font-semibold text-gray-900 dark:text-slate-100">{record.detail?.cardLast4 || '—'}</dd>
                    </div>
                    <div>
                      <dt className="text-gray-500 dark:text-slate-400">Bank / gateway txn id</dt>
                      <dd className="break-all font-semibold text-gray-900 dark:text-slate-100">{record.detail?.bankTxnId || '—'}</dd>
                    </div>
                    <div>
                      <dt className="text-gray-500 dark:text-slate-400">Provider order id</dt>
                      <dd className="break-all font-semibold text-gray-900 dark:text-slate-100">
                        {record.detail?.providerOrderId || '—'}
                      </dd>
                    </div>
                    <div>
                      <dt className="text-gray-500 dark:text-slate-400">Provider payment id</dt>
                      <dd className="break-all font-semibold text-gray-900 dark:text-slate-100">
                        {record.detail?.providerPaymentId || '—'}
                      </dd>
                    </div>
                    <div>
                      <dt className="text-gray-500 dark:text-slate-400">Gateway / Bank reference (UTR)</dt>
                      <dd className="break-all font-semibold text-gray-900 dark:text-slate-100">
                        {record.detail?.collectionRail === 'qr'
                          ? record.detail?.utr || '—'
                          : record.detail?.gatewayUtr ||
                            record.detail?.gatewayTransactionId ||
                            '—'}
                      </dd>
                    </div>
                    {record.detail?.rejectReason ? (
                      <div>
                        <dt className="text-gray-500 dark:text-slate-400">Rejection reason</dt>
                        <dd className="font-medium text-red-700 dark:text-red-300">{record.detail.rejectReason}</dd>
                      </div>
                    ) : null}
                    {record.detail?.agentDetails ? (
                      <div className="sm:col-span-2">
                        <dt className="text-gray-500 dark:text-slate-400">Agent</dt>
                        <dd className="mt-1 font-semibold text-gray-900 dark:text-slate-100">
                          {(record.detail.agentDetails.user_code || '—') +
                            ' · ' +
                            (record.detail.agentDetails.name || '—') +
                            ' · ' +
                            (record.detail.agentDetails.role || '—') +
                            (record.detail.agentDetails.mobile
                              ? ` · ${record.detail.agentDetails.mobile}`
                              : '')}
                        </dd>
                      </div>
                    ) : null}
                    {showPayinFeeBreakdown ? (
                      <div className="sm:col-span-2">
                        <dt className="text-gray-500 dark:text-slate-400">Fee breakdown</dt>
                        <dd className="mt-1">
                          <FeeBreakdownPanel snapshot={record.detail.feeSnapshot} />
                        </dd>
                      </div>
                    ) : null}
                    {record.failureReason ? (
                      <div>
                        <dt className="text-gray-500 dark:text-slate-400">Note</dt>
                        <dd className="font-medium text-red-700 dark:text-red-300">{record.failureReason}</dd>
                      </div>
                    ) : null}
                  </>
                ) : (
                  <>
                    <div>
                      <dt className="text-gray-500 dark:text-slate-400">Bank name</dt>
                      <dd className="font-semibold text-gray-900 dark:text-slate-100">{record.detail?.bankName || '—'}</dd>
                    </div>
                    <div>
                      <dt className="text-gray-500 dark:text-slate-400">Account number</dt>
                      <dd className="font-mono font-semibold text-gray-900 dark:text-slate-100">
                        {record.detail?.accountDisplay || record.detail?.accountMasked || '—'}
                      </dd>
                    </div>
                    <div>
                      <dt className="text-gray-500 dark:text-slate-400">IFSC</dt>
                      <dd className="font-mono font-semibold text-gray-900 dark:text-slate-100">{record.detail?.ifsc || '—'}</dd>
                    </div>
                    <div>
                      <dt className="text-gray-500 dark:text-slate-400">Beneficiary</dt>
                      <dd className="font-semibold text-gray-900 dark:text-slate-100">{record.detail?.beneficiaryName || '—'}</dd>
                    </div>
                    <div>
                      <dt className="text-gray-500 dark:text-slate-400">Transfer mode</dt>
                      <dd className="font-semibold text-gray-900 dark:text-slate-100">{record.detail?.transferMode || '—'}</dd>
                    </div>
                    <div>
                      <dt className="text-gray-500 dark:text-slate-400">UTR / Gateway reference</dt>
                      <dd className="break-all font-semibold text-gray-900 dark:text-slate-100">
                        {record.detail?.gatewayTransactionId || '—'}
                      </dd>
                    </div>
                    <div>
                      <dt className="text-gray-500 dark:text-slate-400">Platform fee</dt>
                      <dd className="font-semibold text-gray-900 dark:text-slate-100">
                        {formatCurrency(record.detail?.platformFee ?? 0)}
                      </dd>
                    </div>
                    <div>
                      <dt className="text-gray-500 dark:text-slate-400">Total debited (incl. charges)</dt>
                      <dd className="font-semibold text-gray-900 dark:text-slate-100">
                        {formatCurrency(record.detail?.totalDeducted ?? record.orderAmount)}
                      </dd>
                    </div>
                    {Array.isArray(record.detail?.commissionBreakdown) &&
                    record.detail.commissionBreakdown.length > 0 ? (
                      <div className="sm:col-span-2">
                        <dt className="text-gray-500 dark:text-slate-400">Commission breakdown</dt>
                        <dd className="mt-1 space-y-1 text-sm text-gray-800 dark:text-slate-200">
                          {record.detail.commissionBreakdown.map((c, i) => (
                            <div key={i} className="flex flex-wrap gap-2 border-b border-gray-100 dark:border-slate-800 py-1">
                              <span className="font-medium">{c.slice || c.role_at_time || '—'}</span>
                              <span>{formatCurrency(parseFloat(c.amount) || 0)}</span>
                            </div>
                          ))}
                        </dd>
                      </div>
                    ) : null}
                    {record.failureReason ? (
                      <div>
                        <dt className="text-gray-500 dark:text-slate-400">Note</dt>
                        <dd className="font-medium text-red-700 dark:text-red-300">{record.failureReason}</dd>
                      </div>
                    ) : null}
                  </>
                )}
              </dl>
            </div>
            <div className="flex flex-col justify-start">
              <p className="mb-2 text-xs font-medium uppercase tracking-wide text-gray-500 dark:text-slate-400">Status</p>
              <StatusBadge status={record.status} />
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default ReportTransactionDetailModal;
