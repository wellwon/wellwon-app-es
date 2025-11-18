// Stub file - OAuth not implemented in new backend yet
// Reference: /reference/frontend_old/src/api/oauth.ts

export interface OAuthProvider {
  id: string;
  name: string;
  enabled: boolean;
}

export async function getOAuthProviders(): Promise<OAuthProvider[]> {
  console.warn('[STUB] OAuth not implemented yet');
  return [];
}

export async function initiateOAuth(provider: string): Promise<string | null> {
  console.warn('[STUB] OAuth not implemented yet');
  return null;
}

export async function handleOAuthCallback(code: string, state: string): Promise<boolean> {
  console.warn('[STUB] OAuth not implemented yet');
  return false;
}
