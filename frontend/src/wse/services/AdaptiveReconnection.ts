// =============================================================================
// File: src/wse/services/AdaptiveReconnection.ts
// Description: Adaptive reconnection strategy for WebSocket connections
// =============================================================================

export class AdaptiveReconnection {
  private history: Array<{
    timestamp: number;
    duration: number;
    success: boolean;
    endpoint: string;
  }> = [];

  private attempts = 0;
  private config: {
    mode: string;
    baseDelay: number;
    maxDelay: number;
    factor: number;
    jitter: boolean;
  };

  constructor(config: any) {
    this.config = config;
  }

  recordAttempt(endpoint: string, success: boolean, duration: number): void {
    this.history.push({
      timestamp: Date.now(),
      duration,
      success,
      endpoint,
    });

    // Keep only last 100 attempts
    if (this.history.length > 100) {
      this.history.shift();
    }

    if (success) {
      this.attempts = 0;
    } else {
      this.attempts++;
    }
  }

  getNextDelay(): number {
    let delay: number;

    switch (this.config.mode) {
      case 'exponential':
        delay = Math.min(
          this.config.maxDelay,
          this.config.baseDelay * Math.pow(this.config.factor, this.attempts)
        );
        break;

      case 'linear':
        delay = Math.min(
          this.config.maxDelay,
          this.config.baseDelay + (this.attempts * 1000)
        );
        break;

      case 'fibonacci': {
        const fib = (n: number): number => n <= 1 ? n : fib(n - 1) + fib(n - 2);
        delay = Math.min(
          this.config.maxDelay,
          this.config.baseDelay * fib(Math.min(this.attempts, 10))
        );
        break;
      }

      case 'adaptive': {
        // Analyze recent history
        const recent = this.history.slice(-10);
        const failures = recent.filter(h => !h.success).length;

        if (failures > 7) {
          // Many recent failures - use longer delays
          delay = Math.min(
            this.config.maxDelay * 2,
            Math.pow(2, this.attempts) * 5000
          );
        } else if (failures > 4) {
          // Some failures - moderate delays
          delay = Math.min(
            this.config.maxDelay,
            Math.pow(1.5, this.attempts) * 2000
          );
        } else {
          // Few failures - standard delays
          delay = Math.min(
            this.config.maxDelay,
            Math.pow(1.5, this.attempts) * 1000
          );
        }
        break;
      }

      default:
        delay = this.config.baseDelay;
    }

    // Add jitter if enabled
    if (this.config.jitter) {
      const jitter = delay * 0.2 * (Math.random() - 0.5);
      delay = Math.max(0, delay + jitter);
    }

    return delay;
  }

  getCurrentDelay(): number {
    return this.getNextDelay();
  }

  getHistory(): Array<{
    timestamp: number;
    duration: number;
    success: boolean;
    endpoint: string;
  }> {
    return [...this.history];
  }

  reset(): void {
    this.attempts = 0;
    this.history = [];
  }

  destroy(): void {
    this.reset();
  }
}