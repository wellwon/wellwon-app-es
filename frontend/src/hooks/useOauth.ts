// Stub hook - OAuth not implemented in new backend yet
// Reference: /reference/frontend_old/src/hooks/useOauth.ts

import { useState } from 'react';

export interface OAuthState {
  loading: boolean;
  error: string | null;
  providers: string[];
}

export function useOauth() {
  const [loading] = useState(false);
  const [error] = useState<string | null>(null);

  const initiateOAuth = async (provider: string) => {
    console.warn('[STUB] OAuth not implemented yet:', provider);
    return false;
  };

  const handleCallback = async (code: string, state: string) => {
    console.warn('[STUB] OAuth callback not implemented yet');
    return false;
  };

  return {
    loading,
    error,
    providers: [],
    initiateOAuth,
    handleCallback,
  };
}

export default useOauth;
