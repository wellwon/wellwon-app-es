// src/api/user_account.ts
import { API, APIWithoutAuth } from "./core";

// -----------------------------------------------------------------------------
// Types (matching backend user_account_api_models.py)
// -----------------------------------------------------------------------------
export interface AuthResponse {
  access_token: string;
  refresh_token: string;
  token_type: string;
  expires_in: number;
  scope: string | null;
  requires_mfa: boolean;
  session_id: string;
  active_sessions: number;
}

export interface RefreshTokenResponse {
  access_token: string;
  refresh_token: string | null;
  token_type: string;
  expires_in: number;
  token_rotated: boolean;
}

export interface UserProfileResponse {
  user_id: string;
  username: string;
  email: string;
  role: string;
  is_active: boolean;
  email_verified: boolean;
  mfa_enabled: boolean;
  created_at: string;
  last_login: string | null;
  last_password_change: string | null;
  security_alerts_enabled: boolean;
  connected_brokers: string[];
  active_sessions_count: number;
}

export interface RegisterRequest {
  username: string;
  email: string;
  password: string;
  secret: string;
  terms_accepted: boolean;
  marketing_consent?: boolean;
  referral_code?: string;
}

export interface VerifyPasswordRequest {
  password: string;
  operation?: string;
}

export interface PasswordResetRequest {
  username: string;
  secret: string;
  new_password: string;
  reset_token?: string;
}

export interface ChangePasswordRequest {
  old_password: string;
  new_password: string;
  revoke_all_sessions?: boolean;
}

export interface DeleteAccountRequest {
  password: string;
  confirmation_phrase: string;
  reason?: string;
  feedback?: string;
}

export interface StatusResponse {
  status: string;
  message?: string;
  code?: string;
  details?: Record<string, any>;
  timestamp: string;
}

export interface SessionInfo {
  session_id: string;
  created_at: string;
  last_used: string;
  device_info: any;
  location?: Record<string, any>;
  is_current: boolean;
  rotation_count: number;
}

// -----------------------------------------------------------------------------
// Pure API Functions - No State Management
// -----------------------------------------------------------------------------

export async function login(
  username: string,
  password: string,
  mfa_code?: string,
  device_info?: Record<string, any>,
  remember_me: boolean = false
): Promise<AuthResponse> {
  const { data } = await APIWithoutAuth.post<AuthResponse>("/user/login", {
    username,
    password,
    mfa_code,
    device_info,
    remember_me,
  });
  return data;
}

export async function logout(): Promise<void> {
  try {
    await API.post("/user/logout");
  } catch (error) {
    console.error('Logout API call failed:', error);
    // Don't throw - let the caller handle cleanup
  }
}

export async function logoutAllSessions(): Promise<StatusResponse> {
  const { data } = await API.post<StatusResponse>("/user/logout-all");
  return data;
}

export async function refreshToken(refresh_token: string): Promise<RefreshTokenResponse> {
  const { data } = await APIWithoutAuth.post<RefreshTokenResponse>(
    "/user/refresh",
    { refresh_token }
  );
  return data;
}

export async function getActiveSessions(): Promise<SessionInfo[]> {
  const { data } = await API.get<SessionInfo[]>("/user/sessions");
  return data;
}

export async function terminateSession(sessionId: string): Promise<StatusResponse> {
  const { data } = await API.post<StatusResponse>(`/user/sessions/${sessionId}/terminate`);
  return data;
}

export async function fetchMe(): Promise<UserProfileResponse> {
  const { data } = await API.get<UserProfileResponse>("/user/me");
  return data;
}

export async function updateProfile(
  email?: string,
  security_alerts_enabled?: boolean,
  mfa_enabled?: boolean
): Promise<UserProfileResponse> {
  const { data } = await API.patch<UserProfileResponse>("/user/profile", {
    email,
    security_alerts_enabled,
    mfa_enabled,
  });
  return data;
}

export async function register(
  username: string,
  email: string,
  password: string,
  secret: string,
  terms_accepted: boolean = true,
  marketing_consent: boolean = false,
  referral_code?: string
): Promise<StatusResponse> {
  const { data } = await APIWithoutAuth.post<StatusResponse>("/user/register", {
    username,
    email,
    password,
    secret,
    terms_accepted,
    marketing_consent,
    referral_code,
  } as RegisterRequest);
  return data;
}

export async function verifyPassword(password: string, operation?: string): Promise<StatusResponse> {
  const { data } = await API.post<StatusResponse>("/user/verify-password", {
    password,
    operation,
  } as VerifyPasswordRequest);
  return data;
}

export async function forgotPassword(
  username: string,
  secret: string,
  new_password: string,
  reset_token?: string
): Promise<StatusResponse> {
  const { data } = await APIWithoutAuth.post<StatusResponse>("/user/forgot-password", {
    username,
    secret,
    new_password,
    reset_token,
  } as PasswordResetRequest);
  return data;
}

export async function changePassword(
  old_password: string,
  new_password: string,
  revoke_all_sessions: boolean = true
): Promise<StatusResponse> {
  const { data } = await API.post<StatusResponse>("/user/change-password", {
    old_password,
    new_password,
    revoke_all_sessions,
  } as ChangePasswordRequest);
  return data;
}

export async function deleteAccount(
  password: string,
  reason?: string,
  feedback?: string
): Promise<StatusResponse> {
  const { data } = await API.post<StatusResponse>("/user/delete", {
    password,
    confirmation_phrase: "DELETE MY ACCOUNT",
    reason,
    feedback,
  } as DeleteAccountRequest);
  return data;
}

// -----------------------------------------------------------------------------
// Simple Storage Helpers (Industrial Standard - No Validation)
// -----------------------------------------------------------------------------

export interface AuthStorage {
  token: string;
  refresh_token: string;
  expires_at: number;
  token_type: string;
  session_id: string;
}

export function getStoredAuth(): AuthStorage | null {
  try {
    const auth = localStorage.getItem("auth");
    return auth ? JSON.parse(auth) : null;
  } catch {
    return null;
  }
}

export function setStoredAuth(auth: AuthStorage): void {
  localStorage.setItem("auth", JSON.stringify(auth));
}

export function clearStoredAuth(): void {
  localStorage.removeItem("auth");
}

// These simple helpers can be used by useAuth.ts
export function getStoredToken(): string | null {
  const auth = getStoredAuth();
  if (!auth?.token) return null;

  // Don't return expired tokens
  if (isTokenExpired()) {
    return null;
  }

  return auth.token;
}

export function isTokenExpired(): boolean {
  const auth = getStoredAuth();
  if (!auth?.expires_at) return true;

  // Add a small buffer (5 seconds) to account for clock differences
  return Date.now() > (auth.expires_at - 5000);
}