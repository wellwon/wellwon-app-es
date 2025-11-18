// =============================================================================
// File: src/wse/services/RateLimiter.ts
// Description: Rate limiting service for WebSocket connections
// =============================================================================

import { logger } from '@/wse';

export class RateLimiter {
  private tokens: number;
  private lastRefill: number;
  private readonly capacity: number;
  private readonly refillRate: number;
  private readonly refillInterval: number;

  constructor(
    capacity: number = 1000,
    refillRate: number = 100,
    refillInterval: number = 1000 // milliseconds
  ) {
    this.capacity = capacity;
    this.refillRate = refillRate;
    this.refillInterval = refillInterval;
    this.tokens = capacity;
    this.lastRefill = Date.now();
  }

  // ─────────────────────────────────────────────────────────────────────────
  // Rate Limiting
  // ─────────────────────────────────────────────────────────────────────────

  canSend(): boolean {
    this.refill();

    if (this.tokens >= 1) {
      this.tokens--;
      return true;
    }

    return false;
  }

  tryConsume(tokens: number = 1): boolean {
    this.refill();

    if (this.tokens >= tokens) {
      this.tokens -= tokens;
      return true;
    }

    return false;
  }

  private refill(): void {
    const now = Date.now();
    const timePassed = now - this.lastRefill;

    if (timePassed >= this.refillInterval) {
      const intervalsElapsed = Math.floor(timePassed / this.refillInterval);
      const tokensToAdd = intervalsElapsed * this.refillRate;

      this.tokens = Math.min(this.capacity, this.tokens + tokensToAdd);
      this.lastRefill = now - (timePassed % this.refillInterval);
    }
  }

  // ─────────────────────────────────────────────────────────────────────────
  // Utilities
  // ─────────────────────────────────────────────────────────────────────────

  getRetryAfter(): number {
    if (this.tokens >= 1) {
      return 0;
    }

    const now = Date.now();
    const timeSinceLastRefill = now - this.lastRefill;
    const timeUntilNextRefill = this.refillInterval - timeSinceLastRefill;

    // Calculate when we have at least 1 token
    const tokensNeeded = 1 - this.tokens;
    const refillsNeeded = Math.ceil(tokensNeeded / this.refillRate);
    const totalWaitTime = (refillsNeeded - 1) * this.refillInterval + timeUntilNextRefill;

    return Math.max(0, totalWaitTime / 1000); // Return in seconds
  }

  getAvailableTokens(): number {
    this.refill();
    return this.tokens;
  }

  getCapacity(): number {
    return this.capacity;
  }

  getUtilization(): number {
    return ((this.capacity - this.tokens) / this.capacity) * 100;
  }

  reset(): void {
    this.tokens = this.capacity;
    this.lastRefill = Date.now();
  }

  // ─────────────────────────────────────────────────────────────────────────
  // Statistics
  // ─────────────────────────────────────────────────────────────────────────

  getStats(): {
    availableTokens: number;
    capacity: number;
    utilizationPercent: number;
    refillRate: number;
    refillInterval: number;
    retryAfter: number;
  } {
    this.refill();

    return {
      availableTokens: this.tokens,
      capacity: this.capacity,
      utilizationPercent: this.getUtilization(),
      refillRate: this.refillRate,
      refillInterval: this.refillInterval,
      retryAfter: this.getRetryAfter(),
    };
  }
}

// ─────────────────────────────────────────────────────────────────────────
// User-based Rate Limiter
// ─────────────────────────────────────────────────────────────────────────

export class UserRateLimiter {
  private userLimiters: Map<string, RateLimiter> = new Map();
  private readonly defaultCapacity: number;
  private readonly defaultRefillRate: number;
  private readonly premiumCapacity: number;
  private readonly premiumRefillRate: number;
  private cleanupInterval: NodeJS.Timeout;

  constructor(
    defaultCapacity: number = 1000,
    defaultRefillRate: number = 100,
    premiumCapacity: number = 5000,
    premiumRefillRate: number = 500
  ) {
    this.defaultCapacity = defaultCapacity;
    this.defaultRefillRate = defaultRefillRate;
    this.premiumCapacity = premiumCapacity;
    this.premiumRefillRate = premiumRefillRate;

    // Cleanup inactive users every hour
    this.cleanupInterval = setInterval(() => {
      this.cleanup();
    }, 3600000);
  }

  checkUser(userId: string, isPremium: boolean = false): boolean {
    const limiter = this.getLimiterForUser(userId, isPremium);
    return limiter.canSend();
  }

  private getLimiterForUser(userId: string, isPremium: boolean): RateLimiter {
    if (!this.userLimiters.has(userId)) {
      const capacity = isPremium ? this.premiumCapacity : this.defaultCapacity;
      const refillRate = isPremium ? this.premiumRefillRate : this.defaultRefillRate;
      this.userLimiters.set(userId, new RateLimiter(capacity, refillRate));
    }

    return this.userLimiters.get(userId)!;
  }

  getUserRetryAfter(userId: string): number {
    const limiter = this.userLimiters.get(userId);
    return limiter ? limiter.getRetryAfter() : 0;
  }

  private cleanup(): void {
    // Remove limiters that haven't been used recently
    // In a real implementation, track last access time
    logger.debug(`Cleaning up ${this.userLimiters.size} user rate limiters`);

    // For now, clear all if too many
    if (this.userLimiters.size > 10000) {
      this.userLimiters.clear();
    }
  }

  destroy(): void {
    if (this.cleanupInterval) {
      clearInterval(this.cleanupInterval);
    }
    this.userLimiters.clear();
  }
}