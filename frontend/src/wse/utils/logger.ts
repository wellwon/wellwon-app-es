// =============================================================================
// File: src/wse/utils/logger.ts
// Description: Logging utility for WebSocket Event System
// =============================================================================

export enum LogLevel {
  DEBUG = 0,
  INFO = 1,
  WARN = 2,
  ERROR = 3,
  NONE = 4,
}

export interface LogEntry {
  level: LogLevel;
  timestamp: Date;
  message: string;
  context?: string;
  data?: any;
  error?: Error;
}

class Logger {
  private level: LogLevel = LogLevel.INFO;
  private context: string;
  private history: LogEntry[] = [];
  private maxHistorySize = 1000;
  private isDevelopment: boolean;

  constructor(context: string = 'WSE') {
    this.context = context;

    // Fix: Use import.meta.env for Vite instead of process.env
    this.isDevelopment = import.meta.env?.DEV || false;

    // Set log level from the environment
    const envLevel = import.meta.env?.VITE_LOG_LEVEL;
    if (envLevel && envLevel in LogLevel) {
      this.level = LogLevel[envLevel as keyof typeof LogLevel];
    }
  }

  // ─────────────────────────────────────────────────────────────────────────
  // Logging Methods
  // ─────────────────────────────────────────────────────────────────────────

  debug(message: string, data?: any): void {
    this.log(LogLevel.DEBUG, message, data);
  }

  info(message: string, data?: any): void {
    this.log(LogLevel.INFO, message, data);
  }

  warn(message: string, data?: any): void {
    this.log(LogLevel.WARN, message, data);
  }

  error(message: string, error?: Error | any, data?: any): void {
    if (error instanceof Error) {
      this.log(LogLevel.ERROR, message, { ...data, error: error.message, stack: error.stack }, error);
    } else {
      this.log(LogLevel.ERROR, message, { ...data, error });
    }
  }

  // ─────────────────────────────────────────────────────────────────────────
  // Core Logging
  // ─────────────────────────────────────────────────────────────────────────

  private log(level: LogLevel, message: string, data?: any, error?: Error): void {
    if (level < this.level) return;

    const entry: LogEntry = {
      level,
      timestamp: new Date(),
      message,
      context: this.context,
      data,
      error,
    };

    // Add to history
    this.addToHistory(entry);

    // Format message
    const formattedMessage = this.formatMessage(entry);

    // Output to console
    switch (level) {
      case LogLevel.DEBUG:
        console.debug(formattedMessage, data);
        break;
      case LogLevel.INFO:
        console.info(formattedMessage, data);
        break;
      case LogLevel.WARN:
        console.warn(formattedMessage, data);
        break;
      case LogLevel.ERROR:
        console.error(formattedMessage, data, error);
        break;
    }

    // In production, could send it to a logging service
    if (!this.isDevelopment && level >= LogLevel.ERROR) {
      this.sendToLoggingService(entry);
    }
  }

  private formatMessage(entry: LogEntry): string {
    const timestamp = entry.timestamp.toISOString();
    const level = LogLevel[entry.level];
    return `[${timestamp}] [${level}] [${entry.context}] ${entry.message}`;
  }

  private addToHistory(entry: LogEntry): void {
    this.history.push(entry);

    // Maintain history size
    if (this.history.length > this.maxHistorySize) {
      this.history = this.history.slice(-this.maxHistorySize);
    }
  }

  // ─────────────────────────────────────────────────────────────────────────
  // Configuration
  // ─────────────────────────────────────────────────────────────────────────

  setLevel(level: LogLevel): void {
    this.level = level;
  }

  getLevel(): LogLevel {
    return this.level;
  }

  setContext(context: string): void {
    this.context = context;
  }

  child(context: string): Logger {
    const childLogger = new Logger(`${this.context}:${context}`);
    childLogger.setLevel(this.level);
    return childLogger;
  }

  // ─────────────────────────────────────────────────────────────────────────
  // History & Diagnostics
  // ─────────────────────────────────────────────────────────────────────────

  getHistory(level?: LogLevel): LogEntry[] {
    if (level !== undefined) {
      return this.history.filter(entry => entry.level === level);
    }
    return [...this.history];
  }

  clearHistory(): void {
    this.history = [];
  }

  exportHistory(): string {
    return this.history
      .map(entry => {
        const message = this.formatMessage(entry);
        if (entry.data) {
          return `${message}\n  Data: ${JSON.stringify(entry.data, null, 2)}`;
        }
        return message;
      })
      .join('\n');
  }

  downloadHistory(): void {
    const content = this.exportHistory();
    const blob = new Blob([content], { type: 'text/plain' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `wse-log-${Date.now()}.txt`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  }

  // ─────────────────────────────────────────────────────────────────────────
  // External Logging Service
  // ─────────────────────────────────────────────────────────────────────────

  private sendToLoggingService(entry: LogEntry): void {
    // In production, send to external service
    // Example: Sentry, LogRocket, etc.

    // For now, store in localStorage for debugging
    try {
      const key = 'wse_error_logs';
      const existing = localStorage.getItem(key);
      const logs = existing ? JSON.parse(existing) : [];

      logs.push({
        ...entry,
        timestamp: entry.timestamp.toISOString(),
      });

      // Keep only the last 100 errors
      if (logs.length > 100) {
        logs.splice(0, logs.length - 100);
      }

      localStorage.setItem(key, JSON.stringify(logs));
    } catch (error) {
      // Ignore storage errors
    }
  }

  // ─────────────────────────────────────────────────────────────────────────
  // Performance Monitoring
  // ─────────────────────────────────────────────────────────────────────────

  time(label: string): void {
    if (this.level <= LogLevel.DEBUG) {
      console.time(`[${this.context}] ${label}`);
    }
  }

  timeEnd(label: string): void {
    if (this.level <= LogLevel.DEBUG) {
      console.timeEnd(`[${this.context}] ${label}`);
    }
  }

  measure<T>(label: string, fn: () => T): T {
    if (this.level > LogLevel.DEBUG) {
      return fn();
    }

    const start = performance.now();
    try {
      const result = fn();
      const duration = performance.now() - start;
      this.debug(`${label} took ${duration.toFixed(2)}ms`);
      return result;
    } catch (error) {
      const duration = performance.now() - start;
      this.error(`${label} failed after ${duration.toFixed(2)}ms`, error as Error);
      throw error;
    }
  }

  async measureAsync<T>(label: string, fn: () => Promise<T>): Promise<T> {
    if (this.level > LogLevel.DEBUG) {
      return fn();
    }

    const start = performance.now();
    try {
      const result = await fn();
      const duration = performance.now() - start;
      this.debug(`${label} took ${duration.toFixed(2)}ms`);
      return result;
    } catch (error) {
      const duration = performance.now() - start;
      this.error(`${label} failed after ${duration.toFixed(2)}ms`, error as Error);
      throw error;
    }
  }
}

// Create default logger instance
export const logger = new Logger();

// Export for creating child loggers
export { Logger };