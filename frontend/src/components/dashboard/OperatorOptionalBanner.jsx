import React, { useCallback, useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';

const SKIP_PREFIX = 'mpayhub.operatorOptionalBanner.skip.v1';
const LATER_PREFIX = 'mpayhub.operatorOptionalBanner.later.v1';

function storageKey(prefix, userId, kind) {
  return `${prefix}.${userId || 'anon'}.${kind}`;
}

function readSkip(userId, kind) {
  try {
    return localStorage.getItem(storageKey(SKIP_PREFIX, userId, kind)) === '1';
  } catch {
    return false;
  }
}

function readLater(userId, kind) {
  try {
    return sessionStorage.getItem(storageKey(LATER_PREFIX, userId, kind)) === '1';
  } catch {
    return false;
  }
}

/**
 * Optional KYC/MPIN notice for Admin / Super Admin.
 * Skip = never show again on dashboard (Profile still available).
 * Remember later = hide for this browser session only.
 */
const OperatorOptionalBanner = ({ user }) => {
  const navigate = useNavigate();
  const userId = user?.id ?? user?.user_id ?? 'anon';
  const onboarding = user?.onboarding || {};

  const kind = useMemo(() => {
    if (onboarding.kyc_optional && !onboarding.kyc_complete) return 'kyc_mpin';
    if (
      onboarding.mpin_optional &&
      onboarding.kyc_optional &&
      onboarding.kyc_complete &&
      !onboarding.mpin_set
    ) {
      return 'mpin';
    }
    return null;
  }, [onboarding]);

  const [hidden, setHidden] = useState(false);

  const dismissed = useMemo(() => {
    if (!kind) return true;
    return readSkip(userId, kind) || readLater(userId, kind);
  }, [userId, kind]);

  const onSkip = useCallback(() => {
    try {
      localStorage.setItem(storageKey(SKIP_PREFIX, userId, kind), '1');
      sessionStorage.removeItem(storageKey(LATER_PREFIX, userId, kind));
    } catch {
      /* ignore */
    }
    setHidden(true);
  }, [userId, kind]);

  const onRememberLater = useCallback(() => {
    try {
      sessionStorage.setItem(storageKey(LATER_PREFIX, userId, kind), '1');
    } catch {
      /* ignore */
    }
    setHidden(true);
  }, [userId, kind]);

  if (!kind || dismissed || hidden) return null;

  const copy =
    kind === 'mpin'
      ? 'MPIN is optional for your role. Set or reset it anytime from Profile if you want an extra login step later.'
      : 'KYC and MPIN are optional for your role. You can use the admin portal now and complete them later from Profile if you want — they are never required.';

  return (
    <div className="flex flex-col gap-3 rounded-lg border border-indigo-200 bg-indigo-50 px-4 py-3 text-sm text-indigo-900 dark:border-indigo-900/40 dark:bg-indigo-950/30 dark:text-indigo-100 sm:flex-row sm:items-center sm:justify-between">
      <p className="min-w-0 flex-1 leading-relaxed">{copy}</p>
      <div className="flex shrink-0 flex-wrap items-center gap-2">
        <button
          type="button"
          onClick={() => navigate('/profile')}
          className="rounded-lg border border-indigo-300 bg-white px-3 py-1.5 text-xs font-semibold text-indigo-800 hover:bg-indigo-100 dark:border-indigo-700 dark:bg-slate-900 dark:text-indigo-200 dark:hover:bg-indigo-950/60"
        >
          Open Profile
        </button>
        <button
          type="button"
          onClick={onRememberLater}
          className="rounded-lg border border-indigo-200 bg-indigo-100/80 px-3 py-1.5 text-xs font-semibold text-indigo-800 hover:bg-indigo-200/80 dark:border-indigo-800 dark:bg-indigo-900/40 dark:text-indigo-200"
        >
          Remember later
        </button>
        <button
          type="button"
          onClick={onSkip}
          className="rounded-lg bg-indigo-600 px-3 py-1.5 text-xs font-semibold text-white hover:bg-indigo-700"
        >
          Skip
        </button>
      </div>
    </div>
  );
};

export default OperatorOptionalBanner;
