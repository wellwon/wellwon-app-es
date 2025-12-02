// =============================================================================
// File: src/api/core.ts — Axios Client for REST API
// =============================================================================
// • Axios instance with JWT Bearer injection from localStorage
// • Handles Authorization on each request
// • Automatic token refresh on 401
// • Industrial Standard: Treats tokens as opaque strings (no validation)
// =============================================================================

import axios, {
  AxiosInstance,
  AxiosError,
  InternalAxiosRequestConfig,
  AxiosResponse,
} from "axios";

// -----------------------------------------------------------------------------
// Axios base client for all REST API calls
// -----------------------------------------------------------------------------
export const API: AxiosInstance = axios.create({
  baseURL: import.meta.env?.VITE_API_URL || "http://localhost:5002/",
  timeout: 10_000,
  headers: {
    "Content-Type": "application/json",
  },
});

// Track if we're currently refreshing to prevent multiple refresh attempts
let isRefreshing = false;
let refreshSubscribers: Array<(token: string) => void> = [];

// Helper to notify all subscribers when token is refreshed
const onRefreshed = (token: string) => {
  refreshSubscribers.forEach(callback => callback(token));
  refreshSubscribers = [];
};

// Helper to add subscribers to the refresh queue
const addRefreshSubscriber = (callback: (token: string) => void) => {
  refreshSubscribers.push(callback);
};

// Storage key must match Zustand persist key
const AUTH_STORAGE_KEY = 'wellwon-auth';

// Helper to get auth data from localStorage (matching Zustand persist format)
function getStoredAuth(): { token: string | null; refreshToken: string | null; expiresAt: number | null; sessionId: string | null } | null {
  try {
    const raw = localStorage.getItem(AUTH_STORAGE_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw);
    return parsed?.state || null;
  } catch {
    return null;
  }
}

// -----------------------------------------------------------------------------
// Attach Authorization header from localStorage before each request
// -----------------------------------------------------------------------------
API.interceptors.request.use(
  (config: InternalAxiosRequestConfig): InternalAxiosRequestConfig => {
    // Skip auth header for refresh endpoint
    if (config.url?.includes('/auth/refresh')) {
      return config;
    }

    const auth = getStoredAuth();
    if (auth?.token && config.headers) {
      config.headers["Authorization"] = `Bearer ${auth.token}`;
    }

    return config;
  },
  (error: AxiosError) => Promise.reject(error)
);

// -----------------------------------------------------------------------------
// Response interceptor: Auto-refresh on 401
// -----------------------------------------------------------------------------
API.interceptors.response.use(
  (response: AxiosResponse) => response,
  async (error: AxiosError) => {
    const originalRequest = error.config as InternalAxiosRequestConfig & {
      _retry?: boolean;
      _queued?: boolean;
    };

    // If refresh endpoint itself returns 401, clear auth and redirect
    if (originalRequest?.url?.includes('/auth/refresh')) {
      console.error('Refresh token is invalid or expired');
      localStorage.removeItem(AUTH_STORAGE_KEY);
      window.location.href = '/login?reason=session_expired';
      return Promise.reject(error);
    }

    // If 401 and not already retried, attempt token refresh
    if (error.response?.status === 401 && !originalRequest._retry) {
      originalRequest._retry = true;

      if (!isRefreshing) {
        isRefreshing = true;

        try {
          // Get current auth data from Zustand persist storage
          const authData = getStoredAuth();
          if (!authData) {
            throw new Error('No auth data found');
          }

          const refreshToken = authData?.refreshToken;

          if (!refreshToken) {
            throw new Error('No refresh token available');
          }

          console.log('[API] Starting token refresh...');

          // Make refresh request directly without using the intercepted client
          const refreshResponse = await axios.post(
            `${import.meta.env?.VITE_API_URL || "http://localhost:5002"}/auth/refresh`,
            { refresh_token: refreshToken },
            {
              headers: {
                'Content-Type': 'application/json',
              },
            }
          );

          const data = refreshResponse.data;

          // Industrial Standard: Just check token existence, no validation
          if (!data.access_token) {
            throw new Error('No access token received from refresh');
          }

          // Update stored auth data in Zustand persist format
          const updatedState = {
            token: data.access_token,
            refreshToken: data.refresh_token || refreshToken, // Keep old refresh token if not rotated
            expiresAt: Date.now() + ((data.expires_in || 900) * 1000), // Default 15 min if not provided
            sessionId: authData.sessionId,
            isAuthenticated: true,
          };

          // Zustand persist wraps state in { state: ..., version: ... }
          const persistData = {
            state: updatedState,
            version: 0,
          };

          localStorage.setItem(AUTH_STORAGE_KEY, JSON.stringify(persistData));
          console.log('[API] Token refreshed successfully');

          // Update the authorization header for the original request
          originalRequest.headers["Authorization"] = `Bearer ${data.access_token}`;

          // Notify all waiting requests
          onRefreshed(data.access_token);

          // Retry the original request
          return API(originalRequest);

        } catch (refreshError: any) {
          console.error('[API] Token refresh failed:', refreshError);

          // Notify all waiting requests of failure
          refreshSubscribers = [];

          // Only clear auth and redirect for actual auth failures (401/403)
          // NOT for network errors (backend down) - let user stay logged in with cached data
          const status = refreshError?.response?.status;
          if (status === 401 || status === 403) {
            // Actual auth failure - session invalid
            localStorage.removeItem(AUTH_STORAGE_KEY);
            window.location.href = '/login?reason=session_expired';
          } else {
            // Network error or server down - don't log out, just fail silently
            // User can continue with cached data until backend comes back
            console.warn('[API] Token refresh failed due to network/server error, keeping session');
          }

          return Promise.reject(refreshError);
        } finally {
          isRefreshing = false;
        }
      } else {
        // Token refresh is already in progress
        // Queue this request to retry after refresh completes
        return new Promise((resolve, reject) => {
          addRefreshSubscriber((token: string) => {
            // Update the authorization header with new token
            originalRequest.headers["Authorization"] = `Bearer ${token}`;
            // Retry the original request
            resolve(API(originalRequest));
          });
        });
      }
    }

    return Promise.reject(error);
  }
);

// -----------------------------------------------------------------------------
// Helper function to make requests without auth interceptor (for auth endpoints)
// -----------------------------------------------------------------------------
export const APIWithoutAuth = axios.create({
  baseURL: import.meta.env?.VITE_API_URL || "http://localhost:5002/",
  timeout: 10_000,
  headers: {
    "Content-Type": "application/json",
  },
});