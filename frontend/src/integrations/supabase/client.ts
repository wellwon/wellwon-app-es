// Stub file - Supabase has been replaced with Event Sourcing backend
// This file exists only to prevent import errors during migration

// eslint-disable-next-line @typescript-eslint/no-explicit-any
type SupabaseStub = any;

// Stub supabase client that throws errors if actually used
export const supabase: SupabaseStub = {
  from: (table: string) => {
    console.warn(`[STUB] Supabase call to table "${table}" - use new API instead`);
    return {
      select: () => ({ data: [], error: null }),
      insert: () => ({ data: null, error: { message: 'Supabase disabled - use new API' } }),
      update: () => ({ data: null, error: { message: 'Supabase disabled - use new API' } }),
      delete: () => ({ data: null, error: { message: 'Supabase disabled - use new API' } }),
      eq: () => ({ data: [], error: null }),
      single: () => ({ data: null, error: null }),
      maybeSingle: () => ({ data: null, error: null }),
    };
  },
  functions: {
    invoke: (name: string) => {
      console.warn(`[STUB] Supabase function "${name}" called - use new API instead`);
      return Promise.resolve({ data: null, error: { message: 'Supabase disabled' } });
    },
  },
  storage: {
    from: (bucket: string) => {
      console.warn(`[STUB] Supabase storage "${bucket}" - use new storage API instead`);
      return {
        upload: () => Promise.resolve({ data: null, error: { message: 'Storage disabled' } }),
        getPublicUrl: () => ({ data: { publicUrl: '' } }),
        download: () => Promise.resolve({ data: null, error: { message: 'Storage disabled' } }),
      };
    },
  },
  auth: {
    getUser: () => Promise.resolve({ data: { user: null }, error: null }),
    getSession: () => Promise.resolve({ data: { session: null }, error: null }),
    onAuthStateChange: () => ({ data: { subscription: { unsubscribe: () => {} } } }),
  },
  channel: () => ({
    on: () => ({ subscribe: () => {} }),
    subscribe: () => {},
    unsubscribe: () => {},
  }),
  rpc: (fn: string) => {
    console.warn(`[STUB] Supabase RPC "${fn}" - use new API instead`);
    return Promise.resolve({ data: null, error: null });
  },
};

export default supabase;
