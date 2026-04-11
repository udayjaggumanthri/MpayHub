import React, { useEffect } from 'react';
import { FiX } from 'react-icons/fi';
import Button from './Button';

/**
 * In-app message dialog (replaces window.alert for clearer UX).
 */
const FeedbackModal = ({
  open,
  onClose,
  title,
  description,
  /** If set, shown as main button; its onClick runs then modal closes. */
  primaryAction,
  /** Optional second button (default label: Close). Only used when primaryAction is set. */
  secondaryLabel = 'Close',
}) => {
  useEffect(() => {
    if (!open) return undefined;
    const onKey = (e) => {
      if (e.key === 'Escape') onClose();
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [open, onClose]);

  if (!open) return null;

  return (
    <div
      className="fixed inset-0 z-[60] flex items-center justify-center p-4 bg-black/50"
      role="presentation"
      onClick={onClose}
    >
      <div
        className="relative w-full max-w-md rounded-2xl bg-white p-6 shadow-2xl ring-1 ring-black/5"
        role="dialog"
        aria-modal="true"
        aria-labelledby="feedback-modal-title"
        onClick={(e) => e.stopPropagation()}
      >
        <button
          type="button"
          onClick={onClose}
          className="absolute right-4 top-4 rounded-lg p-1 text-gray-400 transition-colors hover:bg-gray-100 hover:text-gray-600"
          aria-label="Close"
        >
          <FiX size={22} />
        </button>

        <h2 id="feedback-modal-title" className="pr-10 text-xl font-bold text-gray-900">
          {title}
        </h2>
        <p className="mt-3 whitespace-pre-line text-sm leading-relaxed text-gray-600">{description}</p>

        <div className="mt-6 flex flex-col-reverse gap-3 sm:flex-row sm:justify-end">
          {primaryAction ? (
            <>
              <Button type="button" variant="outline" size="lg" onClick={onClose} className="sm:w-auto">
                {secondaryLabel}
              </Button>
              <Button
                type="button"
                variant="primary"
                size="lg"
                className="sm:w-auto"
                onClick={() => {
                  primaryAction.onClick?.();
                  onClose();
                }}
              >
                {primaryAction.label}
              </Button>
            </>
          ) : (
            <Button type="button" variant="primary" size="lg" onClick={onClose} className="w-full sm:w-auto sm:min-w-[120px]">
              OK
            </Button>
          )}
        </div>
      </div>
    </div>
  );
};

export default FeedbackModal;
