/**
 * Централизованная система логирования для WellWon
 * Простая и эффективная система без внешних зависимостей
 */

export type LogLevel = 'debug' | 'info' | 'warn' | 'error';

export interface LogContext {
  component?: string;
  action?: string;
  userId?: string;
  timestamp?: string;
  metadata?: Record<string, unknown>;
  // Дополнительные поля для более гибкого логирования
  [key: string]: unknown;
}

interface ErrorLog {
  message: string;
  stack?: string;
  timestamp: Date;
  url: string;
  userAgent: string;
}

class Logger {
  private isDevelopment = import.meta.env.DEV;
  private isLogging = false; // Защита от циклического логирования
  
  constructor() {
    if (!this.isDevelopment) {
      this.setupGlobalErrorHandling();
    }
  }
  
  private setupGlobalErrorHandling() {
    window.addEventListener('error', (event) => {
      if (!this.isLogging) {
        this.isLogging = true;
        try {
          this.logToStorage({
            message: event.message,
            stack: event.error?.stack,
            timestamp: new Date(),
            url: window.location.href,
            userAgent: navigator.userAgent
          });
        } catch (e) {
          // Игнорируем ошибки в логгере
        } finally {
          this.isLogging = false;
        }
      }
    });
    
    window.addEventListener('unhandledrejection', (event) => {
      if (!this.isLogging) {
        this.isLogging = true;
        try {
          this.logToStorage({
            message: `Unhandled Promise Rejection: ${event.reason}`,
            timestamp: new Date(),
            url: window.location.href,
            userAgent: navigator.userAgent
          });
        } catch (e) {
          // Игнорируем ошибки в логгере
        } finally {
          this.isLogging = false;
        }
      }
    });
  }
  
  private logToStorage(error: ErrorLog) {
    if (this.isLogging) return;
    
    try {
      // Security: Sanitize error data before storing
      const sanitizedError = {
        ...error,
        message: this.sanitizeMessage(error.message),
        url: new URL(error.url).pathname, // Only path, no query params
        userAgent: error.userAgent.substring(0, 100) // Limit length
      };
      
      const errors = JSON.parse(localStorage.getItem('production-errors') || '[]');
      errors.push(sanitizedError);
      localStorage.setItem('production-errors', JSON.stringify(errors.slice(-5))); // Reduced to 5
    } catch (e) {
      // Игнорируем ошибки при сохранении
    }
  }

  // Очистка сообщений от потенциально чувствительных данных
  private sanitizeMessage(message: string): string {
    return message
      .replace(/user_id[:\s]*[0-9a-f-]{36}/gi, 'user_id: [REDACTED]')
      .replace(/email[:\s]*[\w.-]+@[\w.-]+/gi, 'email: [REDACTED]')  
      .replace(/phone[:\s]*[\d\s+()-]+/gi, 'phone: [REDACTED]')
      .replace(/\b\d{10,}\b/g, '[NUMBER_REDACTED]');
  }
  
  private formatMessage(level: LogLevel, message: string, context?: LogContext): string {
    const timestamp = new Date().toISOString();
    const prefix = context?.component ? `[${context.component}]` : '';
    return `${timestamp} ${level.toUpperCase()} ${prefix} ${message}`;
  }

  debug(message: string, context?: LogContext) {
    if (this.isDevelopment) {
      console.debug(this.formatMessage('debug', message, context), context?.metadata);
    }
  }

  info(message: string, context?: LogContext) {
    const formattedMessage = this.formatMessage('info', message, context);
    
    if (this.isDevelopment) {
      console.info(formattedMessage, context?.metadata);
    }
  }

  warn(message: string, context?: LogContext) {
    const formattedMessage = this.formatMessage('warn', message, context);
    
    if (this.isDevelopment) {
      console.warn(formattedMessage, context?.metadata);
    }
  }

  error(message: string, error?: Error | unknown, context?: LogContext) {
    const formattedMessage = this.formatMessage('error', message, context);
    
    if (this.isDevelopment) {
      console.error(formattedMessage, error, context?.metadata);
    }
    
    if (!this.isDevelopment && !this.isLogging) {
      this.logToStorage({
        message: formattedMessage,
        stack: error instanceof Error ? error.stack : undefined,
        timestamp: new Date(),
        url: window.location.href,
        userAgent: navigator.userAgent
      });
    }
  }

  // Методы для специфичных случаев использования
  authEvent(event: string, success: boolean, context?: Omit<LogContext, 'component'>) {
    const message = `Auth event: ${event} - ${success ? 'SUCCESS' : 'FAILED'}`;
    if (success) {
      this.info(message, { ...context, component: 'Auth' });
    } else {
      this.warn(message, { ...context, component: 'Auth' });
    }
  }

  apiCall(method: string, url: string, status: number, duration?: number, context?: Omit<LogContext, 'component'>) {
    const message = `API ${method} ${url} - ${status} ${duration ? `(${duration}ms)` : ''}`;
    const logContext = { ...context, component: 'API' };
    
    if (status >= 200 && status < 300) {
      this.info(message, logContext);
    } else if (status >= 400) {
      this.error(message, undefined, logContext);
    } else {
      this.warn(message, logContext);
    }
  }

  userAction(action: string, component: string, context?: LogContext) {
    this.info(`User action: ${action}`, { ...context, component, action });
  }

  performance(metric: string, value: number, unit: string = 'ms', context?: LogContext) {
    this.info(`Performance: ${metric} = ${value}${unit}`, { ...context, component: 'Performance' });
  }
}

// Экспортируем singleton instance
export const logger = new Logger();

// Утилитарные функции для быстрого доступа
export const logDebug = (message: string, context?: LogContext) => logger.debug(message, context);
export const logInfo = (message: string, context?: LogContext) => logger.info(message, context);
export const logWarn = (message: string, context?: LogContext) => logger.warn(message, context);
export const logErr = (message: string, error?: Error | unknown, context?: LogContext) => logger.error(message, error, context);