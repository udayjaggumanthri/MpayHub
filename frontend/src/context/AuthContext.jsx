import React, { createContext, useState, useContext, useEffect, useCallback } from 'react';
import { authAPI, systemAPI } from '../services/api';
import { normalizeAuthUser } from '../utils/authUser';
import { DEFAULT_MAINTENANCE, normalizeMaintenance } from '../utils/maintenanceMode';
import { userMayLogin } from '../utils/userAccess';
import { parseLoginFailure } from '../utils/loginErrors';
import { SESSION_POST_MPIN_ANNOUNCE } from '../utils/announcements';

const AuthContext = createContext();

export const useAuth = () => {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
};

export const AuthProvider = ({ children }) => {
  const [user, setUser] = useState(null);
  const [maintenance, setMaintenance] = useState(DEFAULT_MAINTENANCE);
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [mpinVerified, setMpinVerified] = useState(false);
  const [loading, setLoading] = useState(true);

  const applyMaintenanceFromPayload = useCallback((payload) => {
    if (payload?.maintenance) {
      setMaintenance(normalizeMaintenance(payload.maintenance));
    }
  }, []);

  // Check for existing session on mount
  useEffect(() => {
    const checkSession = async () => {
      const storedUser = sessionStorage.getItem('mpayhub_user');
      const storedMpinVerified = sessionStorage.getItem('mpayhub_mpin_verified');
      const accessToken = localStorage.getItem('access_token');

      if (storedUser && accessToken) {
        try {
          try {
            setUser(normalizeAuthUser(JSON.parse(storedUser)));
          } catch {
            /* ignore bad cache */
          }
          // Verify token is still valid by fetching current user
          const result = await authAPI.getCurrentUser();
          if (result.success && result.data?.user) {
            const u = normalizeAuthUser(result.data.user);
            applyMaintenanceFromPayload(result.data);
            if (u && !userMayLogin(u)) {
              await authAPI.logout();
              setUser(null);
              setMaintenance(DEFAULT_MAINTENANCE);
              setIsAuthenticated(false);
              setMpinVerified(false);
            } else {
              setUser(u);
              sessionStorage.setItem('mpayhub_user', JSON.stringify(u));
              setIsAuthenticated(true);
              setMpinVerified(storedMpinVerified === 'true');
            }
          } else {
            // Token invalid, clear session
            authAPI.logout();
          }
        } catch (error) {
          // Token invalid, clear session
          authAPI.logout();
        }
      }
      setLoading(false);
    };

    checkSession();
  }, []);

  // Login function
  const login = async (phone, password) => {
    try {
      const result = await authAPI.login(phone, password);
      if (result.success && result.data?.user) {
        const u = normalizeAuthUser(result.data.user);
        if (u && !userMayLogin(u)) {
          const disabled = parseLoginFailure({
            success: false,
            errorCode: 'USER_DISABLED',
          });
          return {
            success: false,
            message: disabled?.message || 'Your account is disabled. Contact your administrator.',
            errorTitle: disabled?.title,
            errorVariant: disabled?.variant || 'disabled',
            errors: [],
          };
        }
        setUser(u);
        applyMaintenanceFromPayload(result.data);
        sessionStorage.setItem('mpayhub_user', JSON.stringify(u));
        setIsAuthenticated(true);
        setMpinVerified(false); // Session MPIN gate after account is fully ready
        sessionStorage.removeItem('mpayhub_mpin_verified');
        sessionStorage.removeItem(SESSION_POST_MPIN_ANNOUNCE);
        return { success: true, user: u };
      }
      const parsed = parseLoginFailure({ success: false, ...result });
      return {
        success: false,
        message: parsed?.message || 'Login failed',
        errorTitle: parsed?.title,
        errorVariant: parsed?.variant,
        errors: result.errors,
      };
    } catch (error) {
      return {
        success: false,
        message: 'An error occurred during login',
        errors: [],
      };
    }
  };

  // Verify MPIN
  const verifyMPIN = async (mpin) => {
    if (!user) {
      return {
        success: false,
        message: 'User not logged in',
        errors: [],
      };
    }

    try {
      const result = await authAPI.verifyMPIN(mpin);
      if (result.success) {
        setMpinVerified(true);
        return { success: true };
      }
      const errs = Array.isArray(result.errors) ? result.errors : [];
      const message =
        errs.length > 0 ? errs[0] : result.message || 'MPIN verification failed';
      return {
        success: false,
        message,
        errors: errs,
      };
    } catch (error) {
      return {
        success: false,
        message: 'An error occurred during MPIN verification',
        errors: [],
      };
    }
  };

  const refreshUser = useCallback(async () => {
    try {
      const result = await authAPI.getCurrentUser();
      if (result.success && result.data?.user) {
        const u = normalizeAuthUser(result.data.user);
        if (u && !userMayLogin(u)) {
          await authAPI.logout();
          setUser(null);
          setIsAuthenticated(false);
          setMpinVerified(false);
          return null;
        }
        setUser(u);
        applyMaintenanceFromPayload(result.data);
        sessionStorage.setItem('mpayhub_user', JSON.stringify(u));
        return u;
      }
    } catch {
      /* ignore */
    }
    return null;
  }, [applyMaintenanceFromPayload]);

  const refreshMaintenance = useCallback(async () => {
    try {
      const result = await systemAPI.getMaintenanceStatus();
      if (result.success && result.data?.maintenance) {
        setMaintenance(normalizeMaintenance(result.data.maintenance));
      }
    } catch {
      /* ignore */
    }
  }, []);

  const markMpinSessionVerified = () => {
    setMpinVerified(true);
    sessionStorage.setItem('mpayhub_mpin_verified', 'true');
  };

  // Logout function
  const logout = async () => {
    try {
      await authAPI.logout();
    } catch (error) {
      console.error('Logout error:', error);
    } finally {
      sessionStorage.removeItem(SESSION_POST_MPIN_ANNOUNCE);
      setUser(null);
      setMaintenance(DEFAULT_MAINTENANCE);
      setIsAuthenticated(false);
      setMpinVerified(false);
    }
  };

  const value = {
    user,
    maintenance,
    isAuthenticated,
    mpinVerified,
    loading,
    login,
    verifyMPIN,
    refreshUser,
    refreshMaintenance,
    markMpinSessionVerified,
    logout,
  };

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
};
