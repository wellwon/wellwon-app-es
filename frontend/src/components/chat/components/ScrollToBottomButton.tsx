import React from 'react';
import { ChevronDown } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils';
import { usePlatform } from '@/contexts/PlatformContext';

interface ScrollToBottomButtonProps {
  visible: boolean;
  count: number;
  onClick: () => void;
  bottomOffset?: number;
}

export const ScrollToBottomButton: React.FC<ScrollToBottomButtonProps> = ({
  visible,
  count,
  onClick,
  bottomOffset = 24
}) => {
  const { isLightTheme } = usePlatform();

  return (
    <div
      className={cn(
        "absolute z-50 transition-all duration-300 ease-in-out",
        visible
          ? "opacity-100 translate-y-0 pointer-events-auto"
          : "opacity-0 translate-y-2 pointer-events-none"
      )}
      style={{
        right: '24px',
        bottom: `${bottomOffset}px`
      }}
    >
      <div className="relative">
        <Button
          onClick={onClick}
          className={`h-12 w-12 rounded-full shadow-lg backdrop-blur-sm transition-all duration-300 ${
            isLightTheme
              ? 'bg-white border border-gray-300 text-gray-700 hover:text-gray-900 hover:bg-gray-50'
              : 'bg-white/5 border border-white/10 text-white hover:text-white hover:bg-white/10'
          }`}
          size="icon"
        >
          <ChevronDown className="h-7 w-7" />
        </Button>

        {count > 0 && (
          <div className="absolute -top-3 -right-2 min-w-6 h-6 px-1 flex items-center justify-center bg-destructive text-white text-xs font-medium rounded-full pointer-events-none">
            {count > 99 ? '99+' : count}
          </div>
        )}
      </div>
    </div>
  );
};

export default ScrollToBottomButton;