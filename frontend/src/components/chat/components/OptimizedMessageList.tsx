
import React, { memo, useMemo, useEffect, useRef } from 'react';
import { MessageBubbleMemo } from './MessageBubbleMemo';
import { DateSeparator } from './DateSeparator';
import type { Message } from '@/types/realtime-chat';

interface OptimizedMessageListProps {
  messages: Message[];
  currentUser?: {
    id: string;
    first_name?: string;
    last_name?: string;
    avatar_url?: string;
  };
  sendingMessages: Set<string>;
  onReply?: (message: Message) => void;
  onDelete?: (messageId: string) => void;
  onLoadMore?: () => void;
  hasMoreMessages?: boolean;
  className?: string;
  scrollAreaRef?: React.RefObject<HTMLDivElement>;
}

// Group messages by date for optimization
const groupMessagesByDate = (messages: Message[]) => {
  // First sort messages by creation time (old -> new) with NaN-safe comparison
  const sortedMessages = [...messages].sort((a, b) => {
    const timeA = new Date(a.created_at).getTime();
    const timeB = new Date(b.created_at).getTime();
    // Handle NaN: put invalid dates at the end
    if (isNaN(timeA) && isNaN(timeB)) return 0;
    if (isNaN(timeA)) return 1;
    if (isNaN(timeB)) return -1;
    return timeA - timeB;
  });
  
  const groups: Array<{ date: string; messages: Message[] }> = [];
  let currentGroup: { date: string; messages: Message[] } | null = null;
  
  sortedMessages.forEach(message => {
    // Safely parse date with fallback to today for invalid dates
    const parsedDate = new Date(message.created_at);
    const messageDate = isNaN(parsedDate.getTime())
      ? new Date().toDateString()  // Fallback to today
      : parsedDate.toDateString();

    if (!currentGroup || currentGroup.date !== messageDate) {
      currentGroup = { date: messageDate, messages: [message] };
      groups.push(currentGroup);
    } else {
      currentGroup.messages.push(message);
    }
  });
  
  return groups;
};

// Memoized message group
const MessageGroup = memo<{
  date: string;
  messages: Message[];
  currentUser?: OptimizedMessageListProps['currentUser'];
  sendingMessages: Set<string>;
  onReply?: (message: Message) => void;
  onDelete?: (messageId: string) => void;
}>(({ date, messages, currentUser, sendingMessages, onReply, onDelete }) => {
  return (
    <div className="space-y-4">
      <DateSeparator date={new Date(date)} />
      {messages.map(message => (
        <MessageBubbleMemo
          key={message.id}
          message={message}
          isOwn={message.sender_id === currentUser?.id}
          isSending={sendingMessages.has(message.id)}
          currentUser={currentUser}
          onReply={onReply}
          onDelete={onDelete}
        />
      ))}
    </div>
  );
}, (prevProps, nextProps) => {
  // CRITICAL: Re-render if messages array reference changed
  // This ensures new messages are displayed immediately
  if (prevProps.messages !== nextProps.messages) {
    return false; // Re-render
  }

  // Re-render if other key props changed
  if (prevProps.date !== nextProps.date ||
      prevProps.sendingMessages !== nextProps.sendingMessages) {
    return false; // Re-render
  }

  // Re-render if callback availability changed (ensures action buttons render)
  if (!!prevProps.onReply !== !!nextProps.onReply ||
      !!prevProps.onDelete !== !!nextProps.onDelete) {
    return false; // Re-render
  }

  return true; // Props are equal, skip re-render
});

MessageGroup.displayName = 'MessageGroup';

export const OptimizedMessageList = memo<OptimizedMessageListProps>(({
  messages,
  currentUser,
  sendingMessages,
  onReply,
  onDelete,
  onLoadMore,
  hasMoreMessages = true,
  className,
  scrollAreaRef
}) => {
  // Memoize message grouping
  const messageGroups = useMemo(() => {
    return groupMessagesByDate(messages);
  }, [messages]);

  // Предварительно загружаем размеры изображений для предотвращения layout shift
  useEffect(() => {
    const imageMessages = messages.filter(msg => 
      msg.message_type === 'image' && 
      msg.file_url && 
      !msg.metadata?.imageDimensions
    );

    if (imageMessages.length > 0) {
      import('@/utils/imageDimensionsCache').then(({ imageDimensionsCache }) => {
        imageDimensionsCache.preloadMessagesDimensions(imageMessages);
      });
    }
  }, [messages]);

  // Ref for tracking upward scroll for infinite scroll
  const topTriggerRef = useRef<HTMLDivElement>(null);

  // Intersection Observer for loading older messages with visibility control
  // TEMPORARILY DISABLED - debugging infinite loop issue
  // TODO: Re-enable once the loop is fixed
  const observerCreatedRef = useRef(false);

  useEffect(() => {
    if (!onLoadMore || !hasMoreMessages || messages.length < 10) return;
    if (observerCreatedRef.current) return; // Only create once per mount

    let timeoutId: NodeJS.Timeout;
    let observer: IntersectionObserver | null = null;

    const createObserver = () => {
      // Don't create observer when tab is hidden
      if (document.hidden) return;
      if (observer) return; // Already created

      // Get chat viewport as root - delay to ensure DOM is ready
      const viewport = scrollAreaRef?.current?.querySelector('[data-radix-scroll-area-viewport]') as HTMLElement;
      if (!viewport) return;

      observer = new IntersectionObserver(
        (entries) => {
          const [entry] = entries;
          if (entry.isIntersecting && hasMoreMessages && !document.hidden) {
            // Debounce to prevent multiple requests
            clearTimeout(timeoutId);
            timeoutId = setTimeout(() => {
              onLoadMore();
            }, 200);
          }
        },
        {
          root: viewport,
          threshold: 0,
          rootMargin: '0px'
        }
      );

      if (topTriggerRef.current) {
        observer.observe(topTriggerRef.current);
        observerCreatedRef.current = true;
      }
    };

    const handleVisibilityChange = () => {
      if (document.hidden) {
        // Disconnect observer when tab is hidden
        if (observer) {
          observer.disconnect();
          observer = null;
          observerCreatedRef.current = false;
        }
      } else {
        // Recreate observer when tab becomes visible with delay
        setTimeout(createObserver, 600);
      }
    };

    // Delay initial observer creation to avoid issues with Radix ScrollArea ref
    const initTimer = setTimeout(createObserver, 100);

    // Listen for visibility changes
    document.addEventListener('visibilitychange', handleVisibilityChange);

    return () => {
      if (observer) {
        observer.disconnect();
      }
      clearTimeout(timeoutId);
      clearTimeout(initTimer);
      document.removeEventListener('visibilitychange', handleVisibilityChange);
      observerCreatedRef.current = false;
    };
    // Note: scrollAreaRef is a ref, not state - it's stable and shouldn't be in deps
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [onLoadMore, hasMoreMessages, messages.length]);

  return (
    <div className={`space-y-4 ${className || ''}`}>
      {/* Trigger for loading old messages - show only when there is something to load */}
      {hasMoreMessages && messages.length >= 10 && onLoadMore && (
        <div ref={topTriggerRef} className="h-8 flex items-center justify-center mb-4 no-anchor">
          <div className="bg-card/80 backdrop-blur-sm rounded-full px-3 py-1 flex items-center gap-2 border border-white/10">
            <div className="w-3 h-3 border border-primary/60 border-t-transparent rounded-full animate-spin" />
            <span className="text-xs text-muted-foreground">Загрузка истории...</span>
          </div>
        </div>
      )}
      
      {messageGroups.map((group, groupIndex) => (
        <MessageGroup
          key={`${group.date}-${groupIndex}`}
          date={group.date}
          messages={group.messages}
          currentUser={currentUser}
          sendingMessages={sendingMessages}
          onReply={onReply}
          onDelete={onDelete}
        />
      ))}
    </div>
  );
}, (prevProps, nextProps) => {
  // CRITICAL: Always re-render if messages array reference changed
  // This ensures new messages from WSE are displayed immediately
  if (prevProps.messages !== nextProps.messages) {
    return false; // Re-render
  }

  // Check other props that should trigger re-render
  if (prevProps.sendingMessages !== nextProps.sendingMessages ||
      prevProps.currentUser?.id !== nextProps.currentUser?.id ||
      prevProps.hasMoreMessages !== nextProps.hasMoreMessages) {
    return false; // Re-render
  }

  return true; // Props are equal, skip re-render
});

OptimizedMessageList.displayName = 'OptimizedMessageList';
