// =============================================================================
// Platform Pro Error Boundary
// =============================================================================
// Стилизовано согласно DESIGN_SYSTEM.md v5.0

import React, { Component, ErrorInfo, ReactNode } from 'react';
import { AlertCircle, RefreshCw } from 'lucide-react';

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
        // Page background: Section 1.1 - Level 1 dark bg
        <div className="flex items-center justify-center min-h-screen p-8 bg-[#1a1a1e]">
          {/* Card: Section 1.1 Level 2, Section 4 rounded-2xl, Section 1.3 border */}
          <div className="max-w-md w-full p-8 bg-[#232328] border border-white/10 rounded-2xl">
            {/* Header: Section 3 gap-3 */}
            <div className="flex items-center gap-3 mb-4">
              {/* Icon: Section 1.4 accent-red */}
              <AlertCircle className="w-8 h-8 text-accent-red flex-shrink-0" />
              {/* Title: Section 2.2 text-xl, Section 2.3 font-semibold */}
              <h1 className="text-xl font-semibold text-white">Что-то пошло не так</h1>
            </div>

            {/* Message: Section 2.2 text-sm, Section 1.2 secondary text */}
            <p className="text-sm text-gray-400 mb-4">
              Произошла ошибка при загрузке Platform Pro.
            </p>

            {/* Error box: Section 1.1 Level 3 input bg, Section 4 rounded-xl */}
            {this.state.error && (
              <div className="mb-6 p-3 bg-[#1e1e22] border border-white/10 rounded-xl">
                {/* Error text: Section 2.1 mono font, Section 1.2 muted */}
                <p className="text-xs text-gray-500 font-mono break-all">
                  {this.state.error.message}
                </p>
              </div>
            )}

            {/* Button: Section 9.2 Primary CTA - h-10, rounded-xl, text-sm font-medium */}
            <button
              onClick={this.handleReload}
              className="w-full h-10 px-4 bg-accent-red text-white rounded-xl
                flex items-center justify-center gap-2
                text-sm font-medium
                hover:bg-accent-red/90 transition-colors
                focus:outline-none focus:ring-0"
            >
              <RefreshCw className="w-4 h-4" />
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
