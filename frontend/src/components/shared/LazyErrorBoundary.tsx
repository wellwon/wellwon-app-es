import React, { Component, ComponentType, ReactNode } from 'react';
import { GlassButton } from '@/components/design-system';
import { RefreshCw, AlertTriangle } from 'lucide-react';
import { logger } from '@/utils/logger';
import { safeNavigate } from '@/utils/navigationHelper';

interface LazyErrorBoundaryState {
  hasError: boolean;
  retryCount: number;
}

interface LazyErrorBoundaryProps {
  children: ReactNode;
  fallback?: ReactNode;
  maxRetries?: number;
}

class LazyErrorBoundary extends Component<LazyErrorBoundaryProps, LazyErrorBoundaryState> {
  private maxRetries: number;

  constructor(props: LazyErrorBoundaryProps) {
    super(props);
    this.state = {
      hasError: false,
      retryCount: 0,
    };
    this.maxRetries = props.maxRetries || 3;
  }

  static getDerivedStateFromError(): Partial<LazyErrorBoundaryState> {
    return { hasError: true };
  }

  componentDidCatch(error: Error) {
    logger.error('LazyErrorBoundary caught an error', error, {
      component: 'LazyErrorBoundary',
      metadata: {
        retryCount: this.state.retryCount,
        maxRetries: this.maxRetries,
        userAgent: navigator.userAgent,
        url: window.location.href,
      }
    });
  }

  handleRetry = () => {
    if (this.state.retryCount < this.maxRetries) {
      this.setState(prevState => ({
        hasError: false,
        retryCount: prevState.retryCount + 1,
      }));
    }
  };

  handleReload = () => {
    logger.info('Reloading from LazyErrorBoundary', { component: 'LazyErrorBoundary' });
    safeNavigate('/');
    // Reset state for fresh start
    this.setState({
      hasError: false,
      retryCount: 0,
    });
  };

  render() {
    if (this.state.hasError) {
      if (this.props.fallback) {
        return this.props.fallback;
      }

      const canRetry = this.state.retryCount < this.maxRetries;

      return (
        <div className="flex flex-col items-center justify-center p-8 text-center min-h-[200px]">
          <AlertTriangle className="w-12 h-12 text-accent-red mb-4" />
          <h3 className="text-lg font-semibold text-white mb-2">
            Ошибка загрузки компонента
          </h3>
          <p className="text-gray-400 mb-4 max-w-md">
            Не удалось загрузить часть приложения. Попробуйте перезагрузить.
          </p>
          <div className="flex gap-3">
            {canRetry && (
              <GlassButton onClick={this.handleRetry} variant="primary" size="sm">
                <RefreshCw className="w-4 h-4 mr-2" />
                Повторить ({this.maxRetries - this.state.retryCount})
              </GlassButton>
            )}
            <GlassButton onClick={this.handleReload} variant="secondary" size="sm">
              Перезагрузить
            </GlassButton>
          </div>
        </div>
      );
    }

    return this.props.children;
  }
}

// Wrapper для создания lazy компонентов с обработкой ошибок
export const createLazyComponent = <P = Record<string, unknown>>(
  factory: () => Promise<{ default: ComponentType<P> }>,
  maxRetries = 3
) => {
  const LazyComponent = React.lazy(factory);
  
  return (props: P) => (
    <LazyErrorBoundary maxRetries={maxRetries}>
      <LazyComponent {...(props as any)} />
    </LazyErrorBoundary>
  );
};

export { LazyErrorBoundary };
export default LazyErrorBoundary;