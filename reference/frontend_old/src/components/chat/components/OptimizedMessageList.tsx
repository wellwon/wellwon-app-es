
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
  onLoadMore?: () => void;
  hasMoreMessages?: boolean;
  className?: string;
  scrollAreaRef?: React.RefObject<HTMLDivElement>;
}

// Group messages by date for optimization
const groupMessagesByDate = (messages: Message[]) => {
  // First sort messages by creation time (old -> new)
  const sortedMessages = [...messages].sort((a, b) => 
    new Date(a.created_at).getTime() - new Date(b.created_at).getTime()
  );
  
  const groups: Array<{ date: string; messages: Message[] }> = [];
  let currentGroup: { date: string; messages: Message[] } | null = null;
  
  sortedMessages.forEach(message => {
    const messageDate = new Date(message.created_at).toDateString();
    
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
}>(({ date, messages, currentUser, sendingMessages, onReply }) => {
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
        />
      ))}
    </div>
  );
}, (prevProps, nextProps) => {
  // Optimize group re-renders
  return (
    prevProps.date === nextProps.date &&
    prevProps.messages.length === nextProps.messages.length &&
    prevProps.sendingMessages.size === nextProps.sendingMessages.size &&
    prevProps.messages.every((msg, index) => {
      const nextMsg = nextProps.messages[index];
      return msg && nextMsg &&
        msg.id === nextMsg.id &&
        msg.content === nextMsg.content &&
        msg.is_edited === nextMsg.is_edited &&
        JSON.stringify(msg.read_by) === JSON.stringify(nextMsg.read_by);
    })
  );
});

MessageGroup.displayName = 'MessageGroup';

export const OptimizedMessageList = memo<OptimizedMessageListProps>(({ 
  messages,
  currentUser,
  sendingMessages,
  onReply,
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
  useEffect(() => {
    if (!onLoadMore || !hasMoreMessages || messages.length < 10) return;

    let timeoutId: NodeJS.Timeout;
    let observer: IntersectionObserver | null = null;
    
    const createObserver = () => {
      // Don't create observer when tab is hidden
      if (document.hidden) return;
      
      // Get chat viewport as root
      const viewport = scrollAreaRef?.current?.querySelector('[data-radix-scroll-area-viewport]') as HTMLElement;
      
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
          root: viewport || null,
          threshold: 0,
          rootMargin: '0px'
        }
      );

      if (topTriggerRef.current) {
        observer.observe(topTriggerRef.current);
      }
    };
    
    const handleVisibilityChange = () => {
      if (document.hidden) {
        // Disconnect observer when tab is hidden
        if (observer) {
          observer.disconnect();
          observer = null;
        }
      } else {
        // Recreate observer when tab becomes visible with delay
        setTimeout(createObserver, 600);
      }
    };

    // Initial observer creation
    createObserver();
    
    // Listen for visibility changes
    document.addEventListener('visibilitychange', handleVisibilityChange);

    return () => {
      if (observer) {
        observer.disconnect();
      }
      clearTimeout(timeoutId);
      document.removeEventListener('visibilitychange', handleVisibilityChange);
    };
  }, [onLoadMore, hasMoreMessages, messages.length, scrollAreaRef]);

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
        />
      ))}
    </div>
  );
}, (prevProps, nextProps) => {
  // Main optimization - check key changes and message references
  if (prevProps.messages.length !== nextProps.messages.length ||
      prevProps.sendingMessages.size !== nextProps.sendingMessages.size ||
      prevProps.currentUser?.id !== nextProps.currentUser?.id) {
    return false;
  }
  
  // Check if messages array reference changed (indicates filtering)
  if (prevProps.messages !== nextProps.messages) {
    return false;
  }
  
  return true;
});

OptimizedMessageList.displayName = 'OptimizedMessageList';
