import React from 'react';
import { FaCircleCheck, FaLock, FaTriangleExclamation, FaUserSlash } from 'react-icons/fa6';
import Button from './Button';
import { ADMIN_ACCESS_ACTIONS } from '../../utils/accessControl';

const toneStyles = {
  danger: { icon: FaUserSlash, box: 'bg-red-50 text-red-700', button: 'danger' },
  warning: { icon: FaTriangleExclamation, box: 'bg-amber-50 text-amber-800', button: 'danger' },
  success: { icon: FaCircleCheck, box: 'bg-emerald-50 text-emerald-700', button: 'success' },
};

/**
 * Reusable admin confirm dialog for account access changes.
 * @param {{ actionKey: keyof ADMIN_ACCESS_ACTIONS, userName: string, loading?: boolean,
 *   allowPayInWhenDisabled?: boolean, onAllowPayInChange?: (v: boolean) => void,
 *   onConfirm: () => void, onCancel: () => void }} props
 */
const AccessControlConfirmModal = ({
  actionKey,
  userName,
  loading = false,
  allowPayInWhenDisabled = false,
  onAllowPayInChange,
  onConfirm,
  onCancel,
}) => {
  const config = ADMIN_ACCESS_ACTIONS[actionKey];
  if (!config) return null;

  const tone = toneStyles[config.tone] || toneStyles.warning;
  const Icon = tone.icon;

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/60 backdrop-blur-sm"
      role="dialog"
      aria-modal="true"
      aria-labelledby="access-confirm-title"
      onClick={() => !loading && onCancel()}
    >
      <div
        className="w-full max-w-md rounded-2xl bg-white p-6 shadow-2xl"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-start gap-4">
          <div className={`flex h-12 w-12 shrink-0 items-center justify-center rounded-xl ${tone.box}`}>
            <Icon size={22} aria-hidden />
          </div>
          <div className="min-w-0 flex-1">
            <h3 id="access-confirm-title" className="text-lg font-bold text-slate-900">
              {config.title}
            </h3>
            <p className="mt-1 text-sm font-medium text-slate-800">{userName}</p>
          </div>
        </div>

        <ul className="mt-4 space-y-2 rounded-xl border border-slate-100 bg-slate-50/80 px-4 py-3 text-sm text-slate-600">
          {config.bullets.map((line) => (
            <li key={line} className="flex gap-2">
              <span className="text-slate-400" aria-hidden>
                •
              </span>
              <span>{line}</span>
            </li>
          ))}
        </ul>

        {config.showPayInOption && onAllowPayInChange ? (
          <label className="mt-4 flex items-start gap-3 rounded-xl border border-amber-200 bg-amber-50/60 px-4 py-3 text-sm text-slate-800 cursor-pointer">
            <input
              type="checkbox"
              className="mt-0.5 h-4 w-4 rounded border-slate-300 text-indigo-600 focus:ring-indigo-500"
              checked={allowPayInWhenDisabled}
              onChange={(e) => onAllowPayInChange(e.target.checked)}
              disabled={loading}
            />
            <span>
              <span className="font-medium">Allow pay-in only</span>
              <span className="mt-0.5 block text-xs text-slate-600">
                User may sign in and load money; payout, BBPS, and other services stay off.
              </span>
            </span>
          </label>
        ) : null}

        <div className="mt-6 flex gap-3 justify-end">
          <Button onClick={onCancel} disabled={loading} variant="outline" size="lg">
            Cancel
          </Button>
          <Button
            onClick={onConfirm}
            loading={loading}
            variant={tone.button}
            size="lg"
            icon={config.tone === 'success' ? FaCircleCheck : config.showPayInOption ? FaUserSlash : FaLock}
            iconPosition="left"
          >
            {config.confirmLabel}
          </Button>
        </div>
      </div>
    </div>
  );
};

export default AccessControlConfirmModal;
