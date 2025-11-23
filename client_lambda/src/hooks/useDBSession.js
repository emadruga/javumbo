import { useState, useCallback, useEffect, useRef } from 'react';
import axios from '../api/axiosConfig';

/**
 * useDBSession Hook
 *
 * Manages Lambda session lifecycle with:
 * - Automatic session creation
 * - Activity-based TTL refresh (reset on every API call)
 * - sessionStorage persistence (survives page refresh, dies on tab close)
 * - Retry logic for session start failures
 * - Manual flush control
 *
 * CRITICAL DESIGN DECISIONS:
 * 1. Session ID stored in sessionStorage (not localStorage) - dies when tab closes
 * 2. Idle timer resets on EVERY API call (via recordActivity)
 * 3. Exponential backoff retry for session start (max 3 attempts)
 * 4. beforeunload event warns user if active session exists
 */
export const useDBSession = () => {
  const [sessionId, setSessionId] = useState(() => {
    // Try to resume session from sessionStorage on mount
    return sessionStorage.getItem('db_session_id');
  });
  const [isActive, setIsActive] = useState(!!sessionId);
  const [error, setError] = useState(null);

  // Track if component is mounted (prevent state updates after unmount)
  const isMountedRef = useRef(true);

  // Track idle timeout ID (so we can clear/reset it)
  const idleTimeoutRef = useRef(null);

  // Track last activity timestamp
  const lastActivityRef = useRef(Date.now());

  /**
   * Record activity (called by API interceptor or manually)
   * Resets idle timer to 5 minutes from NOW
   */
  const recordActivity = useCallback(() => {
    lastActivityRef.current = Date.now();

    // Clear existing timeout
    if (idleTimeoutRef.current) {
      clearTimeout(idleTimeoutRef.current);
    }

    // Set new timeout (5 minutes from now)
    if (isActive) {
      idleTimeoutRef.current = setTimeout(() => {
        console.log('[useDBSession] Session idle timeout (5min), auto-flushing...');
        endSession();
      }, 5 * 60 * 1000); // 5 minutes
    }
  }, [isActive]);

  /**
   * Start a new session
   * Returns session_id on success, null on failure
   */
  const startSession = useCallback(async (retryCount = 0) => {
    const MAX_RETRIES = 3;

    try {
      setError(null);
      const token = localStorage.getItem('jwt_token');

      if (!token) {
        throw new Error('No JWT token found, please login');
      }

      const response = await axios.post('/api/session/start');

      const newSessionId = response.data.session_id;

      if (!isMountedRef.current) return null;

      // Store in sessionStorage (dies when tab closes)
      sessionStorage.setItem('db_session_id', newSessionId);
      setSessionId(newSessionId);
      setIsActive(true);

      console.log(`[useDBSession] ✓ Session started: ${newSessionId}`);

      // Start idle timer
      recordActivity();

      return newSessionId;

    } catch (err) {
      console.error('[useDBSession] Failed to start session:', err);

      if (!isMountedRef.current) return null;

      // Retry with exponential backoff
      if (retryCount < MAX_RETRIES) {
        const delay = Math.pow(2, retryCount) * 1000; // 1s, 2s, 4s
        console.log(`[useDBSession] Retrying in ${delay}ms (attempt ${retryCount + 1}/${MAX_RETRIES})`);

        await new Promise(resolve => setTimeout(resolve, delay));
        return startSession(retryCount + 1);
      }

      // Max retries exceeded
      setError(err.response?.data?.error || err.message);
      return null;
    }
  }, [recordActivity]);

  /**
   * End session and flush to S3
   */
  const endSession = useCallback(async () => {
    if (!sessionId) {
      console.log('[useDBSession] No active session to end');
      return;
    }

    try {
      const token = localStorage.getItem('jwt_token');

      if (!token) {
        console.warn('[useDBSession] No JWT token, cannot flush session');
        return;
      }

      console.log(`[useDBSession] Flushing session ${sessionId} to S3...`);

      await axios.post('/api/session/flush', { session_id: sessionId });

      console.log('[useDBSession] ✓ Session flushed and ended');

    } catch (err) {
      console.error('[useDBSession] Failed to flush session:', err);
      // Don't throw - always clean up local state even if API fails
    } finally {
      // Always clean up local state
      if (isMountedRef.current) {
        sessionStorage.removeItem('db_session_id');
        setSessionId(null);
        setIsActive(false);
      }

      // Clear idle timeout
      if (idleTimeoutRef.current) {
        clearTimeout(idleTimeoutRef.current);
        idleTimeoutRef.current = null;
      }
    }
  }, [sessionId]);

  /**
   * Get time remaining until session expires (for UI display)
   */
  const getTimeRemaining = useCallback(() => {
    if (!isActive) return 0;

    const elapsed = Date.now() - lastActivityRef.current;
    const remaining = (5 * 60 * 1000) - elapsed; // 5 minutes in ms

    return Math.max(0, remaining);
  }, [isActive]);

  // Cleanup on unmount
  useEffect(() => {
    isMountedRef.current = true;

    return () => {
      isMountedRef.current = false;
      // Clear timeout on unmount (but don't flush - let page nav handle it)
      if (idleTimeoutRef.current) {
        clearTimeout(idleTimeoutRef.current);
      }
    };
  }, []);

  // beforeunload warning if session active
  useEffect(() => {
    if (!isActive) return;

    const handleBeforeUnload = (e) => {
      // Modern browsers ignore custom messages, but we still need to set returnValue
      e.preventDefault();
      e.returnValue = 'You have an active session. Changes will be saved when you close this tab.';
      return e.returnValue;
    };

    window.addEventListener('beforeunload', handleBeforeUnload);

    return () => {
      window.removeEventListener('beforeunload', handleBeforeUnload);
    };
  }, [isActive]);

  return {
    sessionId,
    isActive,
    error,
    startSession,
    endSession,
    recordActivity,
    getTimeRemaining,
  };
};
