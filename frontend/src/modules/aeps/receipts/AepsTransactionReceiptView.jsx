import React, { useMemo, useState } from 'react';
import { FaCircleCheck, FaTriangleExclamation, FaClock } from 'react-icons/fa6';
import Button from '../../../components/common/Button';
import { useAuth } from '../../../context/AuthContext';
import {
  aepsAckAllowed,
  aepsBalanceLabel,
  aepsNeedsStatusCheck,
  aepsProductLabel,
  aepsStatementRows,
  aepsStatusTone,
  buildAepsReceiptRows,
  formatAepsAmount,
  getMpayhubLogoSrc,
  normalizeAepsTxn,
} from './aepsReceiptFields';
import { buildAepsReceiptPrintHtml, openAepsReceiptPrint } from './aepsReceiptPrint';
import { isAepsOperatorRole, splitAepsMessageForRole } from '../utils/aepsUserCopy';

const ReceiptCell = ({ label, value, highlight, mono }) => {
  let valueClass = 'text-slate-900 dark:text-slate-100 font-medium';
  if (highlight === 'success') valueClass = 'text-emerald-700 dark:text-emerald-300 font-semibold';
  if (highlight === 'danger') valueClass = 'text-red-700 dark:text-red-300 font-semibold';
  if (highlight === 'pending') valueClass = 'text-amber-700 dark:text-amber-300 font-semibold capitalize';
  if (highlight === 'amount') valueClass = 'text-slate-900 dark:text-slate-100 font-semibold';
  if (highlight === 'neutral') valueClass = 'text-slate-800 dark:text-slate-200 font-semibold capitalize';

  return (
    <div className="border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900 px-3 py-2 min-h-[52px]">
      <div className="text-[10px] font-semibold uppercase tracking-wide text-slate-500 dark:text-slate-400 mb-0.5">
        {label}
      </div>
      <div className={`text-sm break-all ${mono ? 'font-mono text-xs' : ''} ${valueClass}`}>{value}</div>
    </div>
  );
};

const StatusBanner = ({ tone, title, subtitle }) => {
  const styles = {
    success:
      'border-emerald-200 bg-emerald-50 text-emerald-900 dark:border-emerald-900 dark:bg-emerald-950/50 dark:text-emerald-100',
    danger: 'border-red-200 bg-red-50 text-red-900 dark:border-red-900 dark:bg-red-950/40 dark:text-red-100',
    pending:
      'border-amber-200 bg-amber-50 text-amber-950 dark:border-amber-900 dark:bg-amber-950/40 dark:text-amber-100',
    neutral:
      'border-slate-200 bg-slate-50 text-slate-900 dark:border-slate-700 dark:bg-slate-800/50 dark:text-slate-100',
  };
  const Icon = tone === 'success' ? FaCircleCheck : tone === 'danger' ? FaTriangleExclamation : FaClock;
  return (
    <div className={`flex items-start gap-3 rounded-xl border px-4 py-3 ${styles[tone] || styles.neutral}`}>
      <Icon className="mt-0.5 shrink-0" size={18} />
      <div>
        <p className="text-sm font-bold">{title}</p>
        {subtitle ? <p className="mt-1 text-sm opacity-90">{subtitle}</p> : null}
      </div>
    </div>
  );
};

/**
 * On-screen branded AEPS receipt + print actions + gated status/ack.
 */
const AepsTransactionReceiptView = ({
  result,
  onStatusCheck,
  onAck,
  onDoAnother,
  busy = false,
  showActions = true,
  className = '',
}) => {
  const { user } = useAuth();
  const isOperator = isAepsOperatorRole(user);
  const txn = normalizeAepsTxn(result);
  const [supportOpen, setSupportOpen] = useState(false);

  const tone = aepsStatusTone(txn?.status);
  const messageParts = useMemo(
    () => splitAepsMessageForRole(txn?.response_message, { isOperator }),
    [txn?.response_message, isOperator]
  );

  if (!txn) return null;

  const { headline, support, display } = messageParts;
  const balanceLabel = aepsBalanceLabel(txn);
  const rows = aepsStatementRows(txn);
  const receiptRows = buildAepsReceiptRows(txn);
  const leftCells = receiptRows.filter((_, i) => i % 2 === 0);
  const rightCells = receiptRows.filter((_, i) => i % 2 === 1);
  const canAck = Boolean(onAck) && aepsAckAllowed(txn);
  const canStatus = Boolean(onStatusCheck) && aepsNeedsStatusCheck(txn);
  const isEnquiry = txn.product === 'BE' || txn.product === 'MS';
  const isMini = txn.product === 'MS';

  const bannerTitle =
    tone === 'success'
      ? 'Transaction successful'
      : tone === 'pending'
        ? 'Still confirming with the bank'
        : 'Transaction failed';
  const bannerSubtitle =
    tone === 'success'
      ? balanceLabel
        ? `Available balance: ${balanceLabel}`
        : `${aepsProductLabel(txn.product)} completed.`
      : tone === 'pending'
        ? 'Use Status check if this stays pending.'
        : display || headline || 'This request could not be completed.';

  const printReceipt = (mobile = false) => {
    const html = buildAepsReceiptPrintHtml(
      {
        ...txn,
        response_message: isOperator ? txn.response_message : display || headline,
      },
      { mobile }
    );
    openAepsReceiptPrint(html, { mobile });
  };

  return (
    <div className={`space-y-4 ${className}`}>
      <StatusBanner tone={tone} title={bannerTitle} subtitle={bannerSubtitle} />

      <div className="mpay-paper space-y-4 rounded-xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900 p-4 shadow-sm">
        <div className="flex flex-wrap items-start justify-between gap-3 border-b border-slate-100 dark:border-slate-800 pb-3">
          <img
            src={getMpayhubLogoSrc()}
            alt="mPayHub"
            className="h-10 w-auto max-w-[min(160px,40%)] shrink-0 object-contain object-left"
          />
          <div className="text-right text-xs text-slate-500 dark:text-slate-400">
            <div className="font-semibold text-slate-700 dark:text-slate-200">AEPS Receipt</div>
            <div>{txn.product_label || aepsProductLabel(txn.product)}</div>
            <div className="mt-1 font-mono text-[11px]">{txn.merchant_tran_id}</div>
          </div>
        </div>

        {balanceLabel && tone === 'success' ? (
          <div className="rounded-xl bg-emerald-50 px-4 py-3 ring-1 ring-emerald-100 dark:bg-emerald-950/40 dark:ring-emerald-900">
            <p className="text-[10px] font-semibold uppercase tracking-wide text-emerald-700 dark:text-emerald-300">
              Available balance
            </p>
            <p className="mt-0.5 text-2xl font-bold tabular-nums text-emerald-900 dark:text-emerald-100">
              {balanceLabel}
            </p>
          </div>
        ) : isEnquiry && tone === 'success' && !balanceLabel ? (
          <p className="text-sm text-slate-600 dark:text-slate-400">
            Bank did not return a displayable balance for this account.
          </p>
        ) : null}

        <div className="grid grid-cols-1 md:grid-cols-2 gap-0 border border-slate-200 dark:border-slate-700 rounded-lg overflow-hidden">
          <div className="grid grid-cols-1">
            {leftCells.map((cell) => (
              <ReceiptCell key={cell.label} {...cell} />
            ))}
          </div>
          <div className="grid grid-cols-1 md:border-l md:border-slate-200 dark:md:border-slate-700">
            {rightCells.map((cell) => (
              <ReceiptCell key={cell.label} {...cell} />
            ))}
          </div>
        </div>

        {rows.length ? (
          <div className="overflow-x-auto rounded-lg border border-slate-100 dark:border-slate-800">
            <table className="min-w-full text-left text-sm">
              <thead className="bg-slate-50 dark:bg-slate-800/50 text-xs uppercase text-slate-500 dark:text-slate-400">
                <tr>
                  <th className="px-3 py-2">Date</th>
                  <th className="px-3 py-2">Narration</th>
                  <th className="px-3 py-2">Amount</th>
                  <th className="px-3 py-2">Type</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((r, i) => (
                  <tr key={i} className="border-t border-slate-100 dark:border-slate-800">
                    <td className="px-3 py-2">{r.date || r.txnDate || '—'}</td>
                    <td className="px-3 py-2">{r.narration || r.remarks || '—'}</td>
                    <td className="px-3 py-2">{r.amount || r.txnAmount || '—'}</td>
                    <td className="px-3 py-2">{r.txnType || r.type || '—'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : isMini && tone === 'success' ? (
          <p className="rounded-lg border border-slate-100 bg-slate-50 px-3 py-2 text-sm text-slate-600 dark:border-slate-800 dark:bg-slate-800/50 dark:text-slate-400">
            Bank returned no mini-statement lines for this account.
            {balanceLabel ? ' Available balance is shown above.' : ''}
          </p>
        ) : null}

        {tone === 'danger' && (display || headline) ? (
          <div className="rounded-lg border border-red-100 bg-red-50/80 px-3 py-2 text-sm text-red-800 dark:border-red-900 dark:bg-red-950/30 dark:text-red-200">
            {display || headline}
          </div>
        ) : null}

        {isOperator && (support || txn.response_message) ? (
          <div>
            <button
              type="button"
              className="text-xs font-semibold text-slate-500 hover:text-slate-700 dark:text-slate-400 dark:hover:text-slate-200"
              onClick={() => setSupportOpen((v) => !v)}
            >
              {supportOpen ? 'Hide support details' : 'Show support details (Admin)'}
            </button>
            {supportOpen ? (
              <pre className="mt-2 whitespace-pre-wrap rounded-lg bg-slate-50 p-2 font-mono text-[11px] text-slate-600 dark:bg-slate-800/60 dark:text-slate-300">
                {txn.response_message || support}
              </pre>
            ) : null}
          </div>
        ) : null}

        {showActions ? (
          <div className="flex flex-wrap gap-2 pt-1">
            <Button size="sm" variant="secondary" onClick={() => printReceipt(false)}>
              Print / PDF
            </Button>
            <Button size="sm" variant="secondary" onClick={() => printReceipt(true)}>
              Mobile print
            </Button>
            {canStatus ? (
              <Button size="sm" variant="secondary" loading={busy} onClick={() => onStatusCheck(txn)}>
                Status check
              </Button>
            ) : null}
            {canAck ? (
              <Button size="sm" loading={busy} onClick={() => onAck(txn)}>
                Acknowledge
              </Button>
            ) : null}
            {!canAck && txn.acknowledged && ['CW', 'AP', 'CD', 'CD_OTP'].includes(String(txn.product || '').toUpperCase()) ? (
              <span className="inline-flex items-center rounded-lg bg-emerald-50 px-2.5 py-1.5 text-xs font-semibold text-emerald-800 dark:bg-emerald-950/40 dark:text-emerald-200">
                Acknowledged
              </span>
            ) : null}
            {!canAck && !txn.acknowledged && ['BE', 'MS', '2FA'].includes(String(txn.product || '').toUpperCase()) ? (
              <span className="inline-flex items-center rounded-lg bg-slate-100 px-2.5 py-1.5 text-xs font-medium text-slate-600 dark:bg-slate-800 dark:text-slate-300">
                Ack not required
              </span>
            ) : null}
            {onDoAnother ? (
              <Button size="sm" onClick={onDoAnother}>
                Do another
              </Button>
            ) : null}
          </div>
        ) : null}

        {tone === 'success' ? (
          <p className="text-xs text-slate-500 dark:text-slate-400">
            Amount {formatAepsAmount(txn.amount)} · Save or print this receipt for your customer.
          </p>
        ) : null}
      </div>
    </div>
  );
};

export default AepsTransactionReceiptView;
