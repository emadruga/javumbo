import axios from 'axios';

/**
 * JWT + Session-Aware Axios Instance
 *
 * Differences from original /client axiosConfig:
 * 1. Uses JWT Bearer token (not cookies/withCredentials)
 * 2. Injects X-Session-ID header from sessionStorage
 * 3. Intercepts responses to extract X-Session-ID (backend may update it)
 * 4. Calls recordActivity callback on every request (to reset idle timer)
 *
 * CRITICAL: This instance must be used with a global activity tracker
 */

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:3000';

const api = axios.create({
  baseURL: API_BASE_URL,
  // NO withCredentials (we're using JWT, not cookies)
  headers: {
    'Content-Type': 'application/json',
    Accept: 'application/json',
  },
});

// Global activity callback (set by App.jsx or context provider)
let activityCallback = null;

export const setActivityCallback = (callback) => {
  activityCallback = callback;
};

// Request interceptor: Add JWT + Session-ID headers
api.interceptors.request.use(
  (config) => {
    // 1. Add JWT token (if exists)
    const token = localStorage.getItem('jwt_token');
    if (token) {
      config.headers['Authorization'] = `Bearer ${token}`;
    }

    // 2. Add X-Session-ID header (if exists)
    const sessionId = sessionStorage.getItem('db_session_id');
    if (sessionId) {
      config.headers['X-Session-ID'] = sessionId;
    }

    // 3. Record activity (reset idle timer)
    if (activityCallback) {
      activityCallback();
    }

    console.log(`[axios] → ${config.method?.toUpperCase()} ${config.url}`, {
      hasToken: !!token,
      hasSessionId: !!sessionId,
    });

    return config;
  },
  (error) => {
    console.error('[axios] Request error:', error);
    return Promise.reject(error);
  }
);

// Response interceptor: Extract session-ID from response headers
api.interceptors.response.use(
  (response) => {
    // Backend may return updated session_id in response headers
    const newSessionId = response.headers['x-session-id'];

    if (newSessionId) {
      const currentSessionId = sessionStorage.getItem('db_session_id');

      if (newSessionId !== currentSessionId) {
        console.log(`[axios] ✓ Updated session ID: ${newSessionId}`);
        sessionStorage.setItem('db_session_id', newSessionId);
      }
    }

    console.log(`[axios] ← ${response.status} ${response.config.url}`);
    return response;
  },
  (error) => {
    // Handle 401 Unauthorized (JWT expired)
    if (error.response?.status === 401) {
      console.error('[axios] 401 Unauthorized - JWT expired or invalid');
      // Clear JWT token
      localStorage.removeItem('jwt_token');
      sessionStorage.removeItem('db_session_id');
      // Redirect to login (or let App.jsx handle it)
      window.location.href = '/login';
    }

    // Handle 409 Conflict (session conflict)
    if (error.response?.status === 409) {
      console.error('[axios] 409 Conflict - User has active session elsewhere');
      alert(
        'Active session detected on another tab/device.\n\n' +
        'Please close other tabs or wait for the session to expire.'
      );
      // Clear local session (force user to create new session)
      sessionStorage.removeItem('db_session_id');
    }

    console.error(`[axios] ← ${error.response?.status || 'ERR'} ${error.config?.url}`, error.response?.data);
    return Promise.reject(error);
  }
);

export default api;
