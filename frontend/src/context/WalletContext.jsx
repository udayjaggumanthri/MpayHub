import React, { createContext, useContext, useState, useEffect, useCallback, useRef } from 'react';
import { useAuth } from './AuthContext';
import { walletsAPI, reportsAPI } from '../services/api';
import { canViewCommissionWallet } from '../utils/rolePermissions';

const WalletContext = createContext();

export const useWallet = () => {
  const context = useContext(WalletContext);
  if (!context) {
    throw new Error('useWallet must be used within a WalletProvider');
  }
  return context;
};

const emptyMeta = () => ({
  main: {},
  distributed: {},
  commission: {},
  bbps: {},
  profit: {},
});

function isoDate(d) {
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, '0');
  const day = String(d.getDate()).padStart(2, '0');
  return `${y}-${m}-${day}`;
}

export function periodDateRange(period) {
  const today = new Date();
  today.setHours(12, 0, 0, 0);
  const to = isoDate(today);
  if (period === 'month') {
    const from = new Date(today.getFullYear(), today.getMonth(), 1);
    return { date_from: isoDate(from), date_to: to };
  }
  if (period === 'year') {
    const from = new Date(today.getFullYear(), 0, 1);
    return { date_from: isoDate(from), date_to: to };
  }
  return { date_from: to, date_to: to };
}

export const PERIOD_LABELS = {
  day: 'Today',
  month: 'This month',
  year: 'This year',
};

export const WalletProvider = ({ children }) => {
  const { user } = useAuth();
  const [wallets, setWallets] = useState({
    main: 0,
    distributed: 0,
    earnings: 0,
    commission: 0,
    bbps: 0,
    profit: 0,
  });
  const [walletMeta, setWalletMeta] = useState(emptyMeta());
  const [heldBalance, setHeldBalance] = useState(0);
  const [availableBalance, setAvailableBalance] = useState(0);
  const [loading, setLoading] = useState(true);
  const [earningsRefreshing, setEarningsRefreshing] = useState(false);
  const [earningsPeriod, setEarningsPeriod] = useState('day');
  const earningsPeriodRef = useRef('day');
  const [error, setError] = useState(null);

  const fetchEarningsTotal = useCallback(async (period) => {
    if (!canViewCommissionWallet(user?.role)) return 0;
    const range = periodDateRange(period);
    const rev = await reportsAPI.getRevenueSummary({
      ...range,
      interval: period === 'day' ? 'day' : period === 'month' ? 'month' : 'year',
    });
    if (rev?.success && rev.data) {
      return parseFloat(rev.data.total_earned || 0) || 0;
    }
    return 0;
  }, [user?.role]);

  const loadWallets = useCallback(async (opts = {}) => {
    if (!user) return;
    const soft = Boolean(opts.soft);
    const skipEarnings = Boolean(opts.skipEarnings);

    if (!soft) {
      setLoading(true);
      setError(null);
    }
    try {
      const result = await walletsAPI.getAllWallets();
      let earningsTotal = null;
      if (!skipEarnings) {
        try {
          earningsTotal = await fetchEarningsTotal(earningsPeriodRef.current);
        } catch {
          /* optional */
        }
      }
      if (result.success && result.data?.wallets) {
        const walletData = result.data.wallets;
        const main = walletData.main || {};
        const mainBalance = parseFloat(main.balance ?? main ?? 0) || 0;
        const held = parseFloat(main.held_balance ?? 0) || 0;
        const available =
          main.available_balance != null
            ? parseFloat(main.available_balance) || 0
            : Math.max(0, mainBalance - held);

        const distributed = walletData.distributed || {};
        const distributedBalance =
          parseFloat(distributed.balance ?? distributed ?? 0) || 0;

        setWallets((prev) => ({
          main: mainBalance,
          distributed: distributedBalance,
          earnings: earningsTotal != null ? earningsTotal : prev.earnings,
          commission: 0,
          bbps: 0,
          profit: 0,
        }));
        setHeldBalance(held);
        setAvailableBalance(available);
        setWalletMeta({
          main: {
            source: main.source || null,
            networkUserCount: main.network_user_count ?? null,
            heldBalance: held,
            availableBalance: available,
          },
          distributed: {
            source: distributed.source || null,
            networkUserCount: distributed.network_user_count ?? null,
          },
          commission: {},
          bbps: {},
          profit: {},
        });
      } else if (!soft) {
        setError(result.message || 'Failed to load wallets');
      }
    } catch (err) {
      console.error('Error loading wallets:', err);
      if (!soft) setError('An error occurred while loading wallets');
    } finally {
      if (!soft) setLoading(false);
    }
  }, [user, fetchEarningsTotal]);

  useEffect(() => {
    if (user) {
      loadWallets();
    }
  }, [user, loadWallets]);

  const changeEarningsPeriod = useCallback(
    async (period) => {
      if (!period || period === earningsPeriodRef.current) return;
      earningsPeriodRef.current = period;
      setEarningsPeriod(period);
      setEarningsRefreshing(true);
      try {
        const total = await fetchEarningsTotal(period);
        setWallets((prev) => ({ ...prev, earnings: total }));
      } catch {
        /* keep prior amount */
      } finally {
        setEarningsRefreshing(false);
      }
    },
    [fetchEarningsTotal]
  );

  const updateWallets = (newWallets) => {
    setWallets(newWallets);
  };

  const refreshWallets = useCallback(() => {
    loadWallets({ soft: true, skipEarnings: true });
  }, [loadWallets]);

  const value = {
    wallets,
    walletMeta,
    heldBalance,
    availableBalance,
    loading,
    earningsRefreshing,
    earningsPeriod,
    changeEarningsPeriod,
    error,
    loadWallets,
    updateWallets,
    refreshWallets,
  };

  return <WalletContext.Provider value={value}>{children}</WalletContext.Provider>;
};
