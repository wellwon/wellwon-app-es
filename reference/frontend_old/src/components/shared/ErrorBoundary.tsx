
import React, { Component, ErrorInfo, ReactNode } from 'react';
import { GlassButton } from '@/components/design-system';
import { AlertTriangle, RefreshCw, Home } from 'lucide-react';
import { logger } from '@/utils/logger';
import { safeNavigate } from '@/utils/navigationHelper';

interface Props {
  children: ReactNode;
  fallback?: ReactNode;
  translations?: {
    unexpectedErrorTitle: string;
    unexpectedErrorDescription: string;
    technicalInfo: string;
    retry: string;
    goHome: string;
    errorId: string;
  };
}

interface State {
  hasError: boolean;
  error?: Error;
  errorInfo?: ErrorInfo;
  errorId: string;
}

class ErrorBoundary extends Component<Props, State> {
  private retryCount = 0;
  private maxRetries = 3;

  constructor(props: Props) {
    super(props);
    this.state = {
      hasError: false,
      errorId: '',
    };
  }

  static getDerivedStateFromError(error: Error): Partial<State> {
    const errorId = `error_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
    return {
      hasError: true,
      error,
      errorId,
    };
  }

  componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    // Безопасное логирование с защитой от циклов
    try {
      logger.error('React Error Boundary caught an error', error, {
        component: 'ErrorBoundary',
        metadata: {
          errorId: this.state.errorId,
          componentStack: errorInfo.componentStack.substring(0, 500), // Ограничиваем размер
          retryCount: this.retryCount,
          userAgent: navigator.userAgent.substring(0, 200), // Ограничиваем размер
          url: window.location.href,
          timestamp: new Date().toISOString(),
          reactVersion: React.version || 'unknown',
          strictMode: import.meta.env.DEV ? 'disabled in dev' : 'enabled',
        }
      });
    } catch (loggingError) {
      // Если логирование не работает, сохраняем в консоль
      logger.error('ErrorBoundary caught error', error, { component: 'ErrorBoundary' });
      logger.error('Logging failed', loggingError, { component: 'ErrorBoundary' });
    }

    this.setState({
      errorInfo,
    });

    // Упрощенная отправка в мониторинг
    this.reportToMonitoringService(error, errorInfo);
  }

  private reportToMonitoringService(error: Error, errorInfo: ErrorInfo) {
    // Здесь можно интегрировать с Sentry, LogRocket и т.д.
    logger.info('Error reported to monitoring service', {
      component: 'ErrorBoundary',
      metadata: {
        errorId: this.state.errorId,
        message: error.message,
        stack: error.stack,
      }
    });
  }

  handleRetry = () => {
    if (this.retryCount < this.maxRetries) {
      this.retryCount++;
      logger.info(`Error boundary retry attempt ${this.retryCount}`, {
        component: 'ErrorBoundary',
        metadata: { errorId: this.state.errorId }
      });
      
      this.setState({
        hasError: false,
        error: undefined,
        errorInfo: undefined,
      });
    } else {
      logger.warn('Max retry attempts reached', {
        component: 'ErrorBoundary',
        metadata: { errorId: this.state.errorId, maxRetries: this.maxRetries }
      });
    }
  };

  handleReload = () => {
    logger.info('Reloading from ErrorBoundary', { component: 'ErrorBoundary' });
    // Soft reset state instead of page reload
    this.setState({
      hasError: false,
      error: undefined,
      errorInfo: undefined,
    });
    this.retryCount = 0;
  };

  handleGoHome = () => {
    logger.info('Navigating home from ErrorBoundary', { component: 'ErrorBoundary' });
    safeNavigate('/');
    // Also reset error state
    this.setState({ hasError: false, error: undefined, errorInfo: undefined });
    this.retryCount = 0;
  };

  render() {
    if (this.state.hasError) {
      if (this.props.fallback) {
        return this.props.fallback;
      }

      const canRetry = this.retryCount < this.maxRetries;
      const translations = this.props.translations || {
        unexpectedErrorTitle: 'Произошла ошибка',
        unexpectedErrorDescription: 'Произошла неожиданная ошибка. Мы автоматически уведомлены и работаем над исправлением.',
        technicalInfo: 'Техническая информация',
        retry: 'Повторить',
        goHome: 'На главную',
        errorId: 'ID ошибки'
      };

      return (
        <div className="min-h-screen bg-gradient-dark flex items-center justify-center p-6">
          <div className="glass-card p-8 max-w-lg w-full text-center">
            <AlertTriangle className="w-16 h-16 text-accent-red mx-auto mb-6" />
            
            <h1 className="text-2xl font-bold text-white mb-4">
              {translations.unexpectedErrorTitle}
            </h1>
            
            <p className="text-gray-400 mb-6">
              {translations.unexpectedErrorDescription}
            </p>

            {import.meta.env.DEV && this.state.error && (
              <details className="text-left mb-6 p-4 bg-medium-gray rounded-lg">
                <summary className="text-sm text-gray-300 cursor-pointer mb-2">
                  {translations.technicalInfo} (ID: {this.state.errorId})
                </summary>
                <pre className="text-xs text-red-400 whitespace-pre-wrap">
                  {this.state.error.message}
                  {'\n\n'}
                  {this.state.error.stack}
                </pre>
              </details>
            )}

            <div className="flex flex-col sm:flex-row gap-3 justify-center">
              {canRetry && (
                <GlassButton onClick={this.handleRetry} variant="primary" size="sm">
                  <RefreshCw className="w-4 h-4 mr-2" />
                  {translations.retry}
                </GlassButton>
              )}
              
              <GlassButton onClick={this.handleGoHome} variant="secondary" size="sm">
                <Home className="w-4 h-4 mr-2" />
                {translations.goHome}
              </GlassButton>
            </div>

            <p className="text-xs text-gray-500 mt-6">
              {translations.errorId}: {this.state.errorId}
            </p>
          </div>
        </div>
      );
    }

    return this.props.children;
  }
}

export default ErrorBoundary;
