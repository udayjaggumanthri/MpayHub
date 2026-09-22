import React, { useEffect } from 'react';
import { useNavigate } from 'react-router-dom';

/**
 * Fund-wallet (main→BBPS transfer) was removed in the single-wallet consolidation.
 * This route stays for bookmark/deep-link compatibility and redirects to the dashboard.
 */
const BbpsWalletFund = () => {
  const navigate = useNavigate();

  useEffect(() => {
    navigate('/dashboard', {
      replace: true,
      state: {
        infoMessage:
          'Main-to-BBPS wallet transfer was removed. Bill payments now use your main wallet.',
      },
    });
  }, [navigate]);

  return (
    <div className="mx-auto max-w-lg px-4 py-10">
      <p className="text-sm text-slate-600 dark:text-slate-400">
        Main-to-BBPS wallet transfer was removed. Redirecting to dashboard…
      </p>
    </div>
  );
};

export default BbpsWalletFund;
