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

// -----------------------------------------------------------------------------
// Attach Authorization header from localStorage before each request
// -----------------------------------------------------------------------------
API.interceptors.request.use(
  (config: InternalAxiosRequestConfig): InternalAxiosRequestConfig => {
    // Skip auth header for refresh endpoint
    if (config.url?.includes('/auth/refresh')) {
      return config;
    }

    try {
      const raw = localStorage.getItem("auth");
      const auth = raw ? JSON.parse(raw) : null;

      if (auth?.token && config.headers) {
        config.headers["Authorization"] = `Bearer ${auth.token}`;
      }
    } catch (e) {
      console.warn("[API] Failed to parse auth data from localStorage:", e);
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
      localStorage.removeItem("auth");
      window.location.href = '/login?reason=session_expired';
      return Promise.reject(error);
    }

    // If 401 and not already retried, attempt token refresh
    if (error.response?.status === 401 && !originalRequest._retry) {
      originalRequest._retry = true;

      if (!isRefreshing) {
        isRefreshing = true;

        try {
          // Get current auth data
          const storedAuth = localStorage.getItem("auth");
          if (!storedAuth) {
            throw new Error('No auth data found');
          }

          const authData = JSON.parse(storedAuth);
          const refreshToken = authData?.refresh_token;

          if (!refreshToken) {
            throw new Error('No refresh token available');
          }

          console.log('[API] Starting token refresh...');

          // Make refresh request directly without using the intercepted client
          const refreshResponse = await axios.post(
            `${import.meta.env?.VITE_API_URL || "http://localhost:5001"}/auth/refresh`,
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

          // Update stored auth data - treat token as opaque string
          const updatedAuth = {
            token: data.access_token,
            refresh_token: data.refresh_token || refreshToken, // Keep old refresh token if not rotated
            expires_at: Date.now() + ((data.expires_in || 900) * 1000), // Default 15 min if not provided
            token_type: data.token_type || 'Bearer',
            session_id: authData.session_id
          };

          localStorage.setItem("auth", JSON.stringify(updatedAuth));
          console.log('[API] Token refreshed successfully');

          // Update the authorization header for the original request
          originalRequest.headers["Authorization"] = `Bearer ${data.access_token}`;

          // Notify all waiting requests
          onRefreshed(data.access_token);

          // Retry the original request
          return API(originalRequest);

        } catch (refreshError) {
          console.error('[API] Token refresh failed:', refreshError);

          // Clear auth data
          localStorage.removeItem("auth");

          // Notify all waiting requests of failure
          refreshSubscribers = [];

          // Redirect to login
          window.location.href = '/login?reason=session_expired';

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