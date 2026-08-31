import React from 'react';
import { FaCircleCheck, FaDownload } from 'react-icons/fa6';

import AuthenticatedImage from '../common/AuthenticatedImage';
import { downloadFromUrl } from '../../utils/downloadFile';
import { payinQrReceiptApiUrl } from '../../utils/mediaUrl';
import { buildPayinReceiptRows, buildPayinReceiptSummary, getMpayhubLogoSrc } from './payinReceiptFields';

const ReceiptCell = ({ label, value, highlight, mono }) => {
  let valueClass = 'text-gray-900 font-medium';
  if (highlight === 'success') valueClass = 'text-emerald-600 font-semibold uppercase';
  if (highlight === 'danger') valueClass = 'text-red-600 font-semibold';
  if (highlight === 'amount') valueClass = 'text-gray-900 font-semibold';

  return (
    <div className="border border-gray-300 bg-white px-3 py-2 min-h-[52px]">
      <div className="text-xs text-gray-600 mb-0.5">{label}</div>
      <div className={`text-sm break-all ${mono ? 'font-mono text-xs' : ''} ${valueClass}`}>{value}</div>
    </div>
  );
};

const PayinTransactionReceiptView = ({
  transaction,
  loading = false,
  onPrint,
  onMobilePrint,
  showActions = true,
  className = '',
}) => {
  if (!transaction) return null;

  const rows = buildPayinReceiptRows(transaction);
  const summary = buildPayinReceiptSummary(transaction);
  const isSuccess = String(transaction.status || '').toUpperCase() === 'SUCCESS';
  const leftCells = rows.filter((_, i) => i % 2 === 0);
  const rightCells = rows.filter((_, i) => i % 2 === 1);

  return (
    <div className={`mpay-paper space-y-4 rounded-xl p-4 ${className}`}>
      <div className="space-y-4 border-b border-gray-200 pb-4">
        <div className="flex flex-wrap items-start justify-between gap-x-4 gap-y-3">
          <img
            src={getMpayhubLogoSrc()}
            alt="mPayHub"
            className="h-10 w-auto max-w-[min(160px,40%)] shrink-0 object-contain object-left"
          />
          <div className="text-right text-xs text-gray-500">
            <div className="font-semibold text-gray-700">Pay-in Receipt</div>
            <div>{transaction.railTypeLabel || 'Wallet Top-up'}</div>
          </div>
        </div>
        <div className="flex justify-center">
          {isSuccess ? (
            <span className="inline-flex items-center gap-2 rounded-full border border-emerald-300 bg-emerald-50 px-4 py-2 text-sm font-semibold text-emerald-800">
              <FaCircleCheck size={16} />
              Pay-in Successful
            </span>
          ) : (
            <span className="inline-flex items-center rounded-full border border-gray-300 bg-gray-50 px-4 py-2 text-sm font-semibold text-gray-800 capitalize">
              {transaction.status || 'Unknown'}
            </span>
          )}
        </div>
      </div>

      {loading ? <p className="text-sm text-gray-500 text-center py-2">Loading receipt…</p> : null}

      <div className="grid grid-cols-1 md:grid-cols-2 gap-0 border border-gray-300 rounded-lg overflow-hidden">
        <div className="grid grid-cols-1">
          {leftCells.map((cell) => (
            <ReceiptCell key={cell.label} {...cell} />
          ))}
        </div>
        <div className="grid grid-cols-1 md:border-l md:border-gray-300">
          {rightCells.map((cell) => (
            <ReceiptCell key={cell.label} {...cell} />
          ))}
        </div>
      </div>

      {transaction.hasProofImage && transaction.proofReceiptUrl ? (
        <div className="rounded-lg border border-gray-200 bg-gray-50 p-4">
          <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
            <p className="text-xs font-semibold uppercase tracking-wide text-gray-600">Payment proof (uploaded)</p>
            <button
              type="button"
              onClick={async () => {
                const txnId = transaction.transactionId;
                const url =
                  transaction.proofReceiptUrl ||
                  (txnId ? payinQrReceiptApiUrl(txnId, { download: true }) : '');
                if (!url) return;
                try {
                  await downloadFromUrl(url, `receipt-${txnId || 'proof'}.jpg`);
                } catch {
                  // ignore — user can retry
                }
              }}
              className="inline-flex items-center gap-1 text-xs font-semibold text-blue-700 hover:text-blue-900"
            >
              <FaDownload size={12} />
              Download proof
            </button>
          </div>
          <AuthenticatedImage
            src={transaction.proofReceiptUrl}
            alt="Payment proof"
            className="max-h-72 rounded border border-gray-300 bg-white object-contain mx-auto"
          />
        </div>
      ) : null}

      {summary ? (
        <div className="rounded-lg border border-blue-200 bg-blue-50/80 px-4 py-3 text-sm text-gray-800 leading-relaxed">
          {summary}
        </div>
      ) : null}

      {showActions ? (
        <div className="flex flex-wrap items-center gap-3 pt-2">
          <button
            type="button"
            onClick={onPrint}
            className="px-4 py-2 text-sm font-medium text-blue-700 border border-blue-600 rounded hover:bg-blue-50 transition-colors"
          >
            Print
          </button>
          <button
            type="button"
            onClick={onMobilePrint}
            className="px-4 py-2 text-sm font-medium text-blue-700 border border-blue-600 rounded hover:bg-blue-50 transition-colors"
          >
            Mobile Print
          </button>
        </div>
      ) : null}

      <p className="text-center text-xs text-gray-400">This is a system-generated receipt. No signature is required.</p>
    </div>
  );
};

export default PayinTransactionReceiptView;
