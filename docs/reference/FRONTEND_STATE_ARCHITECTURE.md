# Frontend State Architecture Guide

**Version:** 1.0
**Last Updated:** 2025-11-29
**Pattern:** TkDodo's "Using WebSockets with React Query"

---

## Overview

WellWon frontend uses a three-layer state management architecture:

```
┌─────────────────────────────────────────────────────────────┐
│                        COMPONENTS                           │
│                    (UI Rendering Only)                      │
└─────────────────────────────────────────────────────────────┘
                              │
              ┌───────────────┼───────────────┐
              ▼               ▼               ▼
┌─────────────────┐  ┌─────────────┐  ┌─────────────────────┐
│  React Query    │  │   Zustand   │  │   WSE (WebSocket)   │
│  Server State   │  │  UI State   │  │   Real-time Events  │
└─────────────────┘  └─────────────┘  └─────────────────────┘
         │                                      │
         │              ┌───────────────────────┘
         ▼              ▼
┌─────────────────────────────────────────────────────────────┐
│                    React Query Cache                        │
│              (Single Source of Truth)                       │
└─────────────────────────────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────────────────────┐
│                      REST API (Axios)                       │
└─────────────────────────────────────────────────────────────┘
```

---

## Core Principles

### 1. Server State = React Query

**ALL data from the backend belongs in React Query**, not `useState`.

```typescript
// ❌ WRONG - Old pattern
const [users, setUsers] = useState<User[]>([]);
const [loading, setLoading] = useState(false);

useEffect(() => {
  setLoading(true);
  fetchUsers().then(setUsers).finally(() => setLoading(false));
}, []);

// ✅ CORRECT - React Query pattern
const { data: users, isLoading } = useQuery({
  queryKey: ['users'],
  queryFn: fetchUsers,
});
```

### 2. UI State = Zustand

**Local, synchronous UI state** that doesn't come from the server:

- Active chat ID
- Sidebar collapsed state
- Filter/sort selections
- Modal open/close state
- Form input values (before submission)

```typescript
// ✅ CORRECT - Zustand for UI state
export const useChatUIStore = create<ChatUIState>((set) => ({
  activeChatId: null,
  setActiveChatId: (id) => set({ activeChatId: id }),

  replyingTo: null,
  setReplyingTo: (msg) => set({ replyingTo: msg }),
}));
```

### 3. Real-time Updates = WSE → React Query

**WSE events update React Query cache**, not component state:

```typescript
// ✅ CORRECT - WSE updates React Query
useEffect(() => {
  const handleMessageCreated = (event: CustomEvent) => {
    const message = event.detail;

    // Update cache directly for instant UI
    queryClient.setQueryData(
      chatKeys.messages(message.chat_id),
      (old) => old ? [...old, message] : [message]
    );
  };

  window.addEventListener('messageCreated', handleMessageCreated);
  return () => window.removeEventListener('messageCreated', handleMessageCreated);
}, [queryClient]);
```

---

## Directory Structure

```
frontend/src/
├── api/                    # Axios API functions
│   ├── core.ts            # Axios instance with interceptors
│   ├── chat.ts            # Chat API endpoints
│   ├── company.ts         # Company API endpoints
│   ├── telegram.ts        # Telegram API endpoints
│   └── user_account.ts    # Auth API endpoints
│
├── hooks/                  # React Query + Zustand hooks
│   ├── auth/              # Authentication hooks
│   │   ├── index.ts       # Barrel export
│   │   ├── useProfile.ts  # User profile query + WSE
│   │   ├── useAuthStore.ts # Token state (Zustand)
│   │   └── useAuthMutations.ts # Login/logout mutations
│   │
│   ├── chat/              # Chat hooks
│   │   ├── index.ts
│   │   ├── useChatMessages.ts # Messages infinite query
│   │   ├── useChatList.ts     # Chat list query
│   │   ├── useChatMutations.ts # Send/edit/delete
│   │   ├── useChatUIStore.ts   # UI state (Zustand)
│   │   └── useMessageTemplates.ts
│   │
│   ├── company/           # Company hooks
│   │   └── index.ts       # useCompany, useMyCompanies
│   │
│   ├── telegram/          # Telegram hooks
│   │   └── index.ts       # useTelegramMembers, etc.
│   │
│   └── admin/             # Admin hooks
│       └── index.ts       # useAdminUsers
│
├── wse/                    # WebSocket Engine
│   ├── hooks/
│   │   └── useWSE.ts      # WSE connection hook
│   ├── handlers/
│   │   └── EventHandlers.ts # Event dispatch
│   └── types.ts
│
└── contexts/               # React Contexts (minimal use)
    ├── AuthContext.tsx    # Auth provider (wraps hooks)
    └── RealtimeChatContext.tsx # Chat provider (wraps hooks)
```

---

## Creating a New Domain Hook

### Step 1: Define Query Keys Factory

```typescript
// hooks/products/index.ts

export const productKeys = {
  all: ['products'] as const,
  lists: () => [...productKeys.all, 'list'] as const,
  list: (filters: ProductFilters) => [...productKeys.lists(), filters] as const,
  details: () => [...productKeys.all, 'detail'] as const,
  detail: (id: string) => [...productKeys.details(), id] as const,
};
```

### Step 2: Create Query Hook with WSE

```typescript
export function useProduct(productId: string | null) {
  const queryClient = useQueryClient();

  // WSE event handler - update cache on server events
  useEffect(() => {
    if (!productId) return;

    const handleProductUpdate = (event: CustomEvent) => {
      const updated = event.detail;
      if (updated.id === productId) {
        queryClient.setQueryData(productKeys.detail(productId), updated);
      }
    };

    window.addEventListener('productUpdated', handleProductUpdate);
    return () => window.removeEventListener('productUpdated', handleProductUpdate);
  }, [productId, queryClient]);

  // Query
  const query = useQuery({
    queryKey: productId ? productKeys.detail(productId) : ['disabled'],
    queryFn: () => productApi.getById(productId!),
    enabled: !!productId,
    staleTime: 5 * 60 * 1000, // 5 minutes
  });

  return {
    product: query.data ?? null,
    isLoading: query.isLoading,
    isError: query.isError,
    error: query.error,
    refetch: query.refetch,
  };
}
```

### Step 3: Create Mutations with Optimistic Updates

```typescript
export function useUpdateProduct() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async ({ id, data }: { id: string; data: UpdateProductData }) => {
      const response = await productApi.update(id, data);
      return response.data;
    },

    // Optimistic update
    onMutate: async ({ id, data }) => {
      await queryClient.cancelQueries({ queryKey: productKeys.detail(id) });

      const previousProduct = queryClient.getQueryData(productKeys.detail(id));

      queryClient.setQueryData(productKeys.detail(id), (old: Product | undefined) =>
        old ? { ...old, ...data } : old
      );

      return { previousProduct };
    },

    // Rollback on error
    onError: (err, { id }, context) => {
      if (context?.previousProduct) {
        queryClient.setQueryData(productKeys.detail(id), context.previousProduct);
      }
    },

    // Refetch after mutation
    onSettled: (data, error, { id }) => {
      queryClient.invalidateQueries({ queryKey: productKeys.detail(id) });
      queryClient.invalidateQueries({ queryKey: productKeys.lists() });
    },
  });
}
```

### Step 4: Export from Barrel

```typescript
// hooks/products/index.ts
export { useProduct, useProducts, useUpdateProduct, productKeys };

// hooks/index.ts
export * from './products';
```

---

## WSE Event Integration

### Backend → Frontend Flow

```
Backend Domain Event
        ↓
   WSE Publisher
        ↓
   WebSocket Message
        ↓
   WSE EventHandlers.ts
        ↓
   window.dispatchEvent(new CustomEvent('eventName', { detail }))
        ↓
   React Query Hook (useEffect listener)
        ↓
   queryClient.setQueryData() or queryClient.invalidateQueries()
        ↓
   Component Re-renders with New Data
```

### Standard WSE Event Names

| Event Name | Payload | React Query Action |
|------------|---------|-------------------|
| `messageCreated` | `{ chat_id, message }` | Add to messages cache |
| `messageUpdated` | `{ chat_id, message }` | Update in cache |
| `messageDeleted` | `{ chat_id, message_id }` | Remove from cache |
| `chatUpdated` | `{ chat }` | Update chat detail |
| `chatCreated` | `{ chat }` | Invalidate list |
| `userProfileUpdated` | `{ user }` | Update profile cache |
| `userAdminChange` | `{ userId, changes }` | Update user in cache |
| `companyUpdated` | `{ company }` | Update company cache |
| `memberUpdated` | `{ group_id, member }` | Update members cache |

### Adding New WSE Event Handler

```typescript
// In your hook file
useEffect(() => {
  const handleEvent = (event: CustomEvent<YourEventPayload>) => {
    const payload = event.detail;

    // Option 1: Direct cache update (instant, optimistic)
    queryClient.setQueryData(yourKeys.detail(payload.id), payload);

    // Option 2: Invalidate and refetch (guaranteed fresh)
    queryClient.invalidateQueries({ queryKey: yourKeys.detail(payload.id) });
  };

  window.addEventListener('yourEventName', handleEvent as EventListener);
  return () => window.removeEventListener('yourEventName', handleEvent as EventListener);
}, [queryClient]);
```

---

## Common Patterns

### Pattern 1: Conditional Query

```typescript
// Only fetch when we have an ID
const { data } = useQuery({
  queryKey: id ? keys.detail(id) : ['disabled'],
  queryFn: () => api.getById(id!),
  enabled: !!id, // Don't run if no ID
});
```

### Pattern 2: Infinite Scroll

```typescript
const {
  data,
  fetchNextPage,
  hasNextPage,
  isFetchingNextPage,
} = useInfiniteQuery({
  queryKey: keys.messages(chatId),
  queryFn: ({ pageParam = null }) => api.getMessages(chatId, { cursor: pageParam }),
  getNextPageParam: (lastPage) => lastPage.nextCursor,
  enabled: !!chatId,
});

// Flatten pages for rendering
const messages = data?.pages.flatMap(page => page.items) ?? [];
```

### Pattern 3: Dependent Queries

```typescript
// First query
const { data: user } = useQuery({
  queryKey: ['user'],
  queryFn: fetchUser,
});

// Second query depends on first
const { data: projects } = useQuery({
  queryKey: ['projects', user?.id],
  queryFn: () => fetchProjects(user!.id),
  enabled: !!user?.id, // Only run when user is loaded
});
```

### Pattern 4: Prefetching

```typescript
// Prefetch on hover
const prefetchProduct = (id: string) => {
  queryClient.prefetchQuery({
    queryKey: productKeys.detail(id),
    queryFn: () => productApi.getById(id),
    staleTime: 5 * 60 * 1000,
  });
};

<div onMouseEnter={() => prefetchProduct(item.id)}>
  {item.name}
</div>
```

---

## Anti-Patterns to Avoid

### ❌ useState for Server Data

```typescript
// WRONG
const [data, setData] = useState(null);
useEffect(() => {
  fetchData().then(setData);
}, []);
```

### ❌ Manual Loading States

```typescript
// WRONG
const [loading, setLoading] = useState(false);
const [error, setError] = useState(null);
```

### ❌ Duplicate Cache

```typescript
// WRONG - Don't maintain separate cache
const [companiesCache, setCompaniesCache] = useState(new Map());
```

### ❌ Unstable Dependencies in useEffect

```typescript
// WRONG - setSomething creates new reference each render → infinite loop
useEffect(() => {
  setSomething(value);
}, [setSomething]); // This causes infinite loop!

// CORRECT - Use ref to prevent re-running
const syncedRef = useRef(false);
useEffect(() => {
  if (syncedRef.current) return;
  syncedRef.current = true;
  setSomething(value);
}, [value]);
```

### ❌ Fetching in Components

```typescript
// WRONG - API calls should be in hooks
const Component = () => {
  useEffect(() => {
    axios.get('/api/data').then(res => setData(res.data));
  }, []);
};

// CORRECT - Use hook
const Component = () => {
  const { data } = useData();
};
```

---

## Storage Keys

| Key | Purpose | Format |
|-----|---------|--------|
| `wellwon-auth` | Zustand persist for auth tokens | `{ state: { token, refreshToken, ... }, version: 0 }` |
| `ww:chat.sidebar.state` | Sidebar UI state | `{ selectedSupergroupId, groupsPanelCollapsed, activeMode }` |

**Important:** Axios interceptors read from `wellwon-auth` to match Zustand persist format.

---

## Testing Checklist

When adding new hooks, verify:

- [ ] Query keys are unique and follow the factory pattern
- [ ] `enabled` option prevents unnecessary fetches
- [ ] `staleTime` is set appropriately (default: 5 minutes)
- [ ] WSE events update the cache correctly
- [ ] Mutations have optimistic updates where appropriate
- [ ] Error states are handled
- [ ] Loading states are exposed
- [ ] Hook is exported from barrel file
- [ ] No `useState` for server data
- [ ] No direct API calls in components

---

## References

- [TkDodo's Blog: React Query and WebSockets](https://tkdodo.eu/blog/using-web-sockets-with-react-query)
- [React Query Documentation](https://tanstack.com/query/latest)
- [Zustand Documentation](https://docs.pmnd.rs/zustand)
- [WellWon WSE Protocol](./WSE_MESSAGE_PROTOCOL_REFERENCE.md)
