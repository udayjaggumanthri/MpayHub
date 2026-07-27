import React, { useEffect, useState } from 'react';
import { FiX } from 'react-icons/fi';
import { FaTriangleExclamation } from 'react-icons/fa6';
import Button from '../common/Button';
import { formatUserId } from '../../utils/formatters';

/**
 * Destructive confirmation before permanently deleting a user account.
 */
const DeleteUserConfirmModal = ({
  open,
  user,
  loading = false,
  onConfirm,
  onCancel,
}) => {
  const [confirmText, setConfirmText] = useState('');

  const displayName = user
    ? `${user.first_name || ''} ${user.last_name || ''}`.trim() || 'User'
    : '';
  const userCode = user ? formatUserId(user.display_code || user.member_id || user.user_id || user.id) : '';
  const requiredToken = userCode;

  useEffect(() => {
    if (!open) setConfirmText('');
  }, [open]);

  useEffect(() => {
    if (!open) return undefined;
    const onKey = (e) => {
      if (e.key === 'Escape' && !loading) onCancel?.();
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [open, loading, onCancel]);

  if (!open || !user) return null;

  const canConfirm = confirmText.trim() === requiredToken && !loading;

  return (
    <div
      className="fixed inset-0 z-[70] flex items-center justify-center p-4 bg-black/50"
      role="presentation"
      onClick={() => !loading && onCancel?.()}
    >
      <div
        className="relative w-full max-w-lg rounded-2xl bg-white p-6 shadow-2xl ring-1 ring-black/5"
        role="alertdialog"
        aria-modal="true"
        aria-labelledby="delete-user-modal-title"
        onClick={(e) => e.stopPropagation()}
      >
        <button
          type="button"
          onClick={() => !loading && onCancel?.()}
          className="absolute right-4 top-4 rounded-lg p-1 text-slate-400 transition-colors hover:bg-slate-100 hover:text-slate-600"
          aria-label="Close"
          disabled={loading}
        >
          <FiX size={22} />
        </button>

        <div className="flex items-start gap-3 pr-8">
          <div className="h-10 w-10 shrink-0 rounded-xl bg-red-100 flex items-center justify-center">
            <FaTriangleExclamation className="text-red-600" size={18} />
          </div>
          <div>
            <h2 id="delete-user-modal-title" className="text-xl font-bold text-slate-900">
              Delete user permanently?
            </h2>
            <p className="mt-2 text-sm text-slate-600">
              This will permanently remove <span className="font-semibold text-slate-900">{displayName}</span>{' '}
              (<span className="font-mono">{userCode}</span>) and all related data from the database.
            </p>
          </div>
        </div>

        <ul className="mt-4 ml-1 space-y-1 text-sm text-slate-600 list-disc list-inside">
          <li>Profile, KYC, and verification records</li>
          <li>Wallets, transactions, and passbook history</li>
          <li>Bank accounts, contacts, and package assignments</li>
          <li>BBPS and payment activity linked to this user</li>
        </ul>

        <p className="mt-4 text-sm font-medium text-red-700">This action cannot be undone.</p>

        <label htmlFor="delete-user-confirm" className="mt-4 block text-sm font-medium text-slate-700">
          Type <span className="font-mono font-semibold">{requiredToken}</span> to confirm
        </label>
        <input
          id="delete-user-confirm"
          type="text"
          value={confirmText}
          onChange={(e) => setConfirmText(e.target.value)}
          disabled={loading}
          className="mt-1.5 w-full rounded-xl border border-slate-200 px-4 py-2.5 text-sm font-mono focus:border-red-300 focus:ring-2 focus:ring-red-500/20 outline-none"
          placeholder={requiredToken}
          autoComplete="off"
        />

        <div className="mt-6 flex flex-col-reverse gap-3 sm:flex-row sm:justify-end">
          <Button type="button" variant="outline" size="lg" onClick={onCancel} disabled={loading}>
            Cancel
          </Button>
          <Button
            type="button"
            variant="danger"
            size="lg"
            loading={loading}
            disabled={!canConfirm}
            onClick={onConfirm}
          >
            Delete permanently
          </Button>
        </div>
      </div>
    </div>
  );
};

export default DeleteUserConfirmModal;
