import React, { useState, useRef, useCallback, useMemo, useEffect } from 'react';
import { useRealtimeChatContext } from '@/contexts/RealtimeChatContext';
import { useAuth } from '@/contexts/AuthContext';
import { usePlatform } from '@/contexts/PlatformContext';
import { useUnifiedSidebar } from '@/contexts/chat/UnifiedSidebarProvider';
import { Paperclip, Image, Mic, Send, MessageSquare, Zap } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { AutoResizeTextarea } from '@/components/ui/auto-resize-textarea';
import { ScrollArea } from '@/components/ui/scroll-area';
import { useMentions } from '@/hooks/useMentions';
import { MentionsDropdown } from '../components/MentionsDropdown';
import { isSameDay } from 'date-fns';
import { useOptimizedScroll } from '@/hooks/useOptimizedScroll';
import { MessageBubble } from '../components/MessageBubble';
import { DateSeparator } from '../components/DateSeparator';
import { TypingIndicator } from '../components/TypingIndicator';
import { OptimizedMessageList } from '../components/OptimizedMessageList';
import { FileUploadButton } from '../components/FileUploadButton';
import { VoiceRecordButton } from '../components/VoiceRecordButton';
import { ScrollToBottomButton } from '../components/ScrollToBottomButton';

import ServicesCatalog from '../services/ServicesCatalog';
import SelectChatPlaceholder from './SelectChatPlaceholder';
import { Loader } from '@/components/ui/loader';
import { DraftMessageBubble } from '../components/DraftMessageBubble';
import { logger } from '@/utils/logger';

import { ReplyPreviewOverlay } from '../components/ReplyPreviewOverlay';
import type { MessageTemplate } from '@/utils/messageTemplates';
import type { Message } from '@/types/realtime-chat';

// Utility to wait for DOM element to appear
const waitForMessageElement = (messageId: string, maxWaitTime = 3000): Promise<HTMLElement | null> => {
  return new Promise((resolve) => {
    const startTime = Date.now();
    
    const checkElement = () => {
      const element = document.querySelector(`[data-message-id="${messageId}"]`) as HTMLElement;
      
      if (element) {
        resolve(element);
        return;
      }
      
      if (Date.now() - startTime > maxWaitTime) {
        resolve(null);
        return;
      }
      
      setTimeout(checkElement, 50);
    };
    
    checkElement();
  });
};

const ChatInterface = React.memo(() => {
  const {
    chats,
    activeChat,
    messages,
    filteredMessages,
    displayedMessages,
    messageFilter,
    typingUsers,
    initialLoading,
    loadingMessages,
    loadingMoreMessages,
    hasMoreMessages,
    filteredHasMore,
    sendingMessages,
    sendMessage,
    sendFile,
    sendVoice,
    loadMoreMessages,
    loadHistoryUntilMessage,
    sendInteractiveMessage,
    startTyping,
    stopTyping,
    markAsRead,
    setMessageFilter,
    deleteMessage
  } = useRealtimeChatContext();
  const { user } = useAuth();
  const { isDeveloper, isLightTheme } = usePlatform();
  const { openSidebar } = useUnifiedSidebar();
  
  const [inputValue, setInputValue] = useState('');
  const [textareaHeight, setTextareaHeight] = useState(24);
  const [draftMessage, setDraftMessage] = useState<MessageTemplate | null>(null);
  const [replyTarget, setReplyTarget] = useState<Message | null>(null);
  const [isAtBottom, setIsAtBottom] = useState(true);
  const [newMessagesCount, setNewMessagesCount] = useState(0);
  const [isFirstLoad, setIsFirstLoad] = useState(true);
  
  // Mentions state
  const [mentionOpen, setMentionOpen] = useState(false);
  const [mentionQuery, setMentionQuery] = useState('');
  const [mentionTriggerIndex, setMentionTriggerIndex] = useState(0);
  const [highlightedIndex, setHighlightedIndex] = useState(0);
  const [replyOverlayHeight, setReplyOverlayHeight] = useState(0);
  
  const scrollAreaRef = useRef<HTMLDivElement>(null);
  const sentinelRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const inputContainerRef = useRef<HTMLDivElement>(null);
  
  // Инициализация хука для mentions
  const mentions = useMentions({ activeChat });
  const { items: mentionItems, isLoading: mentionsLoading, filter: filterMentions } = mentions;
  
  // Refs for scroll anchoring during load more
  const anchoringRef = useRef(false);
  const atBottomRef = useRef(false);

  // Helper functions for scroll anchoring
  const getViewport = useCallback(() => {
    return scrollAreaRef.current?.querySelector('[data-radix-scroll-area-viewport]') as HTMLElement;
  }, []);

  const checkIfAtBottom = useCallback((tolerance = 50) => {
    const viewport = getViewport();
    if (!viewport) return false;
    
    const { scrollTop, scrollHeight, clientHeight } = viewport;
    return scrollTop + clientHeight >= scrollHeight - tolerance;
  }, [getViewport]);

  // Стабильный callback для отметки сообщений как прочитанных
  const handleMarkAsRead = useCallback(() => {
    if (displayedMessages.length > 0) {
      const lastMessage = displayedMessages[displayedMessages.length - 1];
      markAsRead(lastMessage.id);
    }
  }, [displayedMessages, markAsRead]);

  // Оптимизированная логика скроллинга
  const { scrollToBottom, checkIfScrollNeeded } = useOptimizedScroll({
    onScrollComplete: handleMarkAsRead,
    delay: 300
  });
  
  // Сброс replyTarget при смене чата
  useEffect(() => {
    setReplyTarget(null);
    setReplyOverlayHeight(0); // Сброс высоты при смене чата
    setNewMessagesCount(0); // Сброс счётчика при смене чата
    setIsAtBottom(true);
  }, [activeChat?.id]);

  // Отслеживание позиции скролла с IntersectionObserver
  useEffect(() => {
    const viewport = getViewport();
    const sentinel = sentinelRef.current;
    if (!viewport || !sentinel) return;

    const observer = new IntersectionObserver(
      ([entry]) => {
        const isCurrentlyAtBottom = entry.isIntersecting;
        setIsAtBottom(isCurrentlyAtBottom);

        // Сброс счётчика если пользователь промотал вниз
        if (isCurrentlyAtBottom) {
          setNewMessagesCount(0);
        }
      },
      {
        root: viewport,
        threshold: 0.1
      }
    );

    observer.observe(sentinel);
    return () => observer.disconnect();
  }, [getViewport]);

  // Track the last message ID to detect new incoming messages
  const lastProcessedMessageIdRef = useRef<string | null>(null);

  // Подсчёт новых сообщений когда пользователь не внизу
  useEffect(() => {
    if (displayedMessages.length > 0 && !isFirstLoad && !loadingMoreMessages) {
      const lastMessage = displayedMessages[displayedMessages.length - 1];

      // Only process if this is a new message we haven't seen
      if (lastMessage.id !== lastProcessedMessageIdRef.current) {
        lastProcessedMessageIdRef.current = lastMessage.id;

        // Only increment for incoming messages (not from current user) when not at bottom
        if (!isAtBottom && lastMessage.sender_id !== user?.id) {
          setNewMessagesCount(prev => prev + 1);
        }
      }
    }
  }, [displayedMessages.length, isAtBottom, isFirstLoad, loadingMoreMessages, displayedMessages, user?.id]);

  // Функция промотки вниз по клику на кнопку
  const handleScrollToBottomClick = useCallback(() => {
    scrollToBottom(scrollAreaRef, { force: true });
    setNewMessagesCount(0);
    setIsAtBottom(true);
  }, [scrollToBottom]);

  // Мемоизированная функция скроллинга с проверкой необходимости
  const handleScrollToBottom = useCallback(() => {
    const isScrollNeeded = checkIfScrollNeeded(scrollAreaRef);
    if (isScrollNeeded) {
      scrollToBottom(scrollAreaRef);
    }
  }, [scrollToBottom, checkIfScrollNeeded]);

  // Мемоизированное количество сообщений для оптимизации
  const messagesCount = useMemo(() => displayedMessages.length, [displayedMessages.length]);

  const handleLoadMoreWithAnchor = useCallback(async () => {
    if (!activeChat || loadingMoreMessages) return;

    // Check if user was at bottom before loading
    atBottomRef.current = checkIfAtBottom();
    anchoringRef.current = true;

    const viewport = getViewport();
    if (!viewport) return;

    // Заморозка анимаций во время загрузки (отключаем animation для новых сообщений)
    viewport.classList.add('chat-freeze');
    viewport.classList.add('chat-loading-history');

    // Запоминаем текущую позицию скролла и высоту
    const prevScrollHeight = viewport.scrollHeight;
    const prevScrollTop = viewport.scrollTop;

    // Жесткий анчоринг: запоминаем первое видимое сообщение
    const allMessages = Array.from(viewport.querySelectorAll('[data-message-id]'));
    const firstVisibleMessage = allMessages.find(el => {
      const rect = el.getBoundingClientRect();
      const viewportRect = viewport.getBoundingClientRect();
      return rect.top >= viewportRect.top - 10 && rect.top <= viewportRect.bottom;
    }) as HTMLElement;

    const anchorMessageId = firstVisibleMessage?.getAttribute('data-message-id');
    const anchorOffsetTop = firstVisibleMessage?.offsetTop || 0;

    try {
      await loadMoreMessages();

      // Мгновенное восстановление позиции без анимации
      requestAnimationFrame(() => {
        const newScrollHeight = viewport.scrollHeight;
        const heightDelta = newScrollHeight - prevScrollHeight;

        if (anchorMessageId && !atBottomRef.current) {
          // Пытаемся найти якорное сообщение
          const anchorElement = viewport.querySelector(`[data-message-id="${anchorMessageId}"]`) as HTMLElement;
          if (anchorElement) {
            // Восстанавливаем позицию относительно якоря
            const newAnchorOffsetTop = anchorElement.offsetTop;
            const offsetDelta = newAnchorOffsetTop - anchorOffsetTop;
            viewport.scrollTop = prevScrollTop + offsetDelta;
          } else {
            // Fallback: просто добавляем дельту высоты
            viewport.scrollTop = prevScrollTop + heightDelta;
          }
        } else if (heightDelta > 0) {
          // Просто корректируем на дельту высоты
          viewport.scrollTop = prevScrollTop + heightDelta;
        }
      });
    } finally {
      // Плавно убираем заморозку
      setTimeout(() => {
        viewport.classList.remove('chat-freeze');
        // Добавляем fade-in эффект
        viewport.classList.add('pagination-reveal');

        setTimeout(() => {
          viewport.classList.remove('chat-loading-history');
          viewport.classList.remove('pagination-reveal');
          anchoringRef.current = false;
        }, 150);
      }, 50);
    }
  }, [activeChat, loadingMoreMessages, loadMoreMessages, checkIfAtBottom, getViewport]);
  
  // Автоматический скролл при новых сообщениях (синхронно для устранения дёрганья)
  useEffect(() => {
    if (messagesCount > 0 && activeChat && !loadingMoreMessages && !anchoringRef.current) {
      if (isFirstLoad) {
        // Первая загрузка - мгновенный статичный скролл без анимации
        requestAnimationFrame(() => {
          const viewport = getViewport();
          if (viewport && viewport.scrollHeight > viewport.clientHeight) {
            viewport.scrollTop = viewport.scrollHeight;
          }
        });
        setIsFirstLoad(false);
      } else {
        // Для реалтайм сообщений - скроллим если пользователь достаточно близко к низу (200px tolerance)
        const isNearBottom = checkIfAtBottom(200);
        if (isNearBottom) {
          const timer = setTimeout(handleScrollToBottom, 50);
          return () => clearTimeout(timer);
        }
      }
    }
  }, [messagesCount, handleScrollToBottom, activeChat, isFirstLoad, getViewport, loadingMoreMessages, checkIfAtBottom]);
  
  // Сброс состояния первой загрузки при смене чата и принудительный скролл
  useEffect(() => {
    setIsFirstLoad(true);
    
    // Принудительный мгновенный скролл вниз при загрузке нового чата
    if (activeChat && displayedMessages.length > 0) {
      requestAnimationFrame(() => {
        const viewport = getViewport();
        if (viewport) {
          viewport.scrollTop = viewport.scrollHeight;
        }
      });
    }
  }, [activeChat?.id, getViewport]);

  // Listen for draft message and reply search events
  useEffect(() => {
    const handleDraftMessage = (event: CustomEvent) => {
      setDraftMessage(event.detail as MessageTemplate);
      setTimeout(handleScrollToBottom, 100);
    };

    const handleFindReplyMessage = async (event: CustomEvent) => {
      const { replyToId, onFound } = event.detail;
      
      // Ищем сообщение в текущих отображаемых сообщениях
      const existingMessage = displayedMessages.find(msg => msg.id === replyToId);
      if (existingMessage) {
        onFound(replyToId);
        return;
      }

      // Dispatch searching status for loading indicator
      window.dispatchEvent(new CustomEvent('chat:findReplyMessage:searching', { 
        detail: { replyToId, searching: true } 
      }));

      // Prevent auto-scroll during background loading
      anchoringRef.current = true;

      // Measure scroll position before loading for stabilization
      const viewport = getViewport();
      const prevScrollTop = viewport.scrollTop;
      const prevScrollHeight = viewport.scrollHeight;

      // Если сообщение не найдено, используем incremental loading до нужного сообщения
      logger.info('Reply target not found, starting incremental history load', { 
        replyToId, 
        currentMessagesCount: displayedMessages.length,
        component: 'ChatInterface' 
      });
      
      try {
        // Заморозка анимаций во время загрузки истории
        viewport.classList.add('chat-freeze');
        
        // Используем новый метод для incremental загрузки истории до целевого сообщения
        const targetFound = await loadHistoryUntilMessage(replyToId);
        
        // Stabilize scroll position immediately after loading to prevent visual jump
        requestAnimationFrame(() => {
          const newScrollHeight = viewport.scrollHeight;
          const delta = newScrollHeight - prevScrollHeight;
          if (delta > 0) {
            viewport.scrollTop = prevScrollTop + delta;
          }
          
          // Убираем заморозку анимаций после стабилизации
          setTimeout(() => {
            viewport.classList.remove('chat-freeze');
          }, 50);
        });
          
        // Secondary stabilization for reliability
        setTimeout(() => {
          const finalScrollHeight = viewport.scrollHeight;
          const finalDelta = finalScrollHeight - prevScrollHeight;
          if (finalDelta > 0 && Math.abs(viewport.scrollTop - (prevScrollTop + finalDelta)) > 5) {
            viewport.scrollTop = prevScrollTop + finalDelta;
          }
        }, 120);
        
        if (targetFound) {
          logger.info('Reply target found after incremental load', { 
            replyToId,
            component: 'ChatInterface' 
          });
          
          // Wait for the message element to appear in DOM before scrolling
          const messageElement = await waitForMessageElement(replyToId);
          
          if (messageElement) {
            // Small delay to ensure stabilization before scrolling to target
            setTimeout(() => onFound(replyToId), 100);
          } else {
            logger.warn('Message element not found in DOM after loading', { 
              replyToId,
              component: 'ChatInterface' 
            });
          }
        } else {
          logger.warn('Reply target still not found after incremental load', { 
            replyToId,
            component: 'ChatInterface' 
          });
        }
      } catch (error) {
        logger.error('Error in incremental history load for reply search', error, { 
          replyToId,
          component: 'ChatInterface' 
        });
      } finally {
        // Dispatch completion status
        window.dispatchEvent(new CustomEvent('chat:findReplyMessage:completed', { 
          detail: { replyToId } 
        }));
        
        // Re-enable auto-scroll after transition
        setTimeout(() => {
          anchoringRef.current = false;
        }, 400);
      }
    };

    const handleScrollToBottom = (event: CustomEvent) => {
      // Блокируем внешние авто-скроллы во время анчоринга
      if (anchoringRef.current) return;
      
      const { force } = event.detail;
      scrollToBottom(scrollAreaRef, { force });
    };

    window.addEventListener('showDraftMessage', handleDraftMessage as EventListener);
    window.addEventListener('chat:scrollToBottom', handleScrollToBottom as EventListener);
    window.addEventListener('chat:findReplyMessage', handleFindReplyMessage as EventListener);
    
    return () => {
      window.removeEventListener('showDraftMessage', handleDraftMessage as EventListener);
      window.removeEventListener('chat:scrollToBottom', handleScrollToBottom as EventListener);
      window.removeEventListener('chat:findReplyMessage', handleFindReplyMessage as EventListener);
    };
  }, [handleScrollToBottom, displayedMessages, loadHistoryUntilMessage, getViewport, scrollToBottom]);
     
  // Mention helpers
  const closeMentions = useCallback(() => {
    setMentionOpen(false);
    setMentionQuery('');
    setHighlightedIndex(0);
  }, []);
  
  const insertMention = useCallback((selectedItem: any) => {
    if (!selectedItem || !textareaRef.current) return;
    
    const textarea = textareaRef.current;
    const currentValue = textarea.value;
    const cursorPosition = textarea.selectionStart || 0;
    
    // Replace from @ to cursor with @username 
    const beforeMention = currentValue.substring(0, mentionTriggerIndex);
    const afterMention = currentValue.substring(cursorPosition);
    const newValue = beforeMention + `@${selectedItem.username} ` + afterMention;
    
    setInputValue(newValue);
    closeMentions();
    
    // Set cursor after the inserted mention
    setTimeout(() => {
      const newCursorPosition = beforeMention.length + selectedItem.username.length + 2;
      textarea.setSelectionRange(newCursorPosition, newCursorPosition);
      textarea.focus();
    }, 0);
  }, [mentionTriggerIndex, closeMentions]);
  
  const handleSendMessage = useCallback(async () => {
    const content = inputValue.trim();
    if (!content) return;

    setInputValue('');
    closeMentions(); // Close mentions on send

    try {
      // sendMessage in useRealtimeChat handles auto-creating chat if no activeChat
      await sendMessage(content, replyTarget?.id);
      setReplyTarget(null); // Clear reply target after sending

      // Smooth scroll to bottom after sending
      setTimeout(() => {
        scrollToBottom(scrollAreaRef, { force: true });
      }, 100);
    } catch (error) {
      logger.error('Failed to send message', error, { component: 'ChatInterface' });
    }
  }, [inputValue, sendMessage, replyTarget, closeMentions, scrollToBottom]);
  
  // Create properly ordered displayedItems that match MentionsDropdown visual order
  const displayedItems = React.useMemo(() => {
    const filteredItems = filterMentions(mentionQuery);
    const telegramUsers = filteredItems.filter(item => item.group === 'telegram');
    const managers = filteredItems.filter(item => item.group === 'manager');
    return [...telegramUsers, ...managers]; // Telegram first, then managers
  }, [filterMentions, mentionQuery]);

  const handleKeyPress = useCallback((e: React.KeyboardEvent) => {
    if (mentionOpen) {
      if (displayedItems.length === 0) return; // Guard against empty list
      
      if (e.key === 'ArrowDown') {
        e.preventDefault();
        setHighlightedIndex(prev => (prev + 1) % displayedItems.length);
        return;
      }
      if (e.key === 'ArrowUp') {
        e.preventDefault(); 
        setHighlightedIndex(prev => prev === 0 ? displayedItems.length - 1 : prev - 1);
        return;
      }
      if (e.key === 'Enter' || e.key === 'Tab') {
        e.preventDefault();
        // Use the item directly from displayedItems
        const selectedItem = displayedItems[highlightedIndex];
        if (selectedItem) {
          insertMention(selectedItem);
        }
        return;
      }
      if (e.key === 'Escape') {
        e.preventDefault();
        closeMentions();
        return;
      }
    }
    // Enter = send, Shift+Enter or Alt+Enter (Option+Enter on Mac) = new line
    if (e.key === 'Enter' && !e.shiftKey && !e.altKey) {
      e.preventDefault();
      handleSendMessage();
    }
    // Alt+Enter (Option+Enter) - insert new line
    if (e.key === 'Enter' && e.altKey) {
      e.preventDefault();
      const textarea = e.target as HTMLTextAreaElement;
      const start = textarea.selectionStart;
      const end = textarea.selectionEnd;
      const newValue = inputValue.substring(0, start) + '\n' + inputValue.substring(end);
      setInputValue(newValue);
      // Set cursor position after the newline
      setTimeout(() => {
        textarea.selectionStart = textarea.selectionEnd = start + 1;
      }, 0);
    }
  }, [handleSendMessage, mentionOpen, displayedItems, highlightedIndex, insertMention, closeMentions, inputValue]);
  
  const handleInputChange = useCallback((e: React.ChangeEvent<HTMLTextAreaElement>) => {
    const value = e.target.value;
    const cursorPosition = e.target.selectionStart || 0;
    
    setInputValue(value);

    // Check for mention trigger
    const beforeCursor = value.substring(0, cursorPosition);
    const mentionMatch = beforeCursor.match(/(?:^|\s)@([A-Za-z0-9_]{0,30})$/);
    
    if (mentionMatch) {
      const triggerIndex = beforeCursor.lastIndexOf('@');
      const query = mentionMatch[1];
      
      setMentionTriggerIndex(triggerIndex);
      setMentionQuery(query);
      setHighlightedIndex(0);
      
      if (!mentionOpen) {
        setMentionOpen(true);
        mentions.fetchIfNeeded();
      }
    } else {
      if (mentionOpen) {
        closeMentions();
      }
    }

    // Debounced typing индикатор для оптимизации
    if (value.length > 0) {
      startTyping();
    } else {
      stopTyping();
    }
  }, [startTyping, stopTyping, mentionOpen, mentions, closeMentions]);

  // Handle focus loss - stop typing indicator  
  const handleInputBlur = useCallback(() => {
    stopTyping();
    // Close mentions with delay to allow clicks on dropdown
    setTimeout(() => {
      if (mentionOpen) {
        closeMentions();
      }
    }, 200);
  }, [stopTyping, mentionOpen, closeMentions]);

  // Handle page/tab switching - stop typing indicator and preserve scroll position
  const forcePinOnReturnRef = useRef(false);
  
  useEffect(() => {
    let wasAtBottom = false;
    
    const handleExternalPlayerOpened = () => {
      forcePinOnReturnRef.current = true;
    };
    
    const handleVisibilityChange = () => {
      if (document.hidden) {
        stopTyping();
        // Check if user was at bottom before leaving tab
        const viewport = scrollAreaRef.current?.querySelector('[data-radix-scroll-area-viewport]') as HTMLElement;
        if (viewport) {
          const { scrollTop, scrollHeight, clientHeight } = viewport;
          wasAtBottom = scrollTop + clientHeight >= scrollHeight - 50; // 50px tolerance
        }
      } else if (wasAtBottom || forcePinOnReturnRef.current) {
        // Restore scroll position when returning to tab with multiple forced scrolls
        const viewport = scrollAreaRef.current?.querySelector('[data-radix-scroll-area-viewport]') as HTMLElement;
        if (viewport) {
          const forceScroll = () => {
            viewport.scrollTop = viewport.scrollHeight;
          };
          
          // Multiple forced scrolls to ensure proper positioning
          requestAnimationFrame(forceScroll);
          setTimeout(forceScroll, 120);
          setTimeout(forceScroll, 400);
          setTimeout(forceScroll, 900);
        }
        forcePinOnReturnRef.current = false;
      }
    };
    
    const handleFocus = () => {
      if (forcePinOnReturnRef.current) {
        const viewport = scrollAreaRef.current?.querySelector('[data-radix-scroll-area-viewport]') as HTMLElement;
        if (viewport) {
          const forceScroll = () => {
            viewport.scrollTop = viewport.scrollHeight;
          };
          
          requestAnimationFrame(forceScroll);
          setTimeout(forceScroll, 120);
          setTimeout(forceScroll, 400);
        }
        forcePinOnReturnRef.current = false;
      }
    };
    
    const handleBeforeUnload = () => {
      stopTyping();
    };
    
    window.addEventListener('chat:externalPlayerOpened', handleExternalPlayerOpened);
    document.addEventListener('visibilitychange', handleVisibilityChange);
    window.addEventListener('focus', handleFocus);
    window.addEventListener('beforeunload', handleBeforeUnload);
    return () => {
      window.removeEventListener('chat:externalPlayerOpened', handleExternalPlayerOpened);
      document.removeEventListener('visibilitychange', handleVisibilityChange);
      window.removeEventListener('focus', handleFocus);
      window.removeEventListener('beforeunload', handleBeforeUnload);
    };
  }, [stopTyping, scrollToBottom]);
  
  const handlePresetMessageSelect = useCallback((message: string) => {
    sendMessage(message);
  }, [sendMessage]);
  
  const handleConfirmDraft = useCallback(() => {
    if (draftMessage) {
      sendInteractiveMessage(draftMessage.template_data, draftMessage.name);
      setDraftMessage(null);
    }
  }, [draftMessage, sendInteractiveMessage]);
  
  const handleCancelDraft = useCallback(() => {
    setDraftMessage(null);
  }, []);

  const handleReply = useCallback((message: Message) => {
    setReplyTarget(message);
  }, []);

  const handleCancelReply = useCallback(() => {
    setReplyTarget(null);
    setReplyOverlayHeight(0); // Сброс высоты при отмене
  }, []);
  
  const handleTemplateChange = useCallback((updatedTemplate: MessageTemplate) => {
    setDraftMessage(updatedTemplate);
  }, []);

  // Проверка прав администратора
  const isAdmin = isDeveloper;

  // Theme-aware styles - messages panel should be lighter than sidebar
  const theme = isLightTheme ? {
    main: 'bg-white',
    input: {
      bg: 'bg-[#f4f4f4]',
      border: 'border border-gray-300',
      text: 'text-gray-900',
      placeholder: 'placeholder:text-gray-500'
    },
    border: 'border-gray-300'
  } : {
    main: 'bg-dark-gray',
    input: {
      bg: 'bg-light-gray',
      border: 'border border-white/10',
      text: 'text-white',
      placeholder: 'placeholder:text-gray-400'
    },
    border: 'border-white/10'
  };

  // Группировка сообщений по датам
  const groupedMessages = useMemo(() => {
    const groups: Array<{
      date: Date;
      messages: typeof displayedMessages[0][];
    }> = [];
    displayedMessages.forEach(message => {
      const messageDate = new Date(message.created_at);
      const lastGroup = groups[groups.length - 1];
      if (lastGroup && isSameDay(lastGroup.date, messageDate)) {
        lastGroup.messages.push(message);
      } else {
        groups.push({
          date: messageDate,
          messages: [message]
        });
      }
    });
    return groups;
  }, [displayedMessages]);

  // Мемоизированные условия для отображения интерфейса
  const showWelcomeScreen = useMemo(() => {
    return !initialLoading && chats.length === 0;
  }, [initialLoading, chats.length]);
  
  const showSelectChatPlaceholder = useMemo(() => {
    return false; // Убираем промежуточную заглушку
  }, []);
  
  const showServicesCatalog = useMemo(() => {
    if (!activeChat || displayedMessages.length === 0) {
      return false;
    }
    const lastMessage = displayedMessages[displayedMessages.length - 1];
    return lastMessage.content?.toLowerCase().includes('новый заказ');
  }, [activeChat, displayedMessages]);
  
  return <div className={`h-full flex ${theme.main}`}>
    {/* Main Chat Content */}
    <div className="flex-1 grid grid-rows-[1fr_auto]">
      {/* Content Area */}
      <div className="overflow-hidden">
        {showWelcomeScreen ?
        // Welcome screen с заголовками и предустановленными сообщениями
        <div className="h-full flex flex-col justify-center p-8 overflow-y-auto">
            <div className="max-w-4xl mx-auto w-full text-center">
              {/* Welcome screen content removed */}
            </div>
          </div> : showSelectChatPlaceholder ?
        // Placeholder для выбора чата
        <SelectChatPlaceholder /> : showServicesCatalog ?
        // Каталог услуг для новых заказов
        <ScrollArea className="h-full [&>div>div[style]]:!pr-0">
            <ServicesCatalog />
          </ScrollArea> :
        // Chat interface - только сообщения
        <div className="relative h-full flex flex-col">
            <ScrollArea ref={scrollAreaRef} className="flex-1 p-6 relative">
              <div className="max-w-4xl mx-auto space-y-6 pb-4">
                {displayedMessages.length === 0 && !loadingMessages ? (
                  <div className="text-center text-gray-400 py-8 hidden">
                    
                  </div>
                ) : displayedMessages.length > 0 ? (
                    <OptimizedMessageList
                      messages={displayedMessages}
                      currentUser={user}
                      sendingMessages={sendingMessages}
                      onReply={handleReply}
                      onDelete={deleteMessage}
                      onLoadMore={handleLoadMoreWithAnchor}
                      hasMoreMessages={messageFilter === 'all' ? hasMoreMessages : filteredHasMore}
                      scrollAreaRef={scrollAreaRef}
                    />
                ) : null}
                
                {/* Draft Message */}
                {draftMessage && <DraftMessageBubble template={draftMessage} onConfirm={handleConfirmDraft} onCancel={handleCancelDraft} onEdit={() => {}} onTemplateChange={handleTemplateChange} />}
                
                {/* Typing Indicator */}
                <TypingIndicator typingUsers={typingUsers} />
                
                {/* Invisible sentinel for intersection observer */}
                <div ref={sentinelRef} className="h-1 w-full" />
              </div>
            </ScrollArea>
            
            {/* Scroll to Bottom Button */}
            <ScrollToBottomButton
              visible={!isAtBottom && displayedMessages.length > 0}
              count={newMessagesCount}
              onClick={handleScrollToBottomClick}
              bottomOffset={24}
            />
          </div>}
      </div>


      {/* Input Area - зафиксировано внизу экрана */}
      <div className={`border-t ${theme.border} ${theme.main} flex-shrink-0 min-h-24`}>
        <div className="flex items-center justify-center px-6 h-full">
          <div className="max-w-4xl mx-auto w-full">
            <div className={`flex items-center gap-2 ${theme.input.bg} ${theme.input.border} rounded-[24px] px-3 py-2`}>
              {/* Иконки прикреплений */}
              <div className="flex gap-1 self-center">
                <FileUploadButton disabled={!activeChat} />
              </div>

              {/* Поле ввода */}
              <div ref={inputContainerRef} className="flex-1 flex items-center justify-center relative">
                <AutoResizeTextarea
                  ref={textareaRef}
                  value={inputValue}
                  onChange={handleInputChange}
                  onKeyDown={handleKeyPress}
                  onBlur={handleInputBlur}
                  onHeightChange={setTextareaHeight}
                  placeholder="Напишите запрос"
                  className={`flex-1 border-0 bg-transparent ${theme.input.text} ${theme.input.placeholder} outline-none focus:outline-none focus-visible:outline-none resize-none text-sm focus:placeholder:opacity-0 placeholder:transition-opacity py-1`}
                  minHeight={32}
                  maxHeight={120}
                />
                
                {/* Mentions Dropdown */}
                <MentionsDropdown
                  open={mentionOpen}
                  anchorRef={inputContainerRef}
                  query={mentionQuery}
                  items={displayedItems}
                  highlightedIndex={highlightedIndex}
                  onSelect={(index) => insertMention(displayedItems[index])}
                  onHover={setHighlightedIndex}
                  onRequestClose={closeMentions}
                  isLoading={mentionsLoading}
                  offsetAboveAnchor={replyTarget ? replyOverlayHeight + 8 : 0}
                />

                {/* Reply Preview Overlay */}
                {replyTarget && (
                  <ReplyPreviewOverlay 
                    open={!!replyTarget}
                    anchorRef={inputContainerRef}
                    replyTarget={replyTarget} 
                    onCancel={handleCancelReply}
                    onHeightChange={setReplyOverlayHeight}
                  />
                )}
              </div>

              {/* Кнопка отправки/микрофона в поле ввода */}
              <div className="self-center">
                {inputValue.trim() || sendingMessages.size > 0 ? <Button
                    onClick={handleSendMessage}
                    className="rounded-full bg-accent-red hover:bg-accent-red/90 h-10 w-10 p-0 transition-all duration-300 hover:scale-105 shadow-lg flex-shrink-0"
                    disabled={sendingMessages.size > 0}
                  >
                    {sendingMessages.size > 0 ? (
                      <div className="w-5 h-5 border-2 border-white border-t-transparent rounded-full animate-spin" />
                    ) : (
                      <Send size={20} />
                    )}
                  </Button> : <VoiceRecordButton disabled={!activeChat} />}
              </div>
            </div>
          </div>
        </div>
      </div>

    </div>
  </div>;
});

ChatInterface.displayName = 'ChatInterface';
export default ChatInterface;