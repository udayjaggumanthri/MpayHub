import React, { useEffect } from 'react';
import { FiX } from 'react-icons/fi';
import { formatCurrency, formatReportDateTime } from '../../utils/formatters';

function DetailField({ label, value }) {
  return (
    <div className="min-w-0">
      <p className="text-xs font-medium uppercase tracking-wide text-gray-500">{label}</p>
      <p className="mt-1 break-all text-sm font-semibold text-gray-900">{value ?? '—'}</p>
    </div>
  );
}

function StatusBadge({ status }) {
  const s = (status || 'PENDING').toUpperCase();
  const map = {
    SUCCESS: 'bg-emerald-600 text-white border-emerald-700',
    PENDING: 'bg-amber-100 text-amber-900 border-amber-200',
    FAILED: 'bg-red-100 text-red-800 border-red-200',
    FAILURE: 'bg-red-100 text-red-800 border-red-200',
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

  return (
    <div
      className="fixed inset-0 z-[70] flex items-center justify-center bg-black/50 p-4"
      role="presentation"
      onClick={onClose}
    >
      <div
        className="relative max-h-[90vh] w-full max-w-3xl overflow-y-auto rounded-2xl bg-white shadow-2xl ring-1 ring-black/5"
        role="dialog"
        aria-modal="true"
        aria-labelledby="report-detail-title"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="sticky top-0 z-10 flex items-start justify-between border-b border-gray-100 bg-white px-6 py-4">
          <h2 id="report-detail-title" className="text-lg font-bold text-gray-900 sm:text-xl">
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

          <div className="grid grid-cols-1 gap-6 border-t border-gray-100 pt-6 sm:grid-cols-2">
            <div>
              <h3 className="mb-3 text-sm font-bold text-gray-900">
                {isPayin ? 'Pay-in details' : 'Transfer details'}
              </h3>
              <dl className="space-y-3 text-sm">
                {isPayin ? (
                  <>
                    <div>
                      <dt className="text-gray-500">Package ID</dt>
                      <dd className="font-semibold text-gray-900">{record.detail?.packageId ?? '—'}</dd>
                    </div>
                    <div>
                      <dt className="text-gray-500">Mode of payment</dt>
                      <dd className="font-semibold text-gray-900">{record.detail?.paymentModeDisplay || '—'}</dd>
                    </div>
                    <div>
                      <dt className="text-gray-500">Payment gateway</dt>
                      <dd className="font-semibold text-gray-900">{record.detail?.paymentGatewayName || '—'}</dd>
                    </div>
                    <div>
                      <dt className="text-gray-500">Package code</dt>
                      <dd className="font-semibold text-gray-900">{record.detail?.packageCode || '—'}</dd>
                    </div>
                    <div>
                      <dt className="text-gray-500">Customer name</dt>
                      <dd className="font-semibold text-gray-900">{record.detail?.customerName || '—'}</dd>
                    </div>
                    <div>
                      <dt className="text-gray-500">Email</dt>
                      <dd className="break-all font-semibold text-gray-900">{record.detail?.customerEmail || '—'}</dd>
                    </div>
                    <div>
                      <dt className="text-gray-500">Mobile number</dt>
                      <dd className="font-semibold text-gray-900">{record.detail?.customerPhone || '—'}</dd>
                    </div>
                    <div>
                      <dt className="text-gray-500">Gateway / Bank reference (UTR)</dt>
                      <dd className="break-all font-semibold text-gray-900">
                        {record.detail?.gatewayTransactionId || '—'}
                      </dd>
                    </div>
                    {record.failureReason ? (
                      <div>
                        <dt className="text-gray-500">Note</dt>
                        <dd className="font-medium text-red-700">{record.failureReason}</dd>
                      </div>
                    ) : null}
                  </>
                ) : (
                  <>
                    <div>
                      <dt className="text-gray-500">Bank name</dt>
                      <dd className="font-semibold text-gray-900">{record.detail?.bankName || '—'}</dd>
                    </div>
                    <div>
                      <dt className="text-gray-500">Account number</dt>
                      <dd className="font-mono font-semibold text-gray-900">{record.detail?.accountDisplay || '—'}</dd>
                    </div>
                    <div>
                      <dt className="text-gray-500">IFSC</dt>
                      <dd className="font-mono font-semibold text-gray-900">{record.detail?.ifsc || '—'}</dd>
                    </div>
                    <div>
                      <dt className="text-gray-500">Beneficiary</dt>
                      <dd className="font-semibold text-gray-900">{record.detail?.beneficiaryName || '—'}</dd>
                    </div>
                    <div>
                      <dt className="text-gray-500">Transfer mode</dt>
                      <dd className="font-semibold text-gray-900">{record.detail?.transferMode || '—'}</dd>
                    </div>
                    <div>
                      <dt className="text-gray-500">UTR / Gateway reference</dt>
                      <dd className="break-all font-semibold text-gray-900">
                        {record.detail?.gatewayTransactionId || '—'}
                      </dd>
                    </div>
                    <div>
                      <dt className="text-gray-500">Platform fee</dt>
                      <dd className="font-semibold text-gray-900">
                        {formatCurrency(record.detail?.platformFee ?? 0)}
                      </dd>
                    </div>
                    <div>
                      <dt className="text-gray-500">Total debited (incl. charges)</dt>
                      <dd className="font-semibold text-gray-900">
                        {formatCurrency(record.detail?.totalDeducted ?? record.orderAmount)}
                      </dd>
                    </div>
                    {record.failureReason ? (
                      <div>
                        <dt className="text-gray-500">Note</dt>
                        <dd className="font-medium text-red-700">{record.failureReason}</dd>
                      </div>
                    ) : null}
                  </>
                )}
              </dl>
            </div>
            <div className="flex flex-col justify-start">
              <p className="mb-2 text-xs font-medium uppercase tracking-wide text-gray-500">Status</p>
              <StatusBadge status={record.status} />
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default ReportTransactionDetailModal;
