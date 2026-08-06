import React, { createContext, useContext, useState, useEffect, useCallback } from 'react';
import { useAuth } from './AuthContext';
import { walletsAPI } from '../services/api';

const WalletContext = createContext();

export const useWallet = () => {
  const context = useContext(WalletContext);
  if (!context) {
    throw new Error('useWallet must be used within a WalletProvider');
  }
  return context;
};

export const WalletProvider = ({ children }) => {
  const { user } = useAuth();
  const [wallets, setWallets] = useState({
    main: 0,
    commission: 0,
    bbps: 0,
    profit: 0,
  });
  const [walletMeta, setWalletMeta] = useState({
    main: {},
    commission: {},
    bbps: {},
    profit: {},
  });
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const loadWallets = useCallback(async () => {
    if (!user) return;

    setLoading(true);
    setError(null);
    try {
      const result = await walletsAPI.getAllWallets();
      if (result.success && result.data?.wallets) {
        // Backend returns: { wallets: { main: {balance: ...}, commission: {...}, bbps: {...} } }
        // Transform to frontend format
        const walletData = result.data.wallets;
        setWallets({
          main: parseFloat(walletData.main?.balance || walletData.main || 0) || 0,
          commission: parseFloat(walletData.commission?.balance || walletData.commission || 0) || 0,
          bbps: parseFloat(walletData.bbps?.balance || walletData.bbps || 0) || 0,
          profit: parseFloat(walletData.profit?.balance || walletData.profit || 0) || 0,
        });
        setWalletMeta({
          main: {
            source: walletData.main?.source || null,
            networkUserCount: walletData.main?.network_user_count ?? null,
          },
          commission: {
            source: walletData.commission?.source || null,
            networkUserCount: walletData.commission?.network_user_count ?? null,
          },
          bbps: {
            source: walletData.bbps?.source || null,
            networkUserCount: walletData.bbps?.network_user_count ?? null,
          },
          profit: {
            source: walletData.profit?.source || null,
            networkUserCount: walletData.profit?.network_user_count ?? null,
          },
        });
      } else {
        setError(result.message || 'Failed to load wallets');
      }
    } catch (error) {
      console.error('Error loading wallets:', error);
      setError('An error occurred while loading wallets');
    } finally {
      setLoading(false);
    }
  }, [user]);

  useEffect(() => {
    if (user) {
      loadWallets();
    }
  }, [user, loadWallets]);

  const updateWallets = (newWallets) => {
    setWallets(newWallets);
  };

  const refreshWallets = useCallback(() => {
    loadWallets();
  }, [loadWallets]);

  const value = {
    wallets,
    walletMeta,
    loading,
    error,
    loadWallets,
    updateWallets,
    refreshWallets,
  };

  return <WalletContext.Provider value={value}>{children}</WalletContext.Provider>;
};
