export interface Profile {
  id: string;
  user_id: string;
  username: string;
  email: string;
  role: string;
  first_name: string | null;
  last_name: string | null;
  avatar_url: string | null;
  bio: string | null;
  phone: string | null;
  active: boolean;
  is_active: boolean;
  is_developer: boolean;
  email_verified: boolean;
  mfa_enabled: boolean;
  user_number?: number;
  user_type?: string;
  created_at: string;
  updated_at: string;
  last_login: string | null;
  last_password_change: string | null;
  security_alerts_enabled: boolean;
  active_sessions_count: number;
}

export interface AuthError {
  message: string;
  status?: number;
  details?: Record<string, unknown>;
}

export interface AuthResponse {
  error: AuthError | null;
  data?: unknown;
}

export interface SignUpMetadata {
  first_name?: string;
  last_name?: string;
  avatar_url?: string;
  [key: string]: unknown;
}