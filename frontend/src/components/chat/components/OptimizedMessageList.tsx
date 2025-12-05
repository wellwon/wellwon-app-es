// =============================================================================
// File: OptimizedMessageList.tsx
// Description: Seamless infinite scroll message list with prefetching
// Pattern: TanStack Query + Intersection Observer (2025 best practices)
// =============================================================================

import React, { memo, useMemo, useEffect, useRef, useCallback } from 'react';
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
  isLoadingMore?: boolean;
  className?: string;
  scrollAreaRef?: React.RefObject<HTMLDivElement>;
}

// Group messages by date for optimization
const groupMessagesByDate = (messages: Message[]) => {
  const sortedMessages = [...messages].sort((a, b) => {
    const timeA = new Date(a.created_at).getTime();
    const timeB = new Date(b.created_at).getTime();
    if (isNaN(timeA) && isNaN(timeB)) return 0;
    if (isNaN(timeA)) return 1;
    if (isNaN(timeB)) return -1;
    return timeA - timeB;
  });

  const groups: Array<{ date: string; messages: Message[] }> = [];
  let currentGroup: { date: string; messages: Message[] } | null = null;

  sortedMessages.forEach(message => {
    const parsedDate = new Date(message.created_at);
    const messageDate = isNaN(parsedDate.getTime())
      ? new Date().toDateString()
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
          // Use _stableKey for React key to prevent remount/re-animation during reconciliation
          // Discord/Slack pattern: stable key persists from temp_xxx -> snowflake transition
          key={message._stableKey || message.id}
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
  if (prevProps.messages !== nextProps.messages) return false;
  if (prevProps.date !== nextProps.date ||
      prevProps.sendingMessages !== nextProps.sendingMessages) return false;
  if (!!prevProps.onReply !== !!nextProps.onReply ||
      !!prevProps.onDelete !== !!nextProps.onDelete) return false;
  return true;
});

MessageGroup.displayName = 'MessageGroup';

// Sentinel threshold - how far from top to start prefetching (in pixels)
const PREFETCH_THRESHOLD_PX = 500;

export const OptimizedMessageList = memo<OptimizedMessageListProps>(({
  messages,
  currentUser,
  sendingMessages,
  onReply,
  onDelete,
  onLoadMore,
  hasMoreMessages = true,
  isLoadingMore = false,
  className,
  scrollAreaRef
}) => {
  // Memoize message grouping
  const messageGroups = useMemo(() => {
    return groupMessagesByDate(messages);
  }, [messages]);

  // Preload image dimensions
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

  // Refs for seamless infinite scroll
  const sentinelRef = useRef<HTMLDivElement>(null);
  const isLoadingRef = useRef(false);
  const lastLoadTimeRef = useRef(0);

  // Debounced load more to prevent rapid-fire requests
  const handleLoadMore = useCallback(() => {
    if (!onLoadMore || !hasMoreMessages || isLoadingMore) return;
    if (isLoadingRef.current) return;

    // Debounce: minimum 500ms between loads
    const now = Date.now();
    if (now - lastLoadTimeRef.current < 500) return;

    isLoadingRef.current = true;
    lastLoadTimeRef.current = now;
    onLoadMore();

    // Reset loading flag after a delay
    setTimeout(() => {
      isLoadingRef.current = false;
    }, 300);
  }, [onLoadMore, hasMoreMessages, isLoadingMore]);

  // Seamless Intersection Observer - triggers BEFORE user sees the top
  useEffect(() => {
    // Lower threshold to 3 - even small chats can have history
    if (!hasMoreMessages || messages.length < 3) return;

    const viewport = scrollAreaRef?.current?.querySelector(
      '[data-radix-scroll-area-viewport]'
    ) as HTMLElement;
    if (!viewport) return;

    let observer: IntersectionObserver | null = null;
    let rafId: number | null = null;

    const createObserver = () => {
      if (document.hidden) return;
      if (observer) return;

      observer = new IntersectionObserver(
        (entries) => {
          const [entry] = entries;
          if (entry.isIntersecting && !document.hidden) {
            // Use requestAnimationFrame for smooth triggering
            if (rafId) cancelAnimationFrame(rafId);
            rafId = requestAnimationFrame(() => {
              handleLoadMore();
            });
          }
        },
        {
          root: viewport,
          // rootMargin extends the trigger zone ABOVE the viewport
          // This means we start loading before user sees the top
          rootMargin: `${PREFETCH_THRESHOLD_PX}px 0px 0px 0px`,
          threshold: 0,
        }
      );

      if (sentinelRef.current) {
        observer.observe(sentinelRef.current);
      }
    };

    const handleVisibilityChange = () => {
      if (document.hidden) {
        if (observer) {
          observer.disconnect();
          observer = null;
        }
      } else {
        setTimeout(createObserver, 300);
      }
    };

    // Delay initial creation
    const initTimer = setTimeout(createObserver, 100);
    document.addEventListener('visibilitychange', handleVisibilityChange);

    return () => {
      if (observer) observer.disconnect();
      if (rafId) cancelAnimationFrame(rafId);
      clearTimeout(initTimer);
      document.removeEventListener('visibilitychange', handleVisibilityChange);
    };
  }, [hasMoreMessages, messages.length, handleLoadMore, scrollAreaRef]);

  return (
    <div className={`space-y-4 ${className || ''}`}>
      {/* Invisible sentinel for seamless prefetch - NO visible loading indicator */}
      {hasMoreMessages && messages.length >= 3 && (
        <div
          ref={sentinelRef}
          className="h-1 w-full pointer-events-none"
          aria-hidden="true"
        />
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
  if (prevProps.messages !== nextProps.messages) return false;
  if (prevProps.sendingMessages !== nextProps.sendingMessages ||
      prevProps.currentUser?.id !== nextProps.currentUser?.id ||
      prevProps.hasMoreMessages !== nextProps.hasMoreMessages ||
      prevProps.isLoadingMore !== nextProps.isLoadingMore) return false;
  return true;
});

OptimizedMessageList.displayName = 'OptimizedMessageList';
