// =============================================================================
// File: src/wse/services/EventSequencer.ts (FIXED VERSION)
// Description: Fixed event sequencing matching backend implementation
// =============================================================================

import { logger } from '@/wse';

interface SequencedEvent {
  id: string;
  sequence: number;
  timestamp: number;
  data?: any;
}

export class EventSequencer {
  private sequence = 0;
  private seenIds: Map<string, number>; // id -> timestamp
  private expectedSequence = 0;
  private outOfOrderBuffer: Map<number, any>;
  private readonly windowSize: number;
  private readonly maxOutOfOrder: number;
  private cleanupInterval: NodeJS.Timeout;

  constructor(windowSize = 10000, maxOutOfOrder = 100) {
    this.windowSize = windowSize;
    this.maxOutOfOrder = maxOutOfOrder;
    this.seenIds = new Map();
    this.outOfOrderBuffer = new Map();

    // Periodic cleanup matching backend
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
  // Deduplication - matching backend window logic
  // ─────────────────────────────────────────────────────────────────────────

  isDuplicate(eventId: string): boolean {
    const now = Date.now();

    if (this.seenIds.has(eventId)) {
      return true;
    }

    this.seenIds.set(eventId, now);

    // Maintain window size by removing old entries
    if (this.seenIds.size > this.windowSize) {
      // Remove oldest entries
      const sortedEntries = Array.from(this.seenIds.entries())
        .sort((a, b) => a[1] - b[1]);

      const toRemove = sortedEntries.slice(0, this.seenIds.size - this.windowSize);
      toRemove.forEach(([id]) => this.seenIds.delete(id));
    }

    return false;
  }

  // ─────────────────────────────────────────────────────────────────────────
  // Sequence Ordering - matching backend logic
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
      // Check if too far ahead - matching backend logic
      if (sequence - this.expectedSequence > this.maxOutOfOrder) {
        logger.warn(`Event sequence ${sequence} too far ahead of expected ${this.expectedSequence}`);
        // Reset expected sequence
        this.expectedSequence = sequence + 1;
        this.outOfOrderBuffer.clear();
        return [event];
      }

      // Buffer the event
      this.outOfOrderBuffer.set(sequence, event);
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
      if (sequences.length > 0) {
        largestGap = sequences[0] - this.expectedSequence;
      }
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
  // Cleanup - matching backend implementation
  // ─────────────────────────────────────────────────────────────────────────

  private cleanup(): void {
    const now = Date.now();
    const maxAge = 5 * 60 * 1000; // 5 minutes - matching backend

    // Clean up old-seen IDs
    const idsToRemove: string[] = [];
    this.seenIds.forEach((timestamp, id) => {
      if (now - timestamp > maxAge) {
        idsToRemove.push(id);
      }
    });
    idsToRemove.forEach(id => this.seenIds.delete(id));

    // Clean up old buffered events
    const sequencesToRemove: number[] = [];
    this.outOfOrderBuffer.forEach((event, seq) => {
      if (event.timestamp && now - event.timestamp > maxAge) {
        sequencesToRemove.push(seq);
      }
    });
    sequencesToRemove.forEach(seq => this.outOfOrderBuffer.delete(seq));

    // Log stats if we have buffered events
    if (this.outOfOrderBuffer.size > 0) {
      logger.debug('EventSequencer stats:', this.getStats());
    }
  }

  destroy(): void {
    if (this.cleanupInterval) {
      clearInterval(this.cleanupInterval);
    }

    this.seenIds.clear();
    this.outOfOrderBuffer.clear();
  }

  reset(): void {
    this.sequence = 0;
    this.expectedSequence = 0;
    this.seenIds.clear();
    this.outOfOrderBuffer.clear();
  }
}
