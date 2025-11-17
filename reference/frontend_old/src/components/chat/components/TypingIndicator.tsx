import React from 'react';
import { Avatar, AvatarFallback, AvatarImage } from '@/components/ui/avatar';
import { useAuth } from '@/contexts/AuthContext';
import type { TypingIndicator as TypingIndicatorType } from '@/types/realtime-chat';

interface TypingIndicatorProps {
  typingUsers: TypingIndicatorType[];
}

export function TypingIndicator({ typingUsers }: TypingIndicatorProps) {
  const { user } = useAuth();

  const visibleUsers = React.useMemo(() => {
    return typingUsers.filter((u) => u.user_id !== user?.id);
  }, [typingUsers, user?.id]);

  if (visibleUsers.length === 0) return null;

  const getDisplayName = (u: TypingIndicatorType) => {
    const profile = u.user_profile;
    if (profile?.first_name || profile?.last_name) {
      return `${profile.first_name || ''} ${profile.last_name || ''}`.trim();
    }
    return 'Пользователь';
  };

  const getTypingText = () => {
    if (visibleUsers.length === 1) {
      return `${getDisplayName(visibleUsers[0])} печатает`;
    } else if (visibleUsers.length === 2) {
      return `${getDisplayName(visibleUsers[0])} и ${getDisplayName(visibleUsers[1])} печатают`;
    } else {
      return `${getDisplayName(visibleUsers[0])} и еще ${visibleUsers.length - 1} печатают`;
    }
  };

  return (
    <div
      className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full bg-card/70 border border-border backdrop-blur-sm text-xs text-muted-foreground shadow-sm animate-fade-in"
      aria-live="polite"
    >
      <div className="flex -space-x-2">
        {visibleUsers.slice(0, 3).map((u) => (
          <Avatar key={u.user_id} className="w-7 h-7 ring-1 ring-border">
            <AvatarImage src={u.user_profile?.avatar_url || undefined} />
            <AvatarFallback className="text-[10px]">
              {getDisplayName(u).charAt(0)}
            </AvatarFallback>
          </Avatar>
        ))}
      </div>

      <span className="whitespace-nowrap">{getTypingText()}</span>

      <div className="flex gap-1 ml-1">
        <span className="w-2 h-2 rounded-full bg-muted-foreground/80 animate-bounce" style={{ animationDelay: '0ms' }} />
        <span className="w-2 h-2 rounded-full bg-muted-foreground/80 animate-bounce" style={{ animationDelay: '150ms' }} />
        <span className="w-2 h-2 rounded-full bg-muted-foreground/80 animate-bounce" style={{ animationDelay: '300ms' }} />
      </div>
    </div>
  );
}