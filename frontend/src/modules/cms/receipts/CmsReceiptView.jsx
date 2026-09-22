import React from 'react';
import { FaCircleCheck, FaTriangleExclamation, FaClock } from 'react-icons/fa6';
import Button from '../../../components/common/Button';
import { useAuth } from '../../../context/AuthContext';
import { getBrandingLogoUrl } from '../../../utils/brandingLogo';
import {
  cmsStatusTone,
  formatCmsAmount,
  formatCmsDateTime,
  isCmsOperatorRole,
  sanitizeCmsUserMessage,
} from '../utils/cmsUserCopy';

const Cell = ({ label, value, highlight, mono }) => {
  let valueClass = 'text-slate-900 dark:text-slate-100 font-medium';
  if (highlight === 'success') valueClass = 'text-emerald-700 dark:text-emerald-300 font-semibold';
  if (highlight === 'danger') valueClass = 'text-red-700 dark:text-red-300 font-semibold';
  if (highlight === 'pending') valueClass = 'text-amber-700 dark:text-amber-300 font-semibold capitalize';
  return (
    <div className="border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900 px-3 py-2 min-h-[52px]">
      <div className="text-[10px] font-semibold uppercase tracking-wide text-slate-500 dark:text-slate-400 mb-0.5">
        {label}
      </div>
      <div className={`text-sm break-all ${mono ? 'font-mono text-xs' : ''} ${valueClass}`}>{value || '—'}</div>
    </div>
  );
};

const CmsReceiptView = ({ txn, onClose, onRefresh }) => {
  const { user } = useAuth();
  const isOperator = isCmsOperatorRole(user);
  if (!txn) return null;
  const tone = cmsStatusTone(txn.status);
  const msg = isOperator ? txn.error_message : sanitizeCmsUserMessage(txn.error_message);
  const Icon = tone === 'success' ? FaCircleCheck : tone === 'danger' ? FaTriangleExclamation : FaClock;
  const banner =
    tone === 'success'
      ? 'border-emerald-200 bg-emerald-50 text-emerald-900 dark:border-emerald-900 dark:bg-emerald-950/50 dark:text-emerald-100'
      : tone === 'danger'
        ? 'border-red-200 bg-red-50 text-red-900 dark:border-red-900 dark:bg-red-950/40 dark:text-red-100'
        : 'border-amber-200 bg-amber-50 text-amber-950 dark:border-amber-900 dark:bg-amber-950/40 dark:text-amber-100';

  const printReceipt = () => {
    const w = window.open('', '_blank');
    if (!w) return;
    w.document.write(`<!doctype html><html><head><title>CMS Receipt</title>
      <style>body{font-family:system-ui;padding:24px} table{width:100%;border-collapse:collapse}
      td,th{border:1px solid #ddd;padding:8px;text-align:left}</style></head><body>
      <h1>mPayHub — CMS Receipt</h1>
      <p>${txn.product_label || 'Cash Collection'} · ${txn.merchant_transaction_id}</p>
      <table>
        <tr><th>Status</th><td>${txn.status}</td></tr>
        <tr><th>Amount</th><td>${formatCmsAmount(txn.amount)}</td></tr>
        <tr><th>Network txn</th><td>${txn.fp_transaction_id || '—'}</td></tr>
        <tr><th>BC login</th><td>${txn.bc_login_id || '—'}</td></tr>
        <tr><th>When</th><td>${formatCmsDateTime(txn.created_at)}</td></tr>
      </table>
      <script>window.print()</script></body></html>`);
    w.document.close();
  };

  return (
    <div className="space-y-4">
      <div className={`flex items-start gap-3 rounded-xl border px-4 py-3 ${banner}`}>
        <Icon className="mt-0.5 shrink-0" size={18} />
        <div>
          <p className="text-sm font-bold capitalize">
            {tone === 'success' ? 'Transaction successful' : tone === 'danger' ? 'Transaction failed' : 'In progress'}
          </p>
          {msg ? <p className="mt-1 text-sm opacity-90">{msg}</p> : null}
        </div>
      </div>

      <div className="rounded-xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900 p-4">
        <div className="mb-3 flex items-start justify-between gap-3 border-b border-slate-100 dark:border-slate-800 pb-3">
          <img src={getBrandingLogoUrl()} alt="mPayHub" className="h-10 w-auto object-contain" />
          <div className="text-right text-xs text-slate-500">
            <div className="font-semibold text-slate-700 dark:text-slate-200">CMS Receipt</div>
            <div>{txn.product_label || 'Cash Collection'}</div>
            <div className="mt-1 font-mono text-[11px]">{txn.merchant_transaction_id}</div>
          </div>
        </div>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-0 border border-slate-200 dark:border-slate-700 rounded-lg overflow-hidden">
          <Cell label="Status" value={txn.status} highlight={tone} />
          <Cell label="Amount" value={formatCmsAmount(txn.amount)} />
          <Cell label="Network txn" value={txn.fp_transaction_id} mono />
          <Cell label="Our txn id" value={txn.merchant_transaction_id} mono />
          <Cell label="BC login" value={txn.bc_login_id} mono />
          <Cell label="Type" value={txn.type_of_transaction || 'CDC'} />
          <Cell label="When" value={formatCmsDateTime(txn.created_at)} />
          <Cell label="Finalized" value={formatCmsDateTime(txn.finalized_at)} />
        </div>
        <div className="mt-4 flex flex-wrap gap-2">
          <Button size="sm" variant="secondary" onClick={printReceipt}>
            Print / PDF
          </Button>
          {onRefresh ? (
            <Button size="sm" variant="secondary" onClick={onRefresh}>
              Refresh
            </Button>
          ) : null}
          {onClose ? (
            <Button size="sm" onClick={onClose}>
              Close
            </Button>
          ) : null}
        </div>
      </div>
    </div>
  );
};

export default CmsReceiptView;
