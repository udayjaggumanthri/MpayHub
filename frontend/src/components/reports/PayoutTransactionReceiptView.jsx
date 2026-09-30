import React from 'react';
import { FaCircleCheck } from 'react-icons/fa6';

import {
  buildPayoutReceiptRows,
  buildPayoutReceiptSummary,
  getMpayhubLogoSrc,
} from './payoutReceiptFields';

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

const PayoutTransactionReceiptView = ({
  transaction,
  loading = false,
  onPrint,
  onMobilePrint,
  showActions = true,
  className = '',
}) => {
  if (!transaction) return null;

  const rows = buildPayoutReceiptRows(transaction);
  const summary = buildPayoutReceiptSummary(transaction);
  const status = String(transaction.status || '').toUpperCase();
  const isSuccess = status === 'SUCCESS';
  const isPending = status === 'PENDING';
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
            <div className="font-semibold text-gray-700">Pay Out Receipt</div>
            <div>{transaction.transferMode || 'Bank Transfer'}</div>
          </div>
        </div>
        <div className="flex justify-center">
          {isSuccess ? (
            <span className="inline-flex items-center gap-2 rounded-full border border-emerald-300 bg-emerald-50 px-4 py-2 text-sm font-semibold text-emerald-800">
              <FaCircleCheck size={16} />
              Payout Successful
            </span>
          ) : isPending ? (
            <span className="inline-flex items-center rounded-full border border-amber-300 bg-amber-50 px-4 py-2 text-sm font-semibold text-amber-900">
              Payout In Progress
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

export default PayoutTransactionReceiptView;
