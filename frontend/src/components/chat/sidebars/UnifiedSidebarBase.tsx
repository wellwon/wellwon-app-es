import React, { ReactNode } from 'react';
import { cn } from '@/lib/utils';
import { usePlatform } from '@/contexts/PlatformContext';

interface UnifiedSidebarBaseProps {
  title: string;
  children: ReactNode;
  footer?: ReactNode;
  className?: string;
}

const UnifiedSidebarBase: React.FC<UnifiedSidebarBaseProps> = ({
  title,
  children,
  footer,
  className
}) => {
  const { isLightTheme } = usePlatform();

  // Theme-aware styles - sidebar should be darker than messages panel
  const theme = isLightTheme ? {
    sidebar: 'bg-[#f4f4f4] border-gray-300',
    header: 'bg-[#f4f4f4] border-gray-300',
    text: 'text-gray-900',
    footer: 'border-gray-300 bg-[#f4f4f4]'
  } : {
    sidebar: 'bg-[#1a1a1d] border-white/10',
    header: 'bg-[#1a1a1d] border-white/10',
    text: 'text-white',
    footer: 'border-white/10 bg-[#1a1a1d]'
  };

  return (
    <div className={cn(
      `w-[420px] h-screen backdrop-blur-sm border-l flex flex-col relative z-50 ${theme.sidebar}`,
      className
    )}>
      {/* Header */}
      <div className={`h-16 backdrop-blur-sm border-b flex items-center justify-center px-6 ${theme.header}`}>
        <h2 className={`font-semibold text-lg ${theme.text}`}>{title}</h2>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto p-6">
        {children}
      </div>

      {/* Footer */}
      {footer && (
        <div className={`border-t min-h-24 flex items-center px-6 py-3 ${theme.footer}`}>
          {footer}
        </div>
      )}
    </div>
  );
};

export default UnifiedSidebarBase;