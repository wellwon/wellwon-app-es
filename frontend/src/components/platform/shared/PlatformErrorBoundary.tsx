import React, { Component, ErrorInfo, ReactNode } from 'react';
import { GlassButton } from '@/components/design-system';
import { AlertTriangle, RefreshCw, Home } from 'lucide-react';
import { logger } from '@/utils/logger';
import { safeNavigate } from '@/utils/navigationHelper';

interface Props {
  children: ReactNode;
  fallback?: ReactNode;
}

interface State {
  hasError: boolean;
  error?: Error;
  errorInfo?: ErrorInfo;
  errorId: string;
}

class PlatformErrorBoundary extends Component<Props, State> {
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
    this.setState({
      error,
      errorInfo,
    });

    logger.error('Компонент упал с ошибкой', error, {
      component: 'PlatformErrorBoundary',
      errorInfo: errorInfo.componentStack,
      errorId: this.state.errorId,
    });
  }

  handleRetry = () => {
    // Simply reload the page - this is the most reliable way to recover
    logger.info('Перезагрузка страницы после ошибки', {
      component: 'PlatformErrorBoundary',
      errorId: this.state.errorId,
    });
    window.location.reload();
  };

  handleGoHome = () => {
    logger.info('Переход на главную из ErrorBoundary', {
      component: 'PlatformErrorBoundary',
      errorId: this.state.errorId,
    });
    
    safeNavigate('/');
  };

  render() {
    if (this.state.hasError) {
      if (this.props.fallback) {
        return this.props.fallback;
      }

      return (
        <div className="min-h-screen bg-dark-gray flex items-center justify-center p-4">
          <div className="max-w-md w-full bg-card/95 backdrop-blur-xl border border-white/20 rounded-xl p-8 text-center">
            <div className="flex flex-col items-center space-y-6">
              <div className="w-16 h-16 bg-accent-red/20 rounded-full flex items-center justify-center">
                <AlertTriangle className="w-8 h-8 text-accent-red" />
              </div>
              
              <div className="space-y-2">
                <h2 className="text-xl font-semibold text-foreground">
                  Неожиданная ошибка
                </h2>
                <p className="text-muted-foreground text-sm">
                  Что-то пошло не так. Попробуйте перезагрузить страницу или вернуться на главную.
                </p>
              </div>

              <div className="w-full space-y-3">
                <GlassButton
                  onClick={this.handleRetry}
                  variant="primary"
                  className="w-full"
                >
                  <RefreshCw className="w-4 h-4 mr-2" />
                  Перезагрузить
                </GlassButton>
                
                <GlassButton
                  onClick={this.handleGoHome}
                  variant="secondary"
                  className="w-full"
                >
                  <Home className="w-4 h-4 mr-2" />
                  На главную
                </GlassButton>
              </div>

              <details className="w-full text-left">
                <summary className="cursor-pointer text-xs text-muted-foreground hover:text-foreground transition-colors">
                  Техническая информация
                </summary>
                <div className="mt-2 p-3 bg-black/20 rounded border border-white/10">
                  <p className="text-xs text-muted-foreground mb-2">
                    ID Ошибки: {this.state.errorId}
                  </p>
                  {this.state.error && (
                    <pre className="text-xs text-accent-red whitespace-pre-wrap break-all">
                      {this.state.error.toString()}
                    </pre>
                  )}
                </div>
              </details>
            </div>
          </div>
        </div>
      );
    }

    return this.props.children;
  }
}

export default PlatformErrorBoundary;