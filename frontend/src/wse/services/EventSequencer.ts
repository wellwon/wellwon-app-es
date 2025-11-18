// =============================================================================
// File: src/wse/services/EventSequencer.ts
// Description: Event sequencing and deduplication service (FIXED)
// =============================================================================

import { logger } from '@/wse';

export class EventSequencer {
  private sequence = 0;
  private seenIds: Map<string, number>;
  private expectedSequence = 0;
  private outOfOrderBuffer: Map<number, any>;
  private readonly windowSize: number;
  private readonly maxOutOfOrder: number;
  private cleanupInterval: NodeJS.Timeout | null = null;

  // FIXED: Add cleanup counter for efficient deduplication
  private cleanupCounter = 0;
  private readonly CLEANUP_INTERVAL = 100; // Clean every 100 messages
  private readonly MAX_AGE_MS = 300000; // 5 minutes

  constructor(windowSize = 10000, maxOutOfOrder = 100) {
    this.windowSize = windowSize;
    this.maxOutOfOrder = maxOutOfOrder;
    this.seenIds = new Map();
    this.outOfOrderBuffer = new Map();

    // Periodic cleanup
    this.cleanupInterval = setInterval(() => {
      this.cleanup();
    }, 60000); // Every minute
  }

  // ─────────────────────────────────────────────────────────────────────────
  // Sequence Generation
  // ─────────────────────────────────────────────────────────────────────────

  getNextSequence(): number {
    return ++this.sequence;
  }

  getCurrentSequence(): number {
    return this.sequence;
  }

  // ─────────────────────────────────────────────────────────────────────────
  // FIXED: Efficient Deduplication
  // ─────────────────────────────────────────────────────────────────────────

  isDuplicate(eventId: string): boolean {
    const now = Date.now();

    if (this.seenIds.has(eventId)) {
      return true;
    }

    this.seenIds.set(eventId, now);
    this.cleanupCounter++;

    // FIXED: Periodic cleanup instead of size-based
    if (this.cleanupCounter >= this.CLEANUP_INTERVAL) {
      this.cleanupCounter = 0;
      this.cleanupOldEntries();
    }

    return false;
  }

  private cleanupOldEntries(): void {
    const cutoff = Date.now() - this.MAX_AGE_MS;
    let removed = 0;

    // Remove old entries
    for (const [id, timestamp] of this.seenIds) {
      if (timestamp < cutoff) {
        this.seenIds.delete(id);
        removed++;
      }
    }

    // Also enforce max size if still too large
    if (this.seenIds.size > this.windowSize * 1.5) {
      const excess = this.seenIds.size - this.windowSize;
      const entries = Array.from(this.seenIds.entries())
        .sort((a, b) => a[1] - b[1])
        .slice(0, excess);

      entries.forEach(([id]) => {
        this.seenIds.delete(id);
        removed++;
      });
    }

    if (removed > 0) {
      logger.debug(`Cleaned up ${removed} old event IDs`);
    }
  }

  // ─────────────────────────────────────────────────────────────────────────
  // Sequence Ordering
  // ─────────────────────────────────────────────────────────────────────────

  recordSequence(sequence: number): void {
    this.expectedSequence = Math.max(this.expectedSequence, sequence + 1);
  }

  processSequencedEvent(sequence: number, event: any): any[] | null {
    // If this is the expected sequence
    if (sequence === this.expectedSequence) {
      const eventsToDeliver = [event];
      this.expectedSequence = sequence + 1;

      // Check if we can deliver buffered events
      while (this.outOfOrderBuffer.has(this.expectedSequence)) {
        const bufferedEvent = this.outOfOrderBuffer.get(this.expectedSequence);
        this.outOfOrderBuffer.delete(this.expectedSequence);
        eventsToDeliver.push(bufferedEvent);
        this.expectedSequence++;
      }

      return eventsToDeliver;
    }

    // If this is a future event
    if (sequence > this.expectedSequence) {
      // Check if too far ahead
      if (sequence - this.expectedSequence > this.maxOutOfOrder) {
        logger.warn(`Event sequence ${sequence} too far ahead of expected ${this.expectedSequence}`);
        // Reset expected sequence
        this.expectedSequence = sequence + 1;
        this.outOfOrderBuffer.clear();
        return [event];
      }

      // Buffer the event
      this.outOfOrderBuffer.set(sequence, {
        ...event,
        _bufferedAt: Date.now() // Add timestamp for cleanup
      });
      return null;
    }

    // If this is an old event, skip it
    logger.debug(`Skipping old event with sequence ${sequence}, expected ${this.expectedSequence}`);
    return null;
  }

  // ─────────────────────────────────────────────────────────────────────────
  // Statistics
  // ─────────────────────────────────────────────────────────────────────────

  getStats(): {
    currentSequence: number;
    expectedSequence: number;
    duplicateWindowSize: number;
    outOfOrderBufferSize: number;
    largestGap: number;
  } {
    let largestGap = 0;

    if (this.outOfOrderBuffer.size > 0) {
      const sequences = Array.from(this.outOfOrderBuffer.keys()).sort((a, b) => a - b);
      largestGap = sequences[0] - this.expectedSequence;
    }

    return {
      currentSequence: this.sequence,
      expectedSequence: this.expectedSequence,
      duplicateWindowSize: this.seenIds.size,
      outOfOrderBufferSize: this.outOfOrderBuffer.size,
      largestGap,
    };
  }

  // ─────────────────────────────────────────────────────────────────────────
  // FIXED: Improved Cleanup
  // ─────────────────────────────────────────────────────────────────────────

  private cleanup(): void {
    try {
      const now = Date.now();
      const maxAge = 5 * 60 * 1000; // 5 minutes

      // Clean up old buffered events
      let removedBuffered = 0;
      for (const [seq, event] of this.outOfOrderBuffer) {
        const bufferedAt = event._bufferedAt || event.timestamp;
        if (bufferedAt && now - bufferedAt > maxAge) {
          this.outOfOrderBuffer.delete(seq);
          removedBuffered++;
        }
      }

      if (removedBuffered > 0) {
        logger.debug(`Removed ${removedBuffered} old buffered events`);
      }

      // Clean up old seen IDs if not done recently
      if (this.cleanupCounter > 0) {
        this.cleanupOldEntries();
      }

      // Log stats if we have buffered events
      if (this.outOfOrderBuffer.size > 0) {
        logger.debug('EventSequencer stats:', this.getStats());
      }

    } catch (error) {
      logger.error('Error in EventSequencer cleanup:', error);
    }
  }

  destroy(): void {
    // Clear the interval first
    if (this.cleanupInterval) {
      clearInterval(this.cleanupInterval);
      this.cleanupInterval = null;
    }

    // Clear all data structures
    this.seenIds.clear();
    this.outOfOrderBuffer.clear();

    // Reset counters
    this.sequence = 0;
    this.expectedSequence = 0;
    this.cleanupCounter = 0;

    logger.debug('EventSequencer destroyed');
  }

  reset(): void {
    this.sequence = 0;
    this.expectedSequence = 0;
    this.seenIds.clear();
    this.outOfOrderBuffer.clear();
    this.cleanupCounter = 0;

    logger.debug('EventSequencer reset');
  }
}