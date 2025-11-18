import React from 'react';
import { cn } from '@/lib/utils';

interface UnreadBadgeProps {
  count: number;
  className?: string;
}

export const UnreadBadge: React.FC<UnreadBadgeProps> = ({ count, className }) => {
  if (count === 0) return null;

  return (
    <div className={cn(
      "inline-flex items-center justify-center min-w-5 h-5 px-1 text-xs font-medium text-white bg-accent-red rounded-full",
      className
    )}>
      {count > 99 ? '99+' : count}
    </div>
  );
};

export default UnreadBadge;