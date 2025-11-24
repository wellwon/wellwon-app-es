// =============================================================================
// Platform Pro Error Boundary
// =============================================================================

import React, { Component, ErrorInfo, ReactNode } from 'react';
import { AlertCircle } from 'lucide-react';

interface Props {
  children: ReactNode;
}

interface State {
  hasError: boolean;
  error: Error | null;
}

class PlatformProErrorBoundary extends Component<Props, State> {
  constructor(props: Props) {
    super(props);
    this.state = {
      hasError: false,
      error: null,
    };
  }

  static getDerivedStateFromError(error: Error): State {
    return {
      hasError: true,
      error,
    };
  }

  componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    console.error('Platform Pro Error:', error, errorInfo);
  }

  handleReload = () => {
    window.location.reload();
  };

  render() {
    if (this.state.hasError) {
      return (
        <div className="flex items-center justify-center h-screen bg-dark-gray">
          <div className="max-w-md p-8 bg-[#232328] border border-gray-700 rounded-2xl">
            <div className="flex items-center gap-3 mb-4">
              <AlertCircle className="w-8 h-8 text-accent-red" />
              <h1 className="text-xl font-bold text-white">Что-то пошло не так</h1>
            </div>

            <p className="text-gray-400 mb-4">
              Произошла ошибка при загрузке Platform Pro.
            </p>

            {this.state.error && (
              <div className="mb-4 p-3 bg-black/30 rounded-lg">
                <p className="text-xs text-gray-500 font-mono break-all">
                  {this.state.error.message}
                </p>
              </div>
            )}

            <button
              onClick={this.handleReload}
              className="w-full px-4 py-2 bg-accent-red text-white rounded-lg hover:bg-accent-red/90 transition-colors"
            >
              Перезагрузить страницу
            </button>
          </div>
        </div>
      );
    }

    return this.props.children;
  }
}

export default PlatformProErrorBoundary;
