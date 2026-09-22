import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { FaWallet } from 'react-icons/fa6';
import { FiEye, FiEyeOff, FiArrowRight } from 'react-icons/fi';
import { useWallet } from '../../context/WalletContext';
import { formatCurrency } from '../../utils/formatters';

/**
 * Channel Main Wallet.
 * @param {{ compact?: boolean }} props — compact when paired with Commission (MD/SD/Distributor).
 */
const MainWalletBalanceCard = ({ compact = false }) => {
  const navigate = useNavigate();
  const { wallets, heldBalance, availableBalance, loading } = useWallet();
  const [hidden, setHidden] = useState(false);
  const spendable =
    heldBalance > 0 && availableBalance != null ? availableBalance : wallets?.main ?? 0;
  const amount =
    loading && wallets?.main == null ? '—' : hidden ? '••••••' : formatCurrency(spendable);

  return (
    <article
      className={`group relative flex h-full flex-col justify-between overflow-hidden rounded-2xl border border-slate-200 bg-gradient-to-br from-white via-slate-50 to-blue-100/80 shadow-sm ring-1 ring-blue-200/60 transition-all duration-300 ease-out hover:shadow-lg hover:ring-blue-300/70 motion-safe:mpay-rise-in motion-safe:mpay-rise-in-delay-1 motion-safe:hover:-translate-y-1 dark:border-slate-600 dark:from-slate-900 dark:via-slate-900 dark:to-blue-950/70 dark:ring-blue-800/80 dark:hover:ring-blue-600/70 ${
        compact
          ? 'p-2.5 sm:p-3.5 lg:min-h-[120px]'
          : 'p-3 sm:p-5 lg:min-h-[132px]'
      }`}
    >
      <div
        className="mpay-wallet-orb pointer-events-none absolute -right-8 -top-8 h-28 w-28 rounded-full bg-gradient-to-br from-blue-400/30 via-sky-300/20 to-transparent blur-2xl dark:from-blue-500/25 dark:via-sky-500/10"
        aria-hidden
      />
      <span className="mpay-action-shine opacity-40" aria-hidden />

      <div className={`relative z-10 flex items-center ${compact ? 'gap-2 sm:gap-2.5' : 'gap-3'}`}>
        <div
          className={`inline-flex shrink-0 items-center justify-center rounded-xl bg-gradient-to-br from-blue-600 to-indigo-700 text-white shadow-md shadow-blue-600/25 transition duration-300 motion-safe:group-hover:rotate-3 motion-safe:group-hover:scale-110 ${
            compact ? 'h-9 w-9 sm:h-10 sm:w-10' : 'h-10 w-10 sm:h-11 sm:w-11'
          }`}
        >
          <FaWallet className={compact ? 'h-3.5 w-3.5 sm:h-4 sm:w-4' : 'h-4 w-4 sm:h-5 sm:w-5'} aria-hidden />
        </div>

        <div className="min-w-0 flex-1">
          <div className="flex items-center justify-between gap-1">
            <p className="text-[10px] font-bold uppercase tracking-wider text-slate-600 dark:text-slate-300">
              {compact ? 'Wallet' : 'Main Wallet'}
            </p>
            <div className="flex items-center gap-0.5">
              <button
                type="button"
                onClick={() => setHidden((v) => !v)}
                className="inline-flex h-7 w-7 items-center justify-center rounded-full text-slate-500 transition hover:bg-white hover:text-slate-700 dark:text-slate-400 dark:hover:bg-slate-800 dark:hover:text-slate-100"
                aria-label={hidden ? 'Show balance' : 'Hide balance'}
              >
                {hidden ? (
                  <FiEyeOff className="h-3.5 w-3.5" aria-hidden />
                ) : (
                  <FiEye className="h-3.5 w-3.5" aria-hidden />
                )}
              </button>
              {!compact ? (
                <button
                  type="button"
                  onClick={() => navigate('/reports/passbook')}
                  className="inline-flex items-center gap-0.5 rounded-full px-2 py-1 text-[10px] font-semibold text-blue-700 transition hover:bg-blue-50 dark:text-blue-300 dark:hover:bg-slate-800 sm:text-[11px]"
                >
                  Ledger
                  <FiArrowRight className="h-3 w-3" aria-hidden />
                </button>
              ) : (
                <button
                  type="button"
                  onClick={() => navigate('/reports/passbook')}
                  className="inline-flex h-7 w-7 items-center justify-center rounded-full text-blue-600 transition hover:bg-blue-50 dark:text-blue-300 dark:hover:bg-slate-800"
                  aria-label="View ledger"
                >
                  <FiArrowRight className="h-3.5 w-3.5" aria-hidden />
                </button>
              )}
            </div>
          </div>

          <p
            className={`mt-0.5 font-bold tabular-nums tracking-tight text-slate-950 dark:text-white ${
              compact ? 'text-base sm:text-lg' : 'text-xl sm:mt-1 sm:text-2xl'
            }`}
          >
            {amount}
          </p>
          <p className="mt-0.5 truncate text-[10px] font-medium text-slate-600 dark:text-slate-300 sm:text-[11px]">
            {heldBalance > 0 && !hidden
              ? `${formatCurrency(heldBalance)} held`
              : 'Available Balance'}
          </p>
        </div>
      </div>

      <div
        className="absolute bottom-0 left-0 right-0 h-0.5 bg-gradient-to-r from-blue-600 via-sky-500 to-indigo-600 sm:h-1"
        aria-hidden
      />
    </article>
  );
};

export default MainWalletBalanceCard;
