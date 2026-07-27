import React, { createContext, useState, useContext, useEffect, useCallback, useRef } from 'react';
import { authAPI, systemAPI } from '../services/api';
import { normalizeAuthUser } from '../utils/authUser';
import { DEFAULT_MAINTENANCE, normalizeMaintenance } from '../utils/maintenanceMode';
import { userMayLogin } from '../utils/userAccess';
import { parseLoginFailure } from '../utils/loginErrors';
import { SESSION_POST_MPIN_ANNOUNCE } from '../utils/announcements';
import SessionTimeoutModal from '../components/auth/SessionTimeoutModal';

const AuthContext = createContext();

const DEFAULT_IDLE_MINUTES = 5;
const IDLE_EVENTS = ['mousemove', 'mousedown', 'keydown', 'touchstart', 'scroll', 'click'];

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
  const [idleTimeoutMinutes, setIdleTimeoutMinutes] = useState(DEFAULT_IDLE_MINUTES);
  /** Mixpanel-style gate: keep UI frozen under modal until user clicks Login */
  const [sessionGate, setSessionGate] = useState(null);
  const idleTimerRef = useRef(null);
  const logoutRef = useRef(null);
  const sessionGateRef = useRef(null);
  const openSessionGateRef = useRef(null);

  const applyMaintenanceFromPayload = useCallback((payload) => {
    if (payload?.maintenance) {
      setMaintenance(normalizeMaintenance(payload.maintenance));
    }
  }, []);

  const clearIdleTimer = useCallback(() => {
    if (idleTimerRef.current) {
      clearTimeout(idleTimerRef.current);
      idleTimerRef.current = null;
    }
  }, []);

  const clearClientTokens = useCallback(() => {
    localStorage.removeItem('access_token');
    localStorage.removeItem('refresh_token');
  }, []);

  /** Soft-end session: revoke server session + clear tokens, keep UI for modal. */
  const openSessionGate = useCallback(
    async (code = 'SESSION_IDLE') => {
      if (sessionGateRef.current) return;
      sessionGateRef.current = code;
      setSessionGate(code);
      clearIdleTimer();
      try {
        await authAPI.logout();
      } catch {
        /* ignore — tokens may already be invalid */
      }
      clearClientTokens();
    },
    [clearIdleTimer, clearClientTokens]
  );

  openSessionGateRef.current = openSessionGate;

  // Bridge for API interceptor (401 session-end → same modal)
  useEffect(() => {
    window.__mpayhubOpenSessionGate = (code) => {
      openSessionGateRef.current?.(code || 'SESSION_INVALID');
    };
    return () => {
      if (window.__mpayhubOpenSessionGate) {
        delete window.__mpayhubOpenSessionGate;
      }
    };
  }, []);

  const acknowledgeSessionGate = useCallback(() => {
    sessionGateRef.current = null;
    setSessionGate(null);
    sessionStorage.removeItem(SESSION_POST_MPIN_ANNOUNCE);
    sessionStorage.removeItem('mpayhub_user');
    sessionStorage.removeItem('mpayhub_mpin_verified');
    clearClientTokens();
    setUser(null);
    setMaintenance(DEFAULT_MAINTENANCE);
    setIsAuthenticated(false);
    setMpinVerified(false);
    window.location.href = '/login';
  }, [clearClientTokens]);

  const resetIdleTimer = useCallback(() => {
    clearIdleTimer();
    if (!isAuthenticated || sessionGateRef.current) return;
    const ms = Math.max(1, Number(idleTimeoutMinutes) || DEFAULT_IDLE_MINUTES) * 60 * 1000;
    idleTimerRef.current = setTimeout(() => {
      if (openSessionGateRef.current) {
        openSessionGateRef.current('SESSION_IDLE');
      }
    }, ms);
  }, [clearIdleTimer, idleTimeoutMinutes, isAuthenticated]);

  const loadSessionPolicy = useCallback(async () => {
    try {
      const result = await authAPI.getSessionPolicy();
      if (result.success && result.data?.idle_timeout_minutes) {
        setIdleTimeoutMinutes(Number(result.data.idle_timeout_minutes) || DEFAULT_IDLE_MINUTES);
      }
    } catch {
      /* keep default */
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
              await loadSessionPolicy();
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
  }, [applyMaintenanceFromPayload, loadSessionPolicy]);

  // Idle activity listeners (paused while session gate modal is open)
  useEffect(() => {
    if (!isAuthenticated || sessionGate) {
      clearIdleTimer();
      return undefined;
    }
    resetIdleTimer();
    const onActivity = () => resetIdleTimer();
    IDLE_EVENTS.forEach((evt) => window.addEventListener(evt, onActivity, { passive: true }));
    const onVisibility = () => {
      if (document.visibilityState === 'visible') resetIdleTimer();
    };
    document.addEventListener('visibilitychange', onVisibility);
    return () => {
      IDLE_EVENTS.forEach((evt) => window.removeEventListener(evt, onActivity));
      document.removeEventListener('visibilitychange', onVisibility);
      clearIdleTimer();
    };
  }, [isAuthenticated, sessionGate, resetIdleTimer, clearIdleTimer]);

  // Login function (optional clientContext: browser geo + device facts)
  const login = async (phone, password, clientContext = null) => {
    try {
      const result = await authAPI.login(phone, password, clientContext);
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
        await loadSessionPolicy();
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
  const logout = useCallback(async () => {
    clearIdleTimer();
    sessionGateRef.current = null;
    setSessionGate(null);
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
  }, [clearIdleTimer]);

  logoutRef.current = logout;

  const value = {
    user,
    maintenance,
    isAuthenticated,
    mpinVerified,
    loading,
    idleTimeoutMinutes,
    sessionGate,
    login,
    verifyMPIN,
    refreshUser,
    refreshMaintenance,
    markMpinSessionVerified,
    logout,
    openSessionGate,
    acknowledgeSessionGate,
  };

  return (
    <AuthContext.Provider value={value}>
      {children}
      {sessionGate ? (
        <SessionTimeoutModal code={sessionGate} onLogin={acknowledgeSessionGate} />
      ) : null}
    </AuthContext.Provider>
  );
};
