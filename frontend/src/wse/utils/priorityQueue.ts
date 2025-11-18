// =============================================================================
// File: src/wse/utils/priorityQueue.ts
// Description: Priority queue implementation for message handling
// =============================================================================

import { MessagePriority } from '@/wse';

export interface PriorityItem<T> {
  priority: MessagePriority;
  item: T;
  timestamp: number;
}

export class PriorityQueue<T> {
  private queues: Map<MessagePriority, PriorityItem<T>[]>;
  private totalSize = 0;
  private readonly maxSize: number;

  constructor(maxSize = 10000) {
    this.maxSize = maxSize;
    this.queues = new Map([
      [MessagePriority.CRITICAL, []],
      [MessagePriority.HIGH, []],
      [MessagePriority.NORMAL, []],
      [MessagePriority.LOW, []],
      [MessagePriority.BACKGROUND, []],
    ]);
  }

  // ─────────────────────────────────────────────────────────────────────────
  // Queue Operations
  // ─────────────────────────────────────────────────────────────────────────

  enqueue(item: T, priority: MessagePriority = MessagePriority.NORMAL): boolean {
    if (this.totalSize >= this.maxSize) {
      // Try to make room by removing the lowest priority item
      if (!this.makeRoom(priority)) {
        return false;
      }
    }

    const queue = this.queues.get(priority);
    if (!queue) {
      throw new Error(`Invalid priority: ${priority}`);
    }

    queue.push({
      priority,
      item,
      timestamp: Date.now(),
    });

    this.totalSize++;
    return true;
  }

  dequeue(): T | undefined {
    // Process from highest to lowest priority
    const priorities = [
      MessagePriority.CRITICAL,
      MessagePriority.HIGH,
      MessagePriority.NORMAL,
      MessagePriority.LOW,
      MessagePriority.BACKGROUND,
    ];

    for (const priority of priorities) {
      const queue = this.queues.get(priority);
      if (queue && queue.length > 0) {
        const item = queue.shift();
        if (item) {
          this.totalSize--;
          return item.item;
        }
      }
    }

    return undefined;
  }

  dequeueBatch(count: number): T[] {
    const batch: T[] = [];

    while (batch.length < count && this.totalSize > 0) {
      const item = this.dequeue();
      if (item !== undefined) {
        batch.push(item);
      } else {
        break;
      }
    }

    return batch;
  }

  peek(): T | undefined {
    const priorities = [
      MessagePriority.CRITICAL,
      MessagePriority.HIGH,
      MessagePriority.NORMAL,
      MessagePriority.LOW,
      MessagePriority.BACKGROUND,
    ];

    for (const priority of priorities) {
      const queue = this.queues.get(priority);
      if (queue && queue.length > 0) {
        return queue[0].item;
      }
    }

    return undefined;
  }

  // ─────────────────────────────────────────────────────────────────────────
  // Utility Methods
  // ─────────────────────────────────────────────────────────────────────────

  private makeRoom(incomingPriority: MessagePriority): boolean {
    // Try to remove the lowest priority item
    const priorities = [
      MessagePriority.BACKGROUND,
      MessagePriority.LOW,
      MessagePriority.NORMAL,
      MessagePriority.HIGH,
      MessagePriority.CRITICAL,
    ];

    for (const priority of priorities) {
      // Don't remove items of higher or equal priority
      if (priority >= incomingPriority) {
        break;
      }

      const queue = this.queues.get(priority);
      if (queue && queue.length > 0) {
        queue.shift(); // Remove the oldest item of this priority
        this.totalSize--;
        return true;
      }
    }

    return false;
  }

  size(): number {
    return this.totalSize;
  }

  isEmpty(): boolean {
    return this.totalSize === 0;
  }

  isFull(): boolean {
    return this.totalSize >= this.maxSize;
  }

  clear(): void {
    this.queues.forEach(queue => queue.length = 0);
    this.totalSize = 0;
  }

  // ─────────────────────────────────────────────────────────────────────────
  // Statistics
  // ─────────────────────────────────────────────────────────────────────────

  getStats(): {
    totalSize: number;
    maxSize: number;
    distribution: Record<MessagePriority, number>;
    oldestMessageAge: number | null;
    utilizationPercent: number;
  } {
    const distribution: Record<MessagePriority, number> = {} as any;
    let oldestTimestamp = Date.now();

    this.queues.forEach((queue, priority) => {
      distribution[priority] = queue.length;

      if (queue.length > 0) {
        const queueOldest = Math.min(...queue.map(item => item.timestamp));
        oldestTimestamp = Math.min(oldestTimestamp, queueOldest);
      }
    });

    const oldestMessageAge = this.totalSize > 0
      ? Date.now() - oldestTimestamp
      : null;

    return {
      totalSize: this.totalSize,
      maxSize: this.maxSize,
      distribution,
      oldestMessageAge,
      utilizationPercent: (this.totalSize / this.maxSize) * 100,
    };
  }

  getItemsByPriority(priority: MessagePriority): T[] {
    const queue = this.queues.get(priority);
    return queue ? queue.map(item => item.item) : [];
  }

  removeOldItems(maxAgeMs: number): number {
    const now = Date.now();
    let removedCount = 0;

    this.queues.forEach(queue => {
      const initialLength = queue.length;
      const filtered = queue.filter(item => now - item.timestamp <= maxAgeMs);

      removedCount += initialLength - filtered.length;
      queue.length = 0;
      queue.push(...filtered);
    });

    this.totalSize -= removedCount;
    return removedCount;
  }

  // ─────────────────────────────────────────────────────────────────────────
  // Iterator
  // ─────────────────────────────────────────────────────────────────────────

  *[Symbol.iterator](): Iterator<T> {
    const priorities = [
      MessagePriority.CRITICAL,
      MessagePriority.HIGH,
      MessagePriority.NORMAL,
      MessagePriority.LOW,
      MessagePriority.BACKGROUND,
    ];

    for (const priority of priorities) {
      const queue = this.queues.get(priority);
      if (queue) {
        for (const item of queue) {
          yield item.item;
        }
      }
    }
  }

  toArray(): T[] {
    return Array.from(this);
  }
}