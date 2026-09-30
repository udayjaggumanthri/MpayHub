import React, { useEffect } from 'react';
import { createPortal } from 'react-dom';
import Button from './Button';
import { formatCurrency } from '../../utils/formatters';

/**
 * Content-scoped payment status modal (keeps header + sidebar usable).
 * phase: 'processing' | 'success' | 'pending' | 'failed'
 */
const PaymentFlowOverlay = ({
  open,
  phase = 'processing',
  kind = 'payout',
  amount,
  subtitle,
  reference,
  details = [],
  primaryAction,
  secondaryAction,
  onClose,
  secondaryLabel = 'Done',
}) => {
  useEffect(() => {
    if (!open || phase === 'processing') return undefined;
    const onKey = (e) => {
      if (e.key === 'Escape') onClose?.();
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [open, phase, onClose]);

  if (!open || typeof document === 'undefined') return null;

  const isProcessing = phase === 'processing';
  const isSuccess = phase === 'success';
  const isPending = phase === 'pending';
  const isFailed = phase === 'failed';

  const kindLabel = kind === 'payin' ? 'Pay In' : 'Pay Out';
  const title = isProcessing
    ? `Processing ${kindLabel.toLowerCase()}…`
    : isSuccess
      ? `${kindLabel} successful`
      : isPending
        ? `${kindLabel} in progress`
        : `${kindLabel} failed`;

  const toneClass = isSuccess
    ? 'payflow-tone-success'
    : isPending
      ? 'payflow-tone-pending'
      : isFailed
        ? 'payflow-tone-failed'
        : 'payflow-tone-processing';

  return createPortal(
    <div
      className={`payflow-shell ${toneClass}`}
      role="dialog"
      aria-modal="true"
      aria-live="polite"
      aria-busy={isProcessing}
      aria-labelledby="payflow-title"
    >
      <button
        type="button"
        className="payflow-backdrop"
        aria-label="Close"
        disabled={isProcessing}
        onClick={() => {
          if (!isProcessing) onClose?.();
        }}
      />

      <div className="payflow-panel-wrap">
        <div className="payflow-panel">
          <div className="payflow-panel-scroll">
            <div className="payflow-stage">
              {(isProcessing || isPending) && (
                <>
                  <span className="payflow-ring payflow-ring-1" />
                  <span className="payflow-ring payflow-ring-2" />
                </>
              )}
              <div className="payflow-core">
                {isProcessing && (
                  <div className="payflow-rupee" aria-hidden>
                    ₹
                  </div>
                )}
                {isPending && (
                  <svg className="payflow-icon" viewBox="0 0 64 64" aria-hidden>
                    <circle cx="32" cy="32" r="26" className="payflow-icon-track" />
                    <path
                      className="payflow-pending-arc"
                      d="M32 10a22 22 0 0 1 22 22"
                      fill="none"
                      strokeWidth="4"
                      strokeLinecap="round"
                    />
                  </svg>
                )}
                {isSuccess && (
                  <svg className="payflow-icon" viewBox="0 0 64 64" aria-hidden>
                    <circle className="payflow-success-circle" cx="32" cy="32" r="28" />
                    <path className="payflow-success-check" d="M18 33.5 27.5 43 46 22" />
                  </svg>
                )}
                {isFailed && (
                  <svg className="payflow-icon payflow-fail-pop" viewBox="0 0 64 64" aria-hidden>
                    <circle className="payflow-fail-circle" cx="32" cy="32" r="28" />
                    <path className="payflow-fail-x" d="M22 22 42 42M42 22 22 42" />
                  </svg>
                )}
              </div>
            </div>

            {amount != null && !Number.isNaN(Number(amount)) ? (
              <p className="payflow-amount">{formatCurrency(Number(amount))}</p>
            ) : null}

            <h2 id="payflow-title" className="payflow-title">
              {title}
            </h2>

            {subtitle ? <p className="payflow-subtitle">{subtitle}</p> : null}

            {isProcessing ? (
              <div className="payflow-dots" aria-hidden>
                <span />
                <span />
                <span />
              </div>
            ) : null}

            {!isProcessing && (details?.length > 0 || reference) ? (
              <div className="payflow-card">
                {reference ? (
                  <div className="payflow-row">
                    <span>Reference</span>
                    <span className="payflow-mono">{reference}</span>
                  </div>
                ) : null}
                {(details || []).map((row) =>
                  row?.label ? (
                    <div key={row.label} className="payflow-row">
                      <span>{row.label}</span>
                      <span className="payflow-value">{row.value}</span>
                    </div>
                  ) : null
                )}
              </div>
            ) : null}
          </div>

          {!isProcessing ? (
            <div className="payflow-actions">
              <Button type="button" variant="outline" size="lg" className="w-full sm:flex-1" onClick={onClose}>
                {secondaryLabel}
              </Button>
              {secondaryAction ? (
                <Button
                  type="button"
                  variant="outline"
                  size="lg"
                  className="w-full sm:flex-1"
                  onClick={() => {
                    secondaryAction.onClick?.();
                    onClose?.();
                  }}
                >
                  {secondaryAction.label}
                </Button>
              ) : null}
              {primaryAction ? (
                <Button
                  type="button"
                  variant="primary"
                  size="lg"
                  className="w-full sm:flex-1"
                  onClick={() => {
                    primaryAction.onClick?.();
                    onClose?.();
                  }}
                >
                  {primaryAction.label}
                </Button>
              ) : null}
            </div>
          ) : null}
        </div>
      </div>
    </div>,
    document.body
  );
};

export default PaymentFlowOverlay;
