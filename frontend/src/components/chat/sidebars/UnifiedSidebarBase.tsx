import React, { ReactNode } from 'react';
import { cn } from '@/lib/utils';

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
  return (
    <div className={cn(
      "w-full h-full bg-dark-gray/95 backdrop-blur-sm border-l border-white/10 flex flex-col relative z-50",
      className
    )}>
      {/* Header */}
      <div className="h-16 bg-dark-gray/95 backdrop-blur-sm border-b border-white/10 flex items-center justify-center px-6 flex-shrink-0">
        <h2 className="text-white font-semibold text-lg">{title}</h2>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto overflow-x-hidden p-6 scrollbar-thin">
        {children}
      </div>

      {/* Footer */}
      {footer && (
        <div className="border-t border-white/10 min-h-24 flex items-center px-6 bg-dark-gray/95 py-3 flex-shrink-0">
          {footer}
        </div>
      )}
    </div>
  );
};

export default UnifiedSidebarBase;