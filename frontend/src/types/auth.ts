export interface Profile {
  id: string;
  user_id: string;
  first_name: string | null;
  last_name: string | null;
  avatar_url: string | null;
  bio: string | null;
  phone: string | null;
  active: boolean;
  is_developer: boolean;
  user_number?: number;
  created_at: string;
  updated_at: string;
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