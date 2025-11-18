// =============================================================================
// File: src/api/oauth.ts — TradeCore v0.5 — OAuth API Layer
// FULL VERSION: Supports both Alpaca (permanent token) and TradeStation (refresh)
// =============================================================================

import { API } from "./core";
import { BrokerEnvironment } from "@/types/broker.types";

// =============================================================================
// Types
// =============================================================================

export interface OAuthPrepareRequest {
  broker_connection_id: string;
  environment: string;
  redirect_uri: string;
  scope?: string;
}

export interface OAuthPrepareResponse {
  oauth_url: string;
  expires_in: number;
  token: string;
}

export interface OAuthStartFlowResponse {
  authorization_url: string;
  broker_connection_id: string;
  state: string;
}

export interface OAuthStatusResponse {
  connected: boolean;
  status: string;
  broker_connection_id?: string;
  broker?: string;
  environment?: string;
  message?: string;
}

export interface OAuthTokenStatusResponse {
  valid: boolean;
  reason: string;
  expires_at?: string;
  expires_in?: number;
  scopes?: string;
}

export interface OAuthTokenRefreshResponse {
  access_token: string;
  expires_at?: string;
  expires_in?: number;
  scope?: string;
}

export interface OAuthRevokeResponse {
  status: string;
  message: string;
}

// =============================================================================
// OAuth Flow Functions
// =============================================================================

/**
 * Step 1: Prepare OAuth flow (requires JWT authentication)
 * Creates temporary token for secure OAuth initiation
 */
export async function prepareOAuthFlow(
  params: OAuthPrepareRequest
): Promise<OAuthPrepareResponse> {
  const { data } = await API.post<OAuthPrepareResponse>('/oauth/prepare', params);
  return data;
}

/**
 * Check OAuth connection status (PUBLIC endpoint - no auth needed)
 * Used after OAuth callback to verify connection
 */
export async function checkOAuthStatus(
  broker: string,
  connectionId: string
): Promise<OAuthStatusResponse> {
  const { data } = await API.get<OAuthStatusResponse>(
    `/oauth/${broker}/status/${connectionId}`
  );
  return data;
}

// =============================================================================
// Token Management Functions (All require authentication)
// =============================================================================

/**
 * Get access token status for a given broker/env
 * Works for both Alpaca (permanent) and TradeStation (expiring) tokens
 */
export async function getAccessTokenStatus(
  broker: string,
  environment: BrokerEnvironment
): Promise<OAuthTokenStatusResponse> {
  const { data } = await API.get<OAuthTokenStatusResponse>(
    `/oauth/${broker}/token/status`,
    { params: { environment } }
  );
  return data;
}

/**
 * Refresh access token using refresh_token
 * - Alpaca: Will return error (no refresh needed)
 * - TradeStation: Returns new access_token
 * - Virtual: Simulates refresh for testing
 */
export async function refreshAccessToken(
  broker: string,
  environment: BrokerEnvironment
): Promise<OAuthTokenRefreshResponse> {
  const { data } = await API.post<OAuthTokenRefreshResponse>(
    `/oauth/${broker}/token/refresh`,
    null,
    { params: { environment } }
  );
  return data;
}

/**
 * Revoke tokens and disconnect
 * - Alpaca: Just clears local tokens (no API revoke)
 * - TradeStation: Calls revoke endpoint + clears tokens
 * - Both: Triggers disconnect flow
 */
export async function revokeRefreshToken(
  broker: string,
  environment: BrokerEnvironment
): Promise<OAuthRevokeResponse> {
  const { data } = await API.post<OAuthRevokeResponse>(
    `/oauth/${broker}/revoke`,
    null,
    { params: { environment } }
  );
  return data;
}

// =============================================================================
// Main OAuth Redirect Handler
// =============================================================================

/**
 * Handle OAuth redirect from backend /broker/connect response
 * This is the main entry point when user clicks "Connect with OAuth"
 */
export async function handleOAuthRedirect(response: any): Promise<void> {
  // Validate response
  if (!response.requires_oauth) {
    console.error('[OAuth] Invalid response - requires_oauth not set:', response);
    throw new Error('Invalid OAuth redirect response');
  }

  if (!response.broker_connection_id) {
    console.error('[OAuth] Missing broker_connection_id:', response);
    throw new Error('broker_connection_id is required for OAuth flow');
  }

  console.log('[OAuth] Starting OAuth flow:', {
    broker: response.broker_id,
    environment: response.environment,
    connection_id: response.broker_connection_id
  });

  try {
    // Step 1: Call /oauth/prepare with JWT to get temporary token
    const prepareResponse = await prepareOAuthFlow({
      broker_connection_id: response.broker_connection_id,
      environment: response.environment || 'paper',
      redirect_uri: response.redirect_uri || `http://localhost:5001/oauth/${response.broker_id}/callback`,
      scope: response.scopes || getDefaultOAuthScopes(response.broker_id || 'alpaca')
    });

    console.log('[OAuth] Prepared successfully:', {
      expires_in: prepareResponse.expires_in,
      oauth_url: prepareResponse.oauth_url
    });

    // Step 2: Redirect browser to backend OAuth endpoint
    const baseUrl = window.location.origin.replace(':5173', ':5001');
    const fullUrl = `${baseUrl}${prepareResponse.oauth_url}`;

    console.log('[OAuth] Redirecting browser to:', fullUrl);

    // CRITICAL FIX: Clear persisted state before OAuth redirect (SELECTIVE)
    // Problem: WebSocket events during OAuth persist connection/accounts → cards appear before redirect
    // Solution: Clear localStorage but KEEP sessionStorage disconnect tracking
    localStorage.removeItem('broker-connections-storage');
    localStorage.removeItem('broker-account-storage');
    localStorage.removeItem('automation-storage');

    // CRITICAL: DON'T clear sessionStorage - it has broker_disconnected_* tracking!
    // Only clear OAuth-specific keys
    const keysToRemove: string[] = [];
    for (let i = 0; i < sessionStorage.length; i++) {
      const key = sessionStorage.key(i);
      if (key && !key.startsWith('broker_disconnected_')) {
        keysToRemove.push(key);
      }
    }
    keysToRemove.forEach(key => sessionStorage.removeItem(key));
    console.log('[OAuth] Cleared localStorage and non-disconnect sessionStorage');

    // This will navigate away from the app
    window.location.href = fullUrl;

  } catch (error) {
    console.error('[OAuth] Failed to prepare OAuth flow:', error);
    throw error;
  }
}

// =============================================================================
// OAuth Callback Parser
// =============================================================================

/**
 * Parse OAuth result from URL after backend redirects back
 * Backend redirects to: /brokers?oauth_success=true&broker=alpaca&...
 */
export function parseOAuthCallback(url: string): {
  success: boolean;
  broker?: string;
  connectionId?: string;
  environment?: string;
  error?: string;
  errorDescription?: string;
} {
  const urlObj = new URL(url);
  const params = urlObj.searchParams;

  // Check for success
  if (params.get('oauth_success') === 'true') {
    return {
      success: true,
      broker: params.get('broker') || undefined,
      connectionId: params.get('connection_id') || undefined,
      environment: params.get('environment') || undefined,
    };
  }

  // Check for error
  if (params.get('oauth_error') === 'true') {
    return {
      success: false,
      broker: params.get('broker') || undefined,
      error: params.get('error') || 'Unknown error',
      errorDescription: params.get('error_description') || undefined,
    };
  }

  // No OAuth params found
  return {
    success: false,
    error: 'No OAuth callback parameters found',
  };
}

// =============================================================================
// Helper Functions
// =============================================================================

/**
 * Get default OAuth scopes for broker
 */
export function getDefaultOAuthScopes(broker: string): string {
  const scopes: Record<string, string> = {
    alpaca: 'account:write trading data',
    tradestation: 'openid profile offline_access MarketData ReadAccount Trade',
    virtual: 'trading account market_data'
  };
  return scopes[broker.toLowerCase()] || '';
}

/**
 * Check if broker supports OAuth
 */
export function supportsOAuth(broker: string): boolean {
  return ['alpaca', 'tradestation', 'virtual'].includes(broker.toLowerCase());
}

/**
 * Check if broker supports token refresh
 * - Alpaca: NO (permanent token)
 * - TradeStation: YES (OAuth2 with refresh)
 * - Virtual: YES (for testing)
 */
export function supportsTokenRefresh(broker: string): boolean {
  return ['tradestation', 'virtual'].includes(broker.toLowerCase());
}

/**
 * Check if broker has token revocation endpoint
 * - Alpaca: NO (just clear locally)
 * - TradeStation: YES (must call revoke)
 * - Virtual: NO (just clear locally)
 */
export function supportsTokenRevocation(broker: string): boolean {
  return broker.toLowerCase() === 'tradestation';
}

// =============================================================================
// UI Helper - Show/hide refresh button based on broker
// =============================================================================

/**
 * Helper for UI to determine if refresh token button should be shown
 */
export function shouldShowRefreshButton(
  broker: string,
  tokenStatus?: OAuthTokenStatusResponse
): boolean {
  // Only show for brokers that support refresh
  if (!supportsTokenRefresh(broker)) {
    return false;
  }

  // If we have status, check if token exists and might need refresh
  if (tokenStatus) {
    // Show if token exists but might expire soon
    return tokenStatus.valid && tokenStatus.expires_at !== null;
  }

  // Default to showing for supported brokers
  return true;
}

// =============================================================================
// Export all types
// =============================================================================

export type {
  BrokerEnvironment
} from "@/types/broker.types";