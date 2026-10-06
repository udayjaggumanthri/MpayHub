import React from 'react';
import { FaEye, FaTrash, FaXmark, FaTriangleExclamation } from 'react-icons/fa6';
import { formatPhone } from '../../utils/formatters';
import Button from '../common/Button';
import Card from '../common/Card';
import { linkedContactLabel } from './BankAccountPager';

const formatDetailValue = (value) => {
  if (value === null || value === undefined || value === '') return '—';
  if (typeof value === 'object') return JSON.stringify(value, null, 2);
  return String(value);
};

const DetailGrid = ({ rows }) => (
  <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
    {rows.map(([label, value]) => (
      <div key={label} className="rounded-lg border border-gray-200 dark:border-slate-700 p-3 bg-gray-50 dark:bg-slate-800/50 min-w-0">
        <p className="text-xs font-medium text-gray-500 dark:text-slate-400">{label}</p>
        <p className="text-sm font-medium text-gray-900 dark:text-slate-100 mt-1 break-words">{formatDetailValue(value)}</p>
      </div>
    ))}
  </div>
);

export const BankAccountDetailsModal = ({ account, onClose }) => {
  if (!account) return null;

  const details = account.verification_details || {};
  const ifscDetails = details.ifsc_details || {};
  const contacts = Array.isArray(account.linked_contacts) ? account.linked_contacts : [];

  const rows = [
    ['Beneficiary name', account.beneficiary_name || account.account_holder_name],
    ['Account holder', account.account_holder_name],
    ['Account number', account.account_number],
    ['IFSC', account.ifsc],
    ['Bank name', account.bank_name],
    ['Mobile number', account.mobile_number ? formatPhone(account.mobile_number) : '—'],
    ['Branch', account.branch || details.branch],
    ['City', account.city || details.city],
    ['Reference ID', account.verification_reference_id || details.reference_id],
    ['Account status', details.account_status],
    ['Status code', details.account_status_code],
    ['Name match score', account.name_match_score || details.name_match_score],
    ['Name match result', account.name_match_result || details.name_match_result],
    ['UTR', details.utr],
    ['MICR', details.micr],
    ['Verified at', account.verified_at ? new Date(account.verified_at).toLocaleString() : '—'],
    ['Provider', account.provider_code],
    ['Verified', account.is_verified ? 'Yes' : 'No'],
  ];

  const ifscRows = Object.entries(ifscDetails).map(([key, value]) => [
    key.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase()),
    formatDetailValue(value),
  ]);

  return (
    <div
      className="fixed inset-0 z-50 flex items-end sm:items-center justify-center p-0 sm:p-4 bg-slate-900/60 backdrop-blur-sm overflow-y-auto"
      role="dialog"
      aria-modal="true"
      aria-labelledby="bank-account-details-title"
      onClick={onClose}
    >
      <div className="w-full sm:max-w-2xl" onClick={(e) => e.stopPropagation()}>
      <Card
        className="w-full border border-gray-200 dark:border-slate-700 sm:my-auto rounded-t-2xl sm:rounded-xl max-h-[92vh] flex flex-col"
        padding="lg"
        shadow="xl"
      >
        <div className="flex items-start justify-between gap-3 mb-4" onClick={(e) => e.stopPropagation()}>
          <div className="min-w-0">
            <h2 id="bank-account-details-title" className="text-xl font-bold text-gray-900 dark:text-slate-100">
              Bank account details
            </h2>
            <p className="mt-1 text-sm text-gray-600 dark:text-slate-400 break-all">
              {account.account_number || '—'} · {account.ifsc || '—'}
            </p>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="shrink-0 text-gray-400 dark:text-slate-500 hover:text-gray-600 dark:hover:text-slate-300 p-1"
            aria-label="Close"
          >
            <FaXmark size={20} />
          </button>
        </div>

        <div className="space-y-6 max-h-[60vh] overflow-y-auto pr-1">
          <div>
            <h3 className="text-sm font-semibold text-gray-700 dark:text-slate-300 mb-3">Linked contacts</h3>
            {contacts.length > 0 ? (
              <div className="space-y-2">
                {contacts.map((row) => (
                  <div key={row.id} className="rounded-lg border border-gray-200 dark:border-slate-700 px-3 py-2 bg-gray-50 dark:bg-slate-800/50">
                    <p className="text-sm font-medium text-gray-900 dark:text-slate-100">{row.name || `Contact #${row.id}`}</p>
                    <p className="text-xs text-gray-500 dark:text-slate-400 mt-0.5">{row.phone ? formatPhone(row.phone) : '—'}</p>
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-sm text-gray-700 dark:text-slate-300">{linkedContactLabel(account)}</p>
            )}
          </div>

          <div>
            <h3 className="text-sm font-semibold text-gray-700 dark:text-slate-300 mb-3">Account summary</h3>
            <DetailGrid rows={rows} />
          </div>

          {ifscRows.length > 0 && (
            <div>
              <h3 className="text-sm font-semibold text-gray-700 dark:text-slate-300 mb-3">IFSC details</h3>
              <DetailGrid rows={ifscRows} />
            </div>
          )}
        </div>

        <div className="mt-6">
          <Button onClick={onClose} variant="primary" fullWidth>
            Close
          </Button>
        </div>
      </Card>
      </div>
    </div>
  );
};

export const BankAccountConfirmModal = ({
  title,
  description,
  account,
  confirmLabel,
  confirmVariant = 'danger',
  loading,
  onCancel,
  onConfirm,
}) => {
  if (!account) return null;

  return (
    <div
      className="fixed inset-0 z-50 flex items-end sm:items-center justify-center p-0 sm:p-4 bg-slate-900/60 backdrop-blur-sm"
      role="dialog"
      aria-modal="true"
      aria-labelledby="bank-account-confirm-title"
      onClick={() => !loading && onCancel()}
    >
      <div
        className="w-full sm:max-w-md rounded-t-2xl sm:rounded-2xl bg-white dark:bg-slate-900 p-6 shadow-2xl"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-start gap-4">
          <div className="flex h-12 w-12 shrink-0 items-center justify-center rounded-xl bg-red-50 dark:bg-red-950/40 text-red-700 dark:text-red-300">
            <FaTriangleExclamation size={22} aria-hidden />
          </div>
          <div className="min-w-0 flex-1">
            <h3 id="bank-account-confirm-title" className="text-lg font-bold text-slate-900 dark:text-slate-100">
              {title}
            </h3>
            <p className="mt-1 text-sm text-slate-600 dark:text-slate-400">{description}</p>
          </div>
        </div>

        <div className="mt-4 rounded-xl border border-slate-100 dark:border-slate-800 bg-slate-50 dark:bg-slate-800/50 px-4 py-3 text-sm text-slate-700 dark:text-slate-300 space-y-1">
          <p>
            <span className="font-medium">Account holder:</span>{' '}
            {account.account_holder_name || account.beneficiary_name || '—'}
          </p>
          <p className="break-all">
            <span className="font-medium">Account number:</span> {account.account_number || '—'}
          </p>
          <p>
            <span className="font-medium">IFSC:</span> {account.ifsc || '—'}
          </p>
          {account.mobile_number ? (
            <p>
              <span className="font-medium">Mobile:</span> {formatPhone(account.mobile_number)}
            </p>
          ) : null}
        </div>

        <div className="mt-6 flex flex-col-reverse sm:flex-row gap-3 sm:justify-end">
          <Button onClick={onCancel} disabled={loading} variant="outline" size="lg" className="w-full sm:w-auto">
            Cancel
          </Button>
          <Button
            onClick={onConfirm}
            loading={loading}
            variant={confirmVariant}
            size="lg"
            icon={FaTrash}
            iconPosition="left"
            className="w-full sm:w-auto"
          >
            {confirmLabel}
          </Button>
        </div>
      </div>
    </div>
  );
};

export const AccountRowActions = ({ onView, onRemove, onDelete }) => (
  <div className="inline-flex flex-nowrap items-center gap-1">
    <button
      type="button"
      onClick={onView}
      className="inline-flex items-center gap-1.5 text-sm font-semibold text-blue-600 dark:text-blue-400 hover:text-blue-800 dark:hover:text-blue-200 px-2.5 py-1.5 rounded-lg hover:bg-blue-50 dark:hover:bg-blue-950/60"
    >
      <FaEye size={16} />
      View
    </button>
    {onRemove ? (
      <button
        type="button"
        onClick={onRemove}
        className="inline-flex items-center gap-1.5 text-sm font-semibold text-red-600 dark:text-red-400 hover:text-red-800 dark:hover:text-red-200 px-2.5 py-1.5 rounded-lg hover:bg-red-50 dark:hover:bg-red-950/60"
      >
        <FaTrash size={15} />
        Remove
      </button>
    ) : null}
    {onDelete ? (
      <button
        type="button"
        onClick={onDelete}
        className="inline-flex items-center gap-1.5 text-sm font-semibold text-red-600 dark:text-red-400 hover:text-red-800 dark:hover:text-red-200 px-2.5 py-1.5 rounded-lg hover:bg-red-50 dark:hover:bg-red-950/60"
      >
        <FaTrash size={15} />
        Delete
      </button>
    ) : null}
  </div>
);
