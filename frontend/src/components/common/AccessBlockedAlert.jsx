import React, { useEffect, useState } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { FaCircleExclamation } from 'react-icons/fa6';

/**
 * Shown only on the page the user was redirected to after a blocked route attempt.
 * Does not follow navigation to other modules (e.g. pay-in after a payout block).
 * End-user wording is intentional: does not expose restriction/lock reasons.
 */
const ACCESS_BLOCKED_USER_MESSAGE =
  'Technical Error: Something went wrong, please contact us if the problem persists.';

const AccessBlockedAlert = () => {
  const location = useLocation();
  const navigate = useNavigate();
  const [alert, setAlert] = useState(null);

  useEffect(() => {
    if (location.state?.accessBlocked) {
      setAlert({
        message: ACCESS_BLOCKED_USER_MESSAGE,
        showOnPath: location.pathname,
      });
      navigate(location.pathname, { replace: true, state: {} });
    }
  }, [location.state, location.pathname, navigate]);

  useEffect(() => {
    if (alert && location.pathname !== alert.showOnPath) {
      setAlert(null);
    }
  }, [location.pathname, alert]);

  if (!alert || location.pathname !== alert.showOnPath) return null;

  return (
    <div
      className="mb-4 rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-950"
      role="alert"
    >
      <div className="flex gap-3">
        <FaCircleExclamation className="mt-0.5 shrink-0 text-amber-700" size={18} aria-hidden />
        <div className="min-w-0 flex-1">
          <p className="font-semibold leading-relaxed">{alert.message}</p>
          <button
            type="button"
            className="mt-2 text-[12px] font-semibold text-amber-900 underline underline-offset-2"
            onClick={() => setAlert(null)}
          >
            Dismiss
          </button>
        </div>
      </div>
    </div>
  );
};

export default AccessBlockedAlert;
