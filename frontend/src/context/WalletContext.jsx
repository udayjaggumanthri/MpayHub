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
    loading,
    error,
    loadWallets,
    updateWallets,
    refreshWallets,
  };

  return <WalletContext.Provider value={value}>{children}</WalletContext.Provider>;
};
