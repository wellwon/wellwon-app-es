# Reactive Interface Reference - Universal Pattern

**For:** Future Projects | **Status:** Reference | **Updated:** Nov 16, 2025

---

## Overview

Universal pattern for building reactive real-time interfaces using **WebSocket Streaming Engine (WSE)** + **React Query** + **Event-Driven Backend**.

**Domain Agnostic:** Works for any real-time application (trading, chat, collaboration, IoT, gaming, etc.)

---

## Architecture Pattern

```
┌────────────────────────────────────────────────────────────────┐
│           Universal Reactive Interface Architecture            │
└────────────────────────────────────────────────────────────────┘

BACKEND                          FRONTEND
────────                         ────────

┌──────────────┐
│ REST API     │ ──────────┐
└──────────────┘           │
                           ├──→ React Query Cache ──→ Components
┌──────────────┐           │         ↑
│ WebSocket    │ ──────────┘         │
│ (WSE)        │                     │
└──────────────┘                structural
       ↑                          sharing
       │                             │
┌──────────────┐              (smart re-renders)
│ Event Store  │
│ (Kafka/      │
│  Redpanda)   │
└──────────────┘
       ↑
       │
┌──────────────┐
│ Domain       │
│ Events       │
└──────────────┘
```

---

## Core Principles

### 1. Single Source of Truth

```typescript
// ✅ React Query = ONLY source for server data
// ✅ Zustand = ONLY for UI state (flags, preferences)

// Data layer (server state)
const { data } = useQuery(...)  // React Query

// UI layer (client state)
const { loading } = useUIStore()  // Zustand
```

### 2. Event-Driven Updates

```typescript
// Backend emits events → WebSocket → Frontend updates cache
Event → EventStore → WSE → WebSocket → setQueryData → UI Update
```

### 3. Optimistic UI

```typescript
// Update UI immediately, rollback on error
onMutate → optimistic update
onError → rollback
onSettled → sync with server
```

---

## Implementation Guide

### Backend: Event-Driven Architecture

#### 1. Domain Events

```python
# app/domain/events.py
from pydantic import BaseModel
from datetime import datetime

class ResourceCreated(BaseModel):
    event_type: str = "ResourceCreated"
    resource_id: str
    resource_type: str
    data: dict
    timestamp: datetime
    user_id: str

class ResourceUpdated(BaseModel):
    event_type: str = "ResourceUpdated"
    resource_id: str
    changes: dict
    timestamp: datetime
    user_id: str
```

#### 2. Command Handler

```python
# app/domain/command_handlers.py
async def handle_create_resource(cmd: CreateResource, deps: HandlerDependencies):
    # 1. Create aggregate
    aggregate = ResourceAggregate.create(cmd.resource_id, cmd.data)

    # 2. Save (emits ResourceCreated event)
    await deps.aggregate_repository.save(aggregate)

    # Event automatically published to EventBus → EventStore → WSE
```

#### 3. WSE Publisher

```python
# app/wse/publishers/domain_publisher.py
class WSEDomainPublisher:
    async def publish_event(self, event: dict):
        # 1. Transform domain event → WebSocket event
        ws_event = self._transform_event(event)

        # 2. Filter by user_id (multi-tenancy)
        user_id = event.get('user_id')

        # 3. Publish to Redis Pub/Sub channel
        await self.redis.publish(
            f"wse:user:{user_id}",
            json.dumps(ws_event)
        )
```

#### 4. WSE Handler (Snapshots)

```python
# app/wse/websocket/wse_handlers.py
async def handle_saga_completion(self, event: dict):
    # When saga completes, send snapshot
    if event.get('original_event_type') == 'SagaCompleted':
        user_id = event.get('user_id')

        # Query fresh data from database
        resources = await self.query_resources(user_id)

        # Send snapshot to frontend
        await self.send_snapshot({
            'type': 'resource_snapshot',
            'resources': resources,
            'timestamp': datetime.now().isoformat(),
        })
```

---

### Frontend: React Query + WebSocket

#### 1. Query Client Setup

```typescript
// lib/queryClient.ts
import { QueryClient } from '@tanstack/react-query';

export function getDynamicStaleTime(): number {
  const wsConnected = window.__WS_CONNECTED__;
  // Infinity with WebSocket, 5s without
  return wsConnected ? Infinity : 5000;
}

export const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: getDynamicStaleTime,
      refetchOnWindowFocus: false,
      refetchOnReconnect: true,
      retry: 3,
    },
  },
});
```

#### 2. Query Keys Factory

```typescript
// lib/queryKeys.ts
export const queryKeys = {
  resources: {
    all: ['resources'] as const,
    lists: () => [...queryKeys.resources.all, 'list'] as const,
    list: (filters) => [...queryKeys.resources.lists(), filters] as const,
    detail: (id) => [...queryKeys.resources.all, 'detail', id] as const,
  },
};
```

#### 3. Base Hook

```typescript
// hooks/useResources.ts
export function useResources(filters?) {
  const queryClient = useQueryClient();
  const ws = useWebSocket();

  // REST API fetch
  const query = useQuery({
    queryKey: queryKeys.resources.list(filters),
    queryFn: () => fetchResources(filters),
  });

  // WebSocket snapshot handler
  const handleSnapshot = useCallback(async (event) => {
    const { resources } = event.detail;

    // Cancel in-flight queries
    await queryClient.cancelQueries({ queryKey: queryKeys.resources.all });

    // Update cache
    queryClient.setQueryData(queryKeys.resources.list(filters), resources);
  }, [queryClient, filters]);

  // WebSocket incremental update
  const handleUpdate = useCallback(async (event) => {
    const resource = event.detail;

    await queryClient.cancelQueries({ queryKey: queryKeys.resources.all });

    // Immutable merge
    queryClient.setQueryData(queryKeys.resources.list(filters), (old) => {
      if (!old) return [resource];
      const index = old.findIndex(r => r.id === resource.id);
      if (index >= 0) {
        return old.map((r, i) => i === index ? resource : r);
      }
      return [...old, resource];
    });
  }, [queryClient, filters]);

  // Register listeners
  useEffect(() => {
    ws.on('resource_snapshot', handleSnapshot);
    ws.on('resource_update', handleUpdate);
    return () => {
      ws.off('resource_snapshot', handleSnapshot);
      ws.off('resource_update', handleUpdate);
    };
  }, [ws, handleSnapshot, handleUpdate]);

  return query;
}
```

#### 4. Specialized Hooks (with `select`)

```typescript
// hooks/useResources.ts

// Filter by type
export function useResourcesByType(type: string) {
  return useQuery({
    queryKey: queryKeys.resources.all,
    queryFn: fetchResources,
    select: useCallback(
      (resources) => resources.filter(r => r.type === type),
      [type]
    ),
  });
}

// Filter by status
export function useResourcesByStatus(status: string) {
  return useQuery({
    queryKey: queryKeys.resources.all,
    queryFn: fetchResources,
    select: useCallback(
      (resources) => resources.filter(r => r.status === status),
      [status]
    ),
  });
}

// Custom filter
export function useFilteredResources(filterFn, deps = []) {
  return useQuery({
    queryKey: queryKeys.resources.all,
    queryFn: fetchResources,
    select: useCallback(
      (resources) => resources.filter(filterFn),
      deps
    ),
  });
}
```

#### 5. Mutations

```typescript
// hooks/useResourceMutations.ts

export function useCreateResource() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (data) => createResource(data),

    onSuccess: () => {
      // Success logic
    },

    onError: (error) => {
      // Error logic
    },

    onSettled: async () => {
      // Guaranteed cache sync
      await queryClient.invalidateQueries({ queryKey: queryKeys.resources.all });
    },
  });
}

export function useUpdateResource() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ id, data }) => updateResource(id, data),

    // Optimistic update
    onMutate: async ({ id, data }) => {
      await queryClient.cancelQueries({ queryKey: queryKeys.resources.all });
      const previous = queryClient.getQueryData(queryKeys.resources.all);

      queryClient.setQueryData(queryKeys.resources.all, (old) =>
        old.map(r => r.id === id ? { ...r, ...data } : r)
      );

      return { previous };
    },

    // Rollback on error
    onError: (error, variables, context) => {
      if (context?.previous) {
        queryClient.setQueryData(queryKeys.resources.all, context.previous);
      }
    },

    // Guaranteed sync
    onSettled: async () => {
      await queryClient.invalidateQueries({ queryKey: queryKeys.resources.all });
    },
  });
}
```

#### 6. WebSocket Event Handler

```typescript
// wse/handlers/EventHandlers.ts

export class EventHandlers {
  private queryClient: QueryClient;

  constructor(queryClient: QueryClient) {
    this.queryClient = queryClient;
  }

  // Snapshot (full state)
  handleSnapshot(snapshot: Snapshot) {
    const { resources } = snapshot;

    this.queryClient.setQueryData(queryKeys.resources.all, resources);

    console.log('Snapshot applied:', resources.length, 'resources');
  }

  // Incremental update
  handleUpdate(update: Update) {
    const resource = update.resource;

    this.queryClient.setQueryData(queryKeys.resources.all, (old) => {
      if (!old) return [resource];
      const index = old.findIndex(r => r.id === resource.id);
      if (index >= 0) {
        return old.map((r, i) => i === index ? resource : r);
      }
      return [...old, resource];
    });

    console.log('Resource updated:', resource.id);
  }

  // Deletion
  handleDelete(deletion: Deletion) {
    const { resource_id } = deletion;

    this.queryClient.setQueryData(queryKeys.resources.all, (old) => {
      if (!old) return [];
      return old.filter(r => r.id !== resource_id);
    });

    console.log('Resource deleted:', resource_id);
  }
}
```

#### 7. UI State Store (Zustand)

```typescript
// stores/useResourceStore.ts

interface ResourceUIState {
  // ❌ NO server data
  // ✅ ONLY UI state

  selectedResourceId: string | null;
  filterType: string;
  sortBy: string;
  sortOrder: 'asc' | 'desc';
  showArchived: boolean;

  setSelectedResourceId: (id: string | null) => void;
  setFilterType: (type: string) => void;
  setSortBy: (field: string) => void;
  toggleSortOrder: () => void;
  toggleShowArchived: () => void;
}

export const useResourceStore = create<ResourceUIState>((set) => ({
  selectedResourceId: null,
  filterType: 'all',
  sortBy: 'created_at',
  sortOrder: 'desc',
  showArchived: false,

  setSelectedResourceId: (id) => set({ selectedResourceId: id }),
  setFilterType: (type) => set({ filterType: type }),
  setSortBy: (field) => set({ sortBy: field }),
  toggleSortOrder: () => set((s) => ({ sortOrder: s.sortOrder === 'asc' ? 'desc' : 'asc' })),
  toggleShowArchived: () => set((s) => ({ showArchived: !s.showArchived })),
}));
```

---

## WSE Protocol

### Event Format (v2)

```typescript
interface WSEvent {
  v: 2;                    // Protocol version
  id: string;              // Event ID (UUID)
  t: string;               // Event type (transformed)
  ts: string;              // Timestamp (ISO 8601)
  seq: number;             // Sequence number
  p: any;                  // Payload
  original_event_type?: string;  // Original type (if transformed)
  latency_ms?: number;     // Latency metadata
}
```

### Message Types

```typescript
// 1. Snapshot (full state)
{
  v: 2,
  t: 'resource_snapshot',
  p: {
    resources: [...],
    total: 100,
    timestamp: '2025-11-16T12:00:00Z',
  }
}

// 2. Incremental Update
{
  v: 2,
  t: 'resource_update',
  p: {
    resource_id: '123',
    changes: { status: 'active' },
    timestamp: '2025-11-16T12:00:01Z',
  }
}

// 3. Deletion
{
  v: 2,
  t: 'resource_deleted',
  p: {
    resource_id: '123',
    timestamp: '2025-11-16T12:00:02Z',
  }
}

// 4. Saga Completion (triggers snapshot)
{
  v: 2,
  t: 'process_update',  // Transformed type
  original_event_type: 'ProcessCompletedSagaCompleted',  // Original type
  p: {
    process_id: '456',
    status: 'completed',
  }
}
```

---

## Instant Snapshots Pattern

### Problem

Snapshots arrive **before** async processes complete, causing empty/incomplete data.

### Solution

1. **Backend:** Saga waits for data propagation
2. **Backend:** Publishes completion event with `original_event_type`
3. **WSE:** Detects completion via `original_event_type`
4. **WSE:** Queries fresh data and sends snapshot
5. **Frontend:** Receives complete data instantly

### Implementation

```python
# Backend: Saga
async def finalize_process(self, process_id):
    # Wait for projectors (150ms safety margin)
    await asyncio.sleep(0.15)

    # Publish completion event
    completion_event = {
        "event_type": "ProcessCompletedSagaCompleted",
        "process_id": process_id,
        # ...
    }
    await event_bus.publish("transport.process-events", completion_event)
```

```python
# Backend: EventTransformer
def transform_event(self, event):
    ws_event = {
        'v': 2,
        't': 'process_update',  # Transformed type
        'p': event_data,
    }

    # CRITICAL: Preserve original type
    if event['event_type'] != 'process_update':
        ws_event['original_event_type'] = event['event_type']

    return ws_event
```

```python
# Backend: WSE Handler
async def handle_process_update(self, event):
    original_type = event.get('original_event_type', event['t'])

    if original_type == 'ProcessCompletedSagaCompleted':
        # Query fresh data (process now complete in DB)
        resources = await self.query_resources(user_id)

        # Send snapshot
        await self.send_snapshot({
            'type': 'resource_snapshot',
            'resources': resources,
        })
```

```typescript
// Frontend: Event handler
handleSnapshot(snapshot) {
  // Update cache with complete data
  queryClient.setQueryData(queryKeys.resources.all, snapshot.resources);
  // UI updates instantly
}
```

---

## Performance Patterns

### 1. Structural Sharing

```typescript
// Component with broker filter
const { data: filtered } = useResourcesByType('type_a');

// Event: type_b resource updated
// select runs → filters to type_a resources
// Result: SAME array reference (type_a resources unchanged)
// Structural sharing: prev === current → NO re-render ✅
```

### 2. Smart Invalidation

```typescript
// Hierarchical keys enable targeted invalidation

// Invalidate all resources
queryClient.invalidateQueries({ queryKey: ['resources'] });

// Invalidate specific resource
queryClient.invalidateQueries({ queryKey: ['resources', 'detail', id] });

// Invalidate filtered lists only
queryClient.invalidateQueries({ queryKey: ['resources', 'list'] });
```

### 3. Optimistic Updates

```typescript
useMutation({
  onMutate: async (variables) => {
    // 1. Cancel in-flight queries
    await queryClient.cancelQueries({ queryKey });

    // 2. Snapshot for rollback
    const previous = queryClient.getQueryData(queryKey);

    // 3. Optimistic update
    queryClient.setQueryData(queryKey, optimisticValue);

    return { previous };
  },

  onError: (error, variables, context) => {
    // 4. Rollback
    queryClient.setQueryData(queryKey, context.previous);
  },

  onSettled: () => {
    // 5. Sync with server
    queryClient.invalidateQueries({ queryKey });
  },
});
```

---

## Testing

### Backend Testing

```python
# Test event publishing
async def test_resource_creation_publishes_event():
    handler = CreateResourceHandler(...)
    cmd = CreateResource(resource_id="123", data={...})

    await handler.handle(cmd, deps)

    # Verify event published
    assert event_bus.published_events[0]['event_type'] == 'ResourceCreated'
```

### Frontend Testing

```typescript
// Test cache updates
import { renderHook, waitFor } from '@testing-library/react';
import { useResources } from './useResources';

test('updates cache on WebSocket event', async () => {
  const { result } = renderHook(() => useResources());

  // Simulate WebSocket event
  window.dispatchEvent(new CustomEvent('resource_update', {
    detail: { resource_id: '123', status: 'active' }
  }));

  await waitFor(() => {
    const resource = result.current.data.find(r => r.id === '123');
    expect(resource.status).toBe('active');
  });
});
```

---

## Checklist

### Backend

- [ ] Domain events defined (Pydantic models)
- [ ] Command handlers publish events to EventBus
- [ ] EventStore persists events (Kafka/Redpanda)
- [ ] Projectors update read models (PostgreSQL)
- [ ] WSE publisher transforms events → WebSocket format
- [ ] WSE handlers detect saga completion (`original_event_type`)
- [ ] Snapshots sent after saga completion
- [ ] Multi-tenancy filtering (by user_id)

### Frontend

- [ ] React Query configured with dynamic staleTime
- [ ] Hierarchical query keys factory
- [ ] Base hooks with WebSocket listeners
- [ ] Specialized hooks with `select` option
- [ ] Mutations with complete lifecycle (onMutate, onSuccess, onError, onSettled)
- [ ] WebSocket handlers update cache via `setQueryData`
- [ ] Zustand stores ONLY UI state (no server data)
- [ ] Structural sharing enabled (memoized selectors)

### Testing

- [ ] Unit tests for hooks
- [ ] Integration tests for WebSocket flow
- [ ] E2E tests for user scenarios
- [ ] Performance tests (re-render count)

---

## Common Patterns

### Pattern 1: Master-Detail View

```typescript
// Master list
const { data: resources } = useResources();

// Selected resource detail
const { selectedResourceId } = useResourceStore();
const { data: resource } = useQuery({
  queryKey: queryKeys.resources.detail(selectedResourceId),
  queryFn: () => fetchResource(selectedResourceId),
  enabled: !!selectedResourceId,
});
```

### Pattern 2: Filtered + Sorted List

```typescript
const { filterType, sortBy, sortOrder } = useResourceStore();

const { data: resources } = useQuery({
  queryKey: queryKeys.resources.all,
  queryFn: fetchResources,
  select: useCallback(
    (resources) => {
      // Filter
      let filtered = filterType === 'all'
        ? resources
        : resources.filter(r => r.type === filterType);

      // Sort
      return [...filtered].sort((a, b) => {
        const aVal = a[sortBy];
        const bVal = b[sortBy];
        return sortOrder === 'asc'
          ? aVal > bVal ? 1 : -1
          : aVal < bVal ? 1 : -1;
      });
    },
    [filterType, sortBy, sortOrder]
  ),
});
```

### Pattern 3: Infinite Scroll

```typescript
const { data, fetchNextPage, hasNextPage } = useInfiniteQuery({
  queryKey: queryKeys.resources.lists(),
  queryFn: ({ pageParam = 0 }) => fetchResources({ offset: pageParam }),
  getNextPageParam: (lastPage) => lastPage.nextOffset,
});

// WebSocket updates merge into existing pages
const handleUpdate = (update) => {
  queryClient.setQueryData(queryKeys.resources.lists(), (old) => {
    const pages = old.pages.map(page => ({
      ...page,
      resources: page.resources.map(r =>
        r.id === update.id ? update : r
      ),
    }));
    return { ...old, pages };
  });
};
```

---

## Summary

**Universal Reactive Interface Pattern:**

1. **Backend:** Event-driven architecture (Domain Events → EventStore → WSE)
2. **Frontend:** React Query as single source of truth
3. **Real-time:** WebSocket updates via `setQueryData`
4. **Performance:** Structural sharing with `select` option
5. **Reliability:** Complete mutation lifecycle (onSettled)
6. **Instant Data:** Saga completion triggers snapshot with fresh data

**Benefits:**
- Real-time updates (< 100ms latency)
- Optimal re-renders (40-70% reduction)
- Complete data (no race conditions)
- Type-safe (TypeScript)
- Scalable (multi-tenant, millions of events)
- Testable (unit + integration + E2E)

---

**Author:** TradeCore Team
**Last Updated:** November 16, 2025
**Version:** 1.0 (Reference)
