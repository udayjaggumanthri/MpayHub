import React from 'react';
import { FaCircleCheck } from 'react-icons/fa6';

import bAssuredPrimary from '../../assets/bbps/b-assured-primary.svg';
import { bAssuredLogoClass } from './bbpsLogoSizes';
import { MPAYHUB_LOGO_SRC, buildBbpsReceiptRows, buildBbpsReceiptSummary } from './bbpsReceiptFields';

const ReceiptCell = ({ label, value, highlight, mono }) => {
  let valueClass = 'text-gray-900 font-medium';
  if (highlight === 'success') valueClass = 'text-emerald-600 font-semibold capitalize';
  if (highlight === 'danger') valueClass = 'text-red-600 font-semibold capitalize';
  if (highlight === 'amount') valueClass = 'text-gray-900 font-semibold';

  return (
    <div className="border border-gray-300 bg-white px-3 py-2 min-h-[52px]">
      <div className="text-xs text-gray-600 mb-0.5">{label}</div>
      <div className={`text-sm break-all ${mono ? 'font-mono text-xs' : ''} ${valueClass}`}>{value}</div>
    </div>
  );
};

/**
 * Enterprise BBPS receipt layout (reference: dual logos, grid table, summary, actions).
 */
const BbpsTransactionReceiptView = ({
  transaction,
  identity,
  loading = false,
  onPrint,
  onMobilePrint,
  onAnotherTransaction,
  showActions = true,
  className = '',
}) => {
  if (!transaction) return null;

  const rows = buildBbpsReceiptRows(transaction, identity);
  const summary = buildBbpsReceiptSummary(transaction, identity);
  const isSuccess = String(transaction.status || '').toUpperCase() === 'SUCCESS';
  const leftCells = rows.filter((_, i) => i % 2 === 0);
  const rightCells = rows.filter((_, i) => i % 2 === 1);

  return (
    <div className={`space-y-4 ${className}`}>
      <div className="flex flex-wrap items-center justify-between gap-4 border-b border-gray-200 pb-4">
        <img
          src={MPAYHUB_LOGO_SRC}
          alt="mPayHub"
          className="h-10 w-auto max-w-[160px] object-contain object-left"
        />
        <div className="flex-1 flex justify-center min-w-[140px]">
          {isSuccess ? (
            <span className="inline-flex items-center gap-2 rounded-full border border-emerald-300 bg-emerald-50 px-4 py-2 text-sm font-semibold text-emerald-800">
              <FaCircleCheck size={16} />
              Payment Successful
            </span>
          ) : (
            <span className="inline-flex items-center rounded-full border border-gray-300 bg-gray-50 px-4 py-2 text-sm font-semibold text-gray-800 capitalize">
              {transaction.status || 'Unknown'}
            </span>
          )}
        </div>
        <img src={bAssuredPrimary} alt="B Assured logo" className={bAssuredLogoClass} />
      </div>

      {loading ? (
        <p className="text-sm text-gray-500 text-center py-2">Refreshing receipt details...</p>
      ) : null}

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
        <div className="rounded-lg border border-emerald-200 bg-emerald-50/80 px-4 py-3 text-sm text-gray-800 leading-relaxed">
          {summary}
        </div>
      ) : null}

      {showActions ? (
        <div className="flex flex-wrap items-center justify-between gap-3 pt-2">
          <div className="flex flex-wrap gap-2">
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
          {onAnotherTransaction ? (
            <button
              type="button"
              onClick={onAnotherTransaction}
              className="px-4 py-2 text-sm font-medium text-rose-700 border border-rose-500 rounded hover:bg-rose-50 transition-colors"
            >
              Another Transaction
            </button>
          ) : null}
        </div>
      ) : null}
    </div>
  );
};

export default BbpsTransactionReceiptView;
