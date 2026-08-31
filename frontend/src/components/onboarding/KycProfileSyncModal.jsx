import React, { useEffect, useState } from 'react';
import { FiX } from 'react-icons/fi';
import { FaArrowsRotate } from 'react-icons/fa6';
import Button from '../common/Button';

const formatDob = (value) => {
  if (!value) return '—';
  const s = String(value).trim();
  if (/^\d{4}-\d{2}-\d{2}/.test(s)) {
    const [y, m, d] = s.slice(0, 10).split('-');
    return `${d}-${m}-${y}`;
  }
  return s;
};

const CompareRow = ({ label, current, verified, differs }) => {
  if (!differs && !current && !verified) return null;
  return (
    <div className="rounded-xl border border-slate-200 dark:border-slate-700 bg-slate-50/80 dark:bg-slate-800/50 p-3">
      <p className="text-xs font-semibold uppercase tracking-wide text-slate-500 dark:text-slate-400 mb-2">{label}</p>
      <dl className="grid grid-cols-1 sm:grid-cols-2 gap-3 text-sm">
        <div>
          <dt className="text-slate-500 dark:text-slate-400">Current profile</dt>
          <dd className="font-medium text-slate-900 dark:text-slate-100 mt-0.5">{current || '—'}</dd>
        </div>
        <div>
          <dt className="text-emerald-700 dark:text-emerald-300">Verified (KYC)</dt>
          <dd className="font-medium text-emerald-900 dark:text-emerald-300 mt-0.5">{verified || '—'}</dd>
        </div>
      </dl>
    </div>
  );
};

/**
 * Confirm or decline syncing verified KYC name/DOB into the user profile.
 */
const KycProfileSyncModal = ({
  open,
  profileSync,
  loading = false,
  onConfirm,
  onDecline,
  onClose,
}) => {
  const [warning, setWarning] = useState('');

  useEffect(() => {
    if (open) setWarning('');
  }, [open, profileSync?.sync_token]);

  useEffect(() => {
    if (!open) return undefined;
    const onKey = (e) => {
      if (e.key === 'Escape' && !loading) onClose?.();
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [open, loading, onClose]);

  if (!open || !profileSync) return null;

  const mismatch = profileSync.mismatch || {};
  const nameBlock = mismatch.name || {};
  const dobBlock = mismatch.date_of_birth || {};

  const handleDecline = async () => {
    setWarning('');
    const result = await onDecline?.();
    if (result?.warning) {
      setWarning(result.warning);
    }
  };

  return (
    <div
      className="fixed inset-0 z-[80] flex items-center justify-center p-4 bg-black/50"
      role="presentation"
      onClick={() => !loading && onClose?.()}
    >
      <div
        className="relative w-full max-w-lg rounded-2xl bg-white dark:bg-slate-900 p-6 shadow-2xl ring-1 ring-black/5"
        role="dialog"
        aria-modal="true"
        aria-labelledby="kyc-profile-sync-title"
        onClick={(e) => e.stopPropagation()}
      >
        <button
          type="button"
          onClick={() => !loading && onClose?.()}
          className="absolute right-4 top-4 rounded-lg p-1 text-slate-400 dark:text-slate-500 hover:bg-slate-100 dark:hover:bg-slate-700 hover:text-slate-600 dark:hover:text-slate-400"
          aria-label="Close"
          disabled={loading}
        >
          <FiX size={22} />
        </button>

        <div className="flex items-start gap-3 pr-8">
          <div className="h-10 w-10 shrink-0 rounded-xl bg-indigo-100 dark:bg-indigo-900/40 flex items-center justify-center">
            <FaArrowsRotate className="text-indigo-600 dark:text-indigo-400" size={18} />
          </div>
          <div>
            <h2 id="kyc-profile-sync-title" className="text-xl font-bold text-slate-900 dark:text-slate-100">
              Update profile from verified KYC?
            </h2>
            <p className="mt-2 text-sm text-slate-600 dark:text-slate-400">
              {profileSync.message ||
                'Your profile name or date of birth differs from verified KYC records.'}
            </p>
          </div>
        </div>

        <div className="mt-4 space-y-3">
          <CompareRow
            label="Name"
            current={nameBlock.current}
            verified={nameBlock.verified}
            differs={nameBlock.differs}
          />
          <CompareRow
            label="Date of birth"
            current={dobBlock.current ? formatDob(dobBlock.current) : ''}
            verified={dobBlock.verified ? formatDob(dobBlock.verified) : ''}
            differs={Boolean(dobBlock.differs && (dobBlock.current || dobBlock.verified))}
          />
        </div>

        <p className="mt-4 text-xs text-slate-500 dark:text-slate-400">
          KYC verification is already complete. You can update your profile now or keep your current details.
        </p>

        {warning ? (
          <p role="alert" className="mt-3 text-sm text-amber-800 dark:text-amber-300 bg-amber-50 dark:bg-amber-950/40 border border-amber-100 dark:border-amber-900 rounded-lg px-3 py-2">
            {warning}
          </p>
        ) : null}

        <div className="mt-6 flex flex-col-reverse gap-3 sm:flex-row sm:justify-end">
          <Button type="button" variant="outline" size="lg" onClick={handleDecline} loading={loading} disabled={loading}>
            Keep current profile
          </Button>
          <Button type="button" variant="primary" size="lg" onClick={onConfirm} loading={loading} disabled={loading}>
            Update my profile
          </Button>
        </div>
      </div>
    </div>
  );
};

export default KycProfileSyncModal;
