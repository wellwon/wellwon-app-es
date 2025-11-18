# Frontend Reference Guide

**Practical guide for building reactive UIs with WebSocket Engine + React Query**

This reference guide provides reusable patterns, code examples, and best practices for implementing TradeCore's reactive UI architecture in any project (SecureOS, task management, monitoring dashboards, etc.).

---

## Table of Contents

- [Quick Start](#quick-start)
- [For SecureOS / Other Projects](#for-secureos--other-projects)
- [Core Patterns](#core-patterns)
- [Generic Examples](#generic-examples)
- [API Reference](#api-reference)
- [Troubleshooting](#troubleshooting)
- [Further Reading](#further-reading)

---

## Quick Start

**5-minute setup for reactive UI:**

### 1. Install Dependencies

```bash
npm install @tanstack/react-query axios
```

### 2. Configure React Query Client

```typescript
// src/lib/queryClient.ts
import { QueryClient } from '@tanstack/react-query';

export const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 5000,        // 5s default (override with WSE events)
      gcTime: 10 * 60 * 1000, // 10 minutes
      retry: 1,
      refetchOnWindowFocus: false,
      refetchOnReconnect: true,
    },
  },
});
```

### 3. Wrap App with QueryClientProvider

```tsx
// src/main.tsx
import { QueryClientProvider } from '@tanstack/react-query';
import { queryClient } from './lib/queryClient';

function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <YourApp />
    </QueryClientProvider>
  );
}
```

### 4. Create Your First Reactive Hook

```typescript
// src/hooks/useTask.ts
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { useEffect } from 'react';
import { wseApi } from '../api/wse';
import { fetchTask } from '../api/tasks';

export function useTask(taskId: string) {
  const queryClient = useQueryClient();

  // STEP 1: React Query (REST API primary)
  const query = useQuery({
    queryKey: ['task', taskId],
    queryFn: () => fetchTask(taskId),
  });

  // STEP 2: WSE Event Listener (real-time updates)
  useEffect(() => {
    const unsubscribe = wseApi.on('task.updated', (event) => {
      if (event.p.task_id === taskId) {
        queryClient.invalidateQueries({ queryKey: ['task', taskId] });
      }
    });
    return unsubscribe;
  }, [taskId, queryClient]);

  return query;
}
```

### 5. Use in Component

```tsx
// src/components/TaskDetail.tsx
import { useTask } from '../hooks/useTask';

export function TaskDetail({ taskId }: { taskId: string }) {
  const { data: task, isLoading, error } = useTask(taskId);

  if (isLoading) return <div>Loading...</div>;
  if (error) return <div>Error: {error.message}</div>;

  return (
    <div>
      <h1>{task.title}</h1>
      <p>Status: {task.status}</p>
    </div>
  );
}
```

**Result**: Your UI automatically updates when backend emits `task.updated` event. No polling required.

---

## For SecureOS / Other Projects

### Architecture Overview

TradeCore's reactive UI architecture is **domain-agnostic** and can be adapted to any real-time application:

```
┌─────────────────────────────────────────────────────────────┐
│  BACKEND (Python/FastAPI)                                   │
│  ┌────────────┐    ┌──────────────┐    ┌────────────────┐ │
│  │   Domain   │───▶│  Event Bus   │───▶│  WSE Publisher │ │
│  │ Aggregates │    │  (Redpanda)  │    │  (MessagePack) │ │
│  └────────────┘    └──────────────┘    └────────┬───────┘ │
└─────────────────────────────────────────────────┼─────────┘
                                                   │ WebSocket
┌─────────────────────────────────────────────────┼─────────┐
│  FRONTEND (React/TypeScript)                    │         │
│  ┌─────────────┐    ┌──────────────────┐   ┌───▼──────┐  │
│  │    REST     │    │   WSE Client     │   │  Event   │  │
│  │     API     │    │  (WebSocket)     │───│ Handlers │  │
│  └──────┬──────┘    └──────────────────┘   └────┬─────┘  │
│         │                                        │         │
│  ┌──────▼────────────────────────────────────────▼──────┐ │
│  │           React Query Cache                          │ │
│  │  (Single Source of Truth for UI State)              │ │
│  └──────┬───────────────────────────────────────────────┘ │
│         │                                                  │
│  ┌──────▼──────┐                                          │
│  │  Components │                                          │
│  └─────────────┘                                          │
└──────────────────────────────────────────────────────────┘
```

### Key Principles

1. **REST API is Primary** - All reads start with REST API call
2. **WebSocket is Secondary** - Events invalidate cache, triggering automatic refetch
3. **No Polling** - Events eliminate need for continuous polling
4. **Cache as SSOT** - React Query cache is single source of truth
5. **Optimistic Updates** - UI updates immediately, rolls back on error

### Adapting for Your Project

**For SecureOS (System Monitoring):**
```typescript
// Replace "tasks" with "processes" or "services"
useProcess(processId)  // Monitor system processes
useService(serviceId)  // Monitor system services
useLog(logId)          // Real-time log streaming
```

**For E-Commerce:**
```typescript
// Replace "tasks" with "orders" or "inventory"
useOrder(orderId)      // Real-time order tracking
useInventory(sku)      // Live inventory updates
useCart(userId)        // Shopping cart sync
```

**For Chat Application:**
```typescript
// Replace "tasks" with "messages" or "channels"
useMessages(channelId) // Real-time message updates
useChannel(channelId)  // Channel state sync
usePresence(userId)    // User online status
```

**Key Adaptation Points:**
1. **Event names**: `task.updated` → `process.updated` / `order.updated`
2. **Query keys**: `['task', taskId]` → `['process', processId]`
3. **API endpoints**: `/api/tasks` → `/api/processes`
4. **Domain models**: `Task` → `Process` / `Order` / `Message`

---

## Core Patterns

### Pattern 1: Dynamic StaleTime (TkDodo Best Practice)

**Problem**: Polling wastes server resources when WebSocket provides real-time updates.

**Solution**: Set `staleTime: Infinity` when WebSocket connected, aggressive refetch when disconnected.

```typescript
// src/lib/queryClient.ts
import { useWSEStore } from '../stores/wseStore';

export function getDynamicStaleTime(): number {
  const wseStore = (window as any).__WSE_STORE__;
  const isConnected = wseStore?.getState?.()?.connectionState === 'CONNECTED';
  return isConnected ? Infinity : 5000; // Infinity when WS active, 5s fallback
}

// Usage in hook
const query = useQuery({
  queryKey: ['task', taskId],
  queryFn: () => fetchTask(taskId),
  staleTime: getDynamicStaleTime(), // Dynamic based on WebSocket state
});
```

**Result**: 90% reduction in server requests when WebSocket connected.

---

### Pattern 2: Event-Driven Cache Invalidation

**Problem**: How to know when to refetch data without polling?

**Solution**: WebSocket events trigger cache invalidation, React Query automatically refetches.

```typescript
// Event → Invalidate → Auto-refetch
useEffect(() => {
  const unsubscribe = wseApi.on('task.updated', (event) => {
    if (event.p.task_id === taskId) {
      // Invalidate cache → React Query auto-refetches
      queryClient.invalidateQueries({ queryKey: ['task', taskId] });
    }
  });
  return unsubscribe;
}, [taskId, queryClient]);
```

**Advanced**: Conditional invalidation strategies

```typescript
// Strategy 1: Full invalidation (all tasks)
queryClient.invalidateQueries({ queryKey: ['tasks'] });

// Strategy 2: Partial invalidation (specific task only)
queryClient.invalidateQueries({ queryKey: ['task', taskId] });

// Strategy 3: Optimistic update + refetch
queryClient.setQueryData(['task', taskId], (old) => ({
  ...old,
  status: event.p.status, // Optimistic update
}));
queryClient.invalidateQueries({ queryKey: ['task', taskId] }); // Verify

// Strategy 4: Conditional invalidation (only if user is viewing)
const isActive = document.visibilityState === 'visible';
if (isActive) {
  queryClient.invalidateQueries({ queryKey: ['task', taskId] });
}
```

---

### Pattern 3: Optimistic Updates with Rollback

**Problem**: UI feels sluggish waiting for server confirmation.

**Solution**: Update UI immediately, roll back on error.

```typescript
// src/hooks/useUpdateTask.ts
import { useMutation, useQueryClient } from '@tanstack/react-query';

export function useUpdateTask() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (params: { taskId: string; status: string }) =>
      updateTask(params.taskId, params.status),

    // Optimistic update (immediate UI change)
    onMutate: async ({ taskId, status }) => {
      // Cancel ongoing queries
      await queryClient.cancelQueries({ queryKey: ['task', taskId] });

      // Snapshot current state (for rollback)
      const previousTask = queryClient.getQueryData(['task', taskId]);

      // Optimistically update cache
      queryClient.setQueryData(['task', taskId], (old: any) => ({
        ...old,
        status, // Immediate UI update
      }));

      return { previousTask }; // Return rollback context
    },

    // Rollback on error
    onError: (err, { taskId }, context) => {
      queryClient.setQueryData(['task', taskId], context?.previousTask);
    },

    // Refetch on success (verify server state)
    onSuccess: (data, { taskId }) => {
      queryClient.invalidateQueries({ queryKey: ['task', taskId] });
    },
  });
}
```

**Usage**:
```tsx
const updateTask = useUpdateTask();

<button onClick={() => updateTask.mutate({ taskId: '123', status: 'completed' })}>
  Complete Task
</button>
```

**Result**: UI updates instantly, rolls back if server rejects.

---

### Pattern 4: Aggressive Polling After State Change

**Problem**: Snapshots may arrive before REST API updates (eventual consistency).

**Solution**: Temporarily increase refetch frequency after state changes.

```typescript
// src/hooks/useTask.ts
const [aggressivePolling, setAggressivePolling] = useState(false);

const query = useQuery({
  queryKey: ['task', taskId],
  queryFn: () => fetchTask(taskId),
  refetchInterval: aggressivePolling ? 2000 : 30000, // 2s → 30s
});

useEffect(() => {
  const unsubscribe = wseApi.on('task.updated', (event) => {
    if (event.p.task_id === taskId) {
      // Aggressive polling for 10 seconds
      setAggressivePolling(true);
      setTimeout(() => setAggressivePolling(false), 10000);

      queryClient.invalidateQueries({ queryKey: ['task', taskId] });
    }
  });
  return unsubscribe;
}, [taskId]);
```

**Result**: UI stays in sync even with eventual consistency delays.

---

### Pattern 5: Snapshot Detection Heuristic

**Problem**: How to distinguish snapshot events from real-time updates?

**Solution**: Use event metadata and timing heuristics.

```typescript
// Snapshot detection logic
const isLikelySnapshot = (event: WSEEvent): boolean => {
  // Heuristic 1: Bulk events (multiple entities in short time)
  const recentEvents = eventBuffer.filter(e =>
    Date.now() - e.timestamp < 1000
  );
  if (recentEvents.length > 5) return true;

  // Heuristic 2: Event metadata (if backend provides)
  if (event.meta?.is_snapshot) return true;

  // Heuristic 3: No changes (state matches cache)
  const cached = queryClient.getQueryData(['task', event.p.task_id]);
  if (JSON.stringify(cached) === JSON.stringify(event.p)) return true;

  return false;
};

// Use in handler
useEffect(() => {
  const unsubscribe = wseApi.on('task.updated', (event) => {
    if (isLikelySnapshot(event)) {
      // Debounce snapshots (batch invalidate)
      debounceInvalidate(['tasks']);
    } else {
      // Immediate invalidation for real-time updates
      queryClient.invalidateQueries({ queryKey: ['task', event.p.task_id] });
    }
  });
  return unsubscribe;
}, []);
```

---

## Generic Examples

### Example 1: Task Management System

**Complete implementation of reactive task list:**

#### Backend Events (Python)
```python
# app/task/events.py
class TaskCreatedEvent(BaseEvent):
    event_type: Literal["TaskCreatedEvent"] = "TaskCreatedEvent"
    task_id: UUID
    title: str
    status: str
    created_at: datetime

class TaskUpdatedEvent(BaseEvent):
    event_type: Literal["TaskUpdatedEvent"] = "TaskUpdatedEvent"
    task_id: UUID
    title: str | None = None
    status: str | None = None
    updated_at: datetime

# app/infra/reactive_bus/wse_monitoring_publisher.py
async def publish_task_events(task_id: UUID, event: TaskUpdatedEvent):
    """Publish task events to WSE"""
    await wse_publisher.publish_event(
        event_type="task.updated",
        payload={
            "task_id": str(task_id),
            "title": event.title,
            "status": event.status,
            "updated_at": event.updated_at.isoformat(),
        }
    )
```

#### Frontend Implementation

**API Layer:**
```typescript
// src/api/tasks.ts
import axios from 'axios';

const api = axios.create({ baseURL: '/api' });

export interface Task {
  id: string;
  title: string;
  status: 'pending' | 'in_progress' | 'completed';
  created_at: string;
  updated_at: string;
}

export async function fetchTasks(): Promise<Task[]> {
  const { data } = await api.get('/tasks');
  return data;
}

export async function fetchTask(taskId: string): Promise<Task> {
  const { data } = await api.get(`/tasks/${taskId}`);
  return data;
}

export async function createTask(title: string): Promise<Task> {
  const { data } = await api.post('/tasks', { title });
  return data;
}

export async function updateTask(taskId: string, status: string): Promise<Task> {
  const { data } = await api.patch(`/tasks/${taskId}`, { status });
  return data;
}
```

**Hooks:**
```typescript
// src/hooks/useTasks.ts
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { useEffect } from 'react';
import { wseApi } from '../api/wse';
import { fetchTasks } from '../api/tasks';

export function useTasks() {
  const queryClient = useQueryClient();

  const query = useQuery({
    queryKey: ['tasks'],
    queryFn: fetchTasks,
  });

  // Listen for task events
  useEffect(() => {
    const unsubscribeCreated = wseApi.on('task.created', () => {
      queryClient.invalidateQueries({ queryKey: ['tasks'] });
    });

    const unsubscribeUpdated = wseApi.on('task.updated', () => {
      queryClient.invalidateQueries({ queryKey: ['tasks'] });
    });

    const unsubscribeDeleted = wseApi.on('task.deleted', () => {
      queryClient.invalidateQueries({ queryKey: ['tasks'] });
    });

    return () => {
      unsubscribeCreated();
      unsubscribeUpdated();
      unsubscribeDeleted();
    };
  }, [queryClient]);

  return query;
}

// src/hooks/useTask.ts
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { useEffect } from 'react';
import { wseApi } from '../api/wse';
import { fetchTask } from '../api/tasks';

export function useTask(taskId: string) {
  const queryClient = useQueryClient();

  const query = useQuery({
    queryKey: ['task', taskId],
    queryFn: () => fetchTask(taskId),
    enabled: !!taskId,
  });

  useEffect(() => {
    const unsubscribe = wseApi.on('task.updated', (event) => {
      if (event.p.task_id === taskId) {
        queryClient.invalidateQueries({ queryKey: ['task', taskId] });
      }
    });
    return unsubscribe;
  }, [taskId, queryClient]);

  return query;
}

// src/hooks/useCreateTask.ts
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { createTask } from '../api/tasks';

export function useCreateTask() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (title: string) => createTask(title),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['tasks'] });
    },
  });
}

// src/hooks/useUpdateTask.ts
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { updateTask } from '../api/tasks';

export function useUpdateTask() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ taskId, status }: { taskId: string; status: string }) =>
      updateTask(taskId, status),

    // Optimistic update
    onMutate: async ({ taskId, status }) => {
      await queryClient.cancelQueries({ queryKey: ['task', taskId] });
      const previous = queryClient.getQueryData(['task', taskId]);

      queryClient.setQueryData(['task', taskId], (old: any) => ({
        ...old,
        status,
      }));

      return { previous };
    },

    onError: (err, { taskId }, context) => {
      queryClient.setQueryData(['task', taskId], context?.previous);
    },

    onSuccess: (data, { taskId }) => {
      queryClient.invalidateQueries({ queryKey: ['task', taskId] });
      queryClient.invalidateQueries({ queryKey: ['tasks'] });
    },
  });
}
```

**Components:**
```tsx
// src/components/TaskList.tsx
import { useTasks } from '../hooks/useTasks';
import { useCreateTask } from '../hooks/useCreateTask';
import { TaskItem } from './TaskItem';

export function TaskList() {
  const { data: tasks, isLoading, error } = useTasks();
  const createTask = useCreateTask();

  const handleCreate = () => {
    const title = prompt('Enter task title:');
    if (title) {
      createTask.mutate(title);
    }
  };

  if (isLoading) return <div>Loading tasks...</div>;
  if (error) return <div>Error: {error.message}</div>;

  return (
    <div>
      <button onClick={handleCreate}>Create Task</button>
      <div>
        {tasks?.map((task) => (
          <TaskItem key={task.id} task={task} />
        ))}
      </div>
    </div>
  );
}

// src/components/TaskItem.tsx
import { useUpdateTask } from '../hooks/useUpdateTask';
import { Task } from '../api/tasks';

export function TaskItem({ task }: { task: Task }) {
  const updateTask = useUpdateTask();

  const handleStatusChange = (status: string) => {
    updateTask.mutate({ taskId: task.id, status });
  };

  return (
    <div>
      <h3>{task.title}</h3>
      <p>Status: {task.status}</p>
      <button onClick={() => handleStatusChange('in_progress')}>
        Start
      </button>
      <button onClick={() => handleStatusChange('completed')}>
        Complete
      </button>
    </div>
  );
}

// src/components/TaskDetail.tsx
import { useTask } from '../hooks/useTask';
import { useUpdateTask } from '../hooks/useUpdateTask';

export function TaskDetail({ taskId }: { taskId: string }) {
  const { data: task, isLoading, error } = useTask(taskId);
  const updateTask = useUpdateTask();

  if (isLoading) return <div>Loading task...</div>;
  if (error) return <div>Error: {error.message}</div>;
  if (!task) return <div>Task not found</div>;

  return (
    <div>
      <h1>{task.title}</h1>
      <p>Status: {task.status}</p>
      <p>Created: {new Date(task.created_at).toLocaleString()}</p>
      <p>Updated: {new Date(task.updated_at).toLocaleString()}</p>

      <select
        value={task.status}
        onChange={(e) => updateTask.mutate({
          taskId: task.id,
          status: e.target.value
        })}
      >
        <option value="pending">Pending</option>
        <option value="in_progress">In Progress</option>
        <option value="completed">Completed</option>
      </select>
    </div>
  );
}
```

**Result**:
- UI updates automatically when other users change task status
- No polling required
- Optimistic updates for instant feedback
- Automatic rollback on errors

---

### Example 2: Real-Time Monitoring Dashboard (SecureOS)

**Monitoring system processes with WebSocket updates:**

```typescript
// src/hooks/useProcesses.ts
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { useEffect } from 'react';
import { wseApi } from '../api/wse';

export function useProcesses() {
  const queryClient = useQueryClient();

  const query = useQuery({
    queryKey: ['processes'],
    queryFn: async () => {
      const response = await fetch('/api/processes');
      return response.json();
    },
    refetchInterval: 30000, // Fallback polling every 30s
  });

  useEffect(() => {
    // Real-time process events
    const unsubscribe = wseApi.on('process.status_changed', (event) => {
      // Optimistic update for instant feedback
      queryClient.setQueryData(['processes'], (old: any) => {
        if (!old) return old;
        return old.map((p: any) =>
          p.id === event.p.process_id
            ? { ...p, status: event.p.status, cpu: event.p.cpu, memory: event.p.memory }
            : p
        );
      });
    });

    return unsubscribe;
  }, [queryClient]);

  return query;
}

// Usage in component
export function ProcessMonitor() {
  const { data: processes } = useProcesses();

  return (
    <table>
      <thead>
        <tr>
          <th>Process</th>
          <th>Status</th>
          <th>CPU</th>
          <th>Memory</th>
        </tr>
      </thead>
      <tbody>
        {processes?.map((process) => (
          <tr key={process.id}>
            <td>{process.name}</td>
            <td>{process.status}</td>
            <td>{process.cpu}%</td>
            <td>{process.memory}MB</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}
```

---

## API Reference

### React Query Hooks

#### useQuery
```typescript
const query = useQuery({
  queryKey: string[],           // Cache key (e.g., ['task', '123'])
  queryFn: () => Promise<T>,    // Fetch function
  staleTime?: number,           // Cache freshness (default: 5000ms)
  gcTime?: number,              // Garbage collection (default: 10min)
  enabled?: boolean,            // Conditional fetching
  refetchInterval?: number,     // Polling interval (use sparingly)
});

// Returns:
query.data         // Fetched data
query.isLoading    // Initial loading state
query.isFetching   // Background refetch state
query.error        // Error object
query.refetch()    // Manual refetch
```

#### useMutation
```typescript
const mutation = useMutation({
  mutationFn: (params: T) => Promise<R>,
  onMutate?: (params) => Promise<Context>,  // Optimistic update
  onError?: (err, params, context) => void, // Rollback
  onSuccess?: (data, params) => void,       // Invalidate cache
});

// Usage:
mutation.mutate(params);
mutation.isLoading
mutation.isError
mutation.error
```

#### useQueryClient
```typescript
const queryClient = useQueryClient();

// Cache operations
queryClient.invalidateQueries({ queryKey: ['task', taskId] });
queryClient.setQueryData(['task', taskId], newData);
queryClient.getQueryData(['task', taskId]);
queryClient.removeQueries({ queryKey: ['tasks'] });
queryClient.cancelQueries({ queryKey: ['task', taskId] });
```

---

### WSE Client API

#### Connection Management
```typescript
wseApi.connect()              // Establish WebSocket connection
wseApi.disconnect()           // Close connection
wseApi.getConnectionState()   // 'CONNECTED' | 'DISCONNECTED' | 'CONNECTING'
```

#### Event Handlers
```typescript
// Subscribe to event
const unsubscribe = wseApi.on('event.type', (event) => {
  console.log(event.p); // Event payload
});

// Unsubscribe
unsubscribe();

// One-time handler
wseApi.once('event.type', handler);

// Remove all handlers for event type
wseApi.off('event.type');
```

#### Request/Response
```typescript
// Send request, wait for response
const response = await wseApi.request('task.get', { task_id: '123' });

// Send command (no response expected)
wseApi.send('task.update', { task_id: '123', status: 'completed' });
```

---

## Troubleshooting

### Issue 1: UI Not Updating After WebSocket Event

**Symptoms**: WebSocket event received, but UI doesn't update.

**Diagnosis**:
```typescript
// Add logging to event handler
useEffect(() => {
  const unsubscribe = wseApi.on('task.updated', (event) => {
    console.log('Event received:', event);
    console.log('Invalidating:', ['task', event.p.task_id]);
    queryClient.invalidateQueries({ queryKey: ['task', event.p.task_id] });
  });
  return unsubscribe;
}, [queryClient]);
```

**Common Causes**:
1. **Query key mismatch**: Event uses `task_id`, query key uses `taskId`
2. **Stale closure**: `queryClient` not in dependency array
3. **Missing refetchOnMount**: Query disabled or data already cached

**Solutions**:
```typescript
// Solution 1: Ensure query key consistency
const queryKey = ['task', taskId]; // Use same format everywhere

// Solution 2: Force refetch after invalidation
queryClient.invalidateQueries({
  queryKey: ['task', taskId],
  refetchType: 'active', // Only refetch if query is mounted
});

// Solution 3: Set query data directly (optimistic)
queryClient.setQueryData(['task', taskId], event.p);
```

---

### Issue 2: Too Many Refetches

**Symptoms**: Network tab shows excessive requests, UI flickering.

**Diagnosis**:
```typescript
// Enable React Query DevTools
import { ReactQueryDevtools } from '@tanstack/react-query-devtools';

<ReactQueryDevtools initialIsOpen={false} />
```

**Common Causes**:
1. **Aggressive refetchInterval**: Polling too frequently
2. **Missing staleTime**: Every render triggers refetch
3. **Event storm**: Too many invalidations

**Solutions**:
```typescript
// Solution 1: Use dynamic staleTime
staleTime: getDynamicStaleTime(), // Infinity when WS connected

// Solution 2: Debounce invalidations
const debounceInvalidate = debounce((queryKey) => {
  queryClient.invalidateQueries({ queryKey });
}, 500);

// Solution 3: Conditional invalidation
if (document.visibilityState === 'visible') {
  queryClient.invalidateQueries({ queryKey: ['tasks'] });
}
```

---

### Issue 3: WebSocket Connection Drops

**Symptoms**: Events stop arriving, UI reverts to polling.

**Diagnosis**:
```typescript
// Monitor connection state
const connectionState = useWSEStore((state) => state.connectionState);

useEffect(() => {
  console.log('WebSocket state:', connectionState);
}, [connectionState]);
```

**Common Causes**:
1. **Network instability**: WiFi drops, server restarts
2. **Idle timeout**: Server closes inactive connections
3. **Authentication expired**: JWT token expired

**Solutions**:
```typescript
// Solution 1: Auto-reconnect with exponential backoff
wseApi.on('disconnect', () => {
  setTimeout(() => wseApi.connect(), 1000);  // 1s
  setTimeout(() => wseApi.connect(), 5000);  // 5s
  setTimeout(() => wseApi.connect(), 15000); // 15s
});

// Solution 2: Heartbeat/ping
setInterval(() => {
  if (wseApi.getConnectionState() === 'CONNECTED') {
    wseApi.send('ping', {});
  }
}, 30000); // Every 30s

// Solution 3: Fallback to aggressive polling
const query = useQuery({
  queryKey: ['tasks'],
  queryFn: fetchTasks,
  refetchInterval: connectionState === 'CONNECTED' ? false : 5000,
});
```

---

### Issue 4: Stale Data After Optimistic Update

**Symptoms**: UI shows optimistic update, but doesn't revert to server state.

**Diagnosis**:
```typescript
// Check if refetch happens after optimistic update
onSuccess: (data, { taskId }) => {
  console.log('Mutation success, invalidating...');
  queryClient.invalidateQueries({ queryKey: ['task', taskId] });
}
```

**Common Causes**:
1. **Missing invalidation**: Forgot to invalidate after success
2. **staleTime too high**: Cache never considered stale
3. **No refetchOnMount**: Query doesn't refetch when re-rendered

**Solutions**:
```typescript
// Solution 1: Always invalidate after mutation
onSuccess: () => {
  queryClient.invalidateQueries({ queryKey: ['task', taskId] });
}

// Solution 2: Force immediate refetch
onSuccess: async () => {
  await queryClient.refetchQueries({ queryKey: ['task', taskId] });
}

// Solution 3: Set server data directly
onSuccess: (serverData) => {
  queryClient.setQueryData(['task', taskId], serverData);
}
```

---

### Issue 5: Memory Leak from Event Listeners

**Symptoms**: Console warning "Can't perform state update on unmounted component".

**Diagnosis**:
```typescript
// Check if cleanup function is called
useEffect(() => {
  const unsubscribe = wseApi.on('task.updated', handler);

  return () => {
    console.log('Cleanup called'); // Should log when component unmounts
    unsubscribe();
  };
}, []);
```

**Common Causes**:
1. **Missing cleanup**: Forgot to return unsubscribe function
2. **Stale closure**: Handler references old state/props
3. **Multiple subscriptions**: Component re-renders create duplicate listeners

**Solutions**:
```typescript
// Solution 1: Always return cleanup function
useEffect(() => {
  const unsubscribe = wseApi.on('event', handler);
  return unsubscribe; // Critical!
}, []);

// Solution 2: Use useCallback to avoid stale closures
const handler = useCallback((event) => {
  queryClient.invalidateQueries({ queryKey: ['task', event.p.task_id] });
}, [queryClient]);

useEffect(() => {
  const unsubscribe = wseApi.on('task.updated', handler);
  return unsubscribe;
}, [handler]);

// Solution 3: Cleanup on unmount
useEffect(() => {
  return () => {
    wseApi.off('task.updated'); // Remove all handlers
  };
}, []);
```

---

## Further Reading

### Official Documentation
- **React Query (TanStack Query)**: https://tanstack.com/query/latest/docs/react/overview
- **TkDodo Blog (React Query Guru)**: https://tkdodo.eu/blog/practical-react-query
- **WebSocket API**: https://developer.mozilla.org/en-US/docs/Web/API/WebSocket

### TradeCore Documentation
- **Frontend Architecture**: `/docs/mvp/FRONTEND_ARCHITECTURE.md` - High-level overview
- **WSE + React Query Integration**: `/docs/mvp/WSE_REACT_QUERY_INTEGRATION.md` - Integration patterns
- **Reactive UI Best Practices**: `/docs/mvp/REACTIVE_UI_BEST_PRACTICES.md` - TkDodo patterns

### TkDodo's Essential Posts
1. **Practical React Query** - https://tkdodo.eu/blog/practical-react-query
2. **React Query and Forms** - https://tkdodo.eu/blog/react-query-and-forms
3. **React Query Error Handling** - https://tkdodo.eu/blog/react-query-error-handling
4. **Effective React Query Keys** - https://tkdodo.eu/blog/effective-react-query-keys
5. **Testing React Query** - https://tkdodo.eu/blog/testing-react-query

### Related Technologies
- **MessagePack**: https://msgpack.org/ - Binary serialization format
- **Zustand**: https://github.com/pmndrs/zustand - Lightweight state management
- **Vite**: https://vitejs.dev/ - Next-generation frontend tooling

---

## Contributing to This Guide

Found an issue or want to add examples? This reference guide is open for contributions:

1. **Add new examples**: Create PRs with generic, reusable patterns
2. **Improve troubleshooting**: Add common issues you've encountered
3. **Update API reference**: Keep in sync with React Query v5+ changes
4. **Translate**: Help make this guide available in other languages

---

**Happy Building! 🚀**

For questions, check `/docs/mvp/` for architectural theory or open an issue in the TradeCore repository.
