import { useState, useEffect, useCallback, useRef, useMemo } from 'react';
import { useAuth } from '@/contexts/AuthContext';
import { logger } from '@/utils/logger';
import * as companyApi from '@/api/company';
import * as chatApi from '@/api/chat';
import * as userApi from '@/api/user_account';
import type { Chat, Message, TypingIndicator, RealtimeChatContextType, Company, MessageFilter } from '@/types/realtime-chat';
import { useNotificationSound } from '@/hooks/useNotificationSound';
import { useToast } from '@/hooks/use-toast';

// Safe platform context usage с правильным импортом
import { usePlatform } from '@/contexts/PlatformContext';

const usePlatformSafe = () => {
  try {
    return usePlatform();
  } catch (error) {
    logger.warn('PlatformContext hook failed', { component: 'useRealtimeChat' });
    return { 
      selectedCompany: null, 
      chatId: undefined, 
      setActiveSection: () => {},
      setSelectedCompany: () => {}
    };
  }
};

export function useRealtimeChat(): RealtimeChatContextType {
  const { user } = useAuth();
  const { selectedCompany, chatId, setActiveSection } = usePlatformSafe();
  const { playNotificationSound } = useNotificationSound();
  const { toast } = useToast();
  
  const [chats, setChats] = useState<Chat[]>([]);
  const [activeChat, setActiveChat] = useState<Chat | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [messageFilter, setMessageFilter] = useState<MessageFilter>('all');
  const [typingUsers, setTypingUsers] = useState<TypingIndicator[]>([]);
  const [initialLoading, setInitialLoading] = useState(true);
  const [loadingMessages, setLoadingMessages] = useState(false);
  const [loadingMoreMessages, setLoadingMoreMessages] = useState(false);
  const [sendingMessages, setSendingMessages] = useState<Set<string>>(new Set());
  const [hasMoreMessages, setHasMoreMessages] = useState(true);
  const [messageOffset, setMessageOffset] = useState(0);
  const [isCreatingChat, setIsCreatingChat] = useState(false);
  
  // Состояние для отфильтрованных сообщений
  const [filteredMessages, setFilteredMessages] = useState<Message[]>([]);
  const [filteredOffset, setFilteredOffset] = useState(0);
  const [filteredHasMore, setFilteredHasMore] = useState(true);
  const [filteredLoading, setFilteredLoading] = useState(false);
  // Removed clientCompany state - admin-only system
  const [companiesCache, setCompaniesCache] = useState<Map<string, Company | null>>(new Map());
  const [isLoadingChats, setIsLoadingChats] = useState(false);

  // Функция для синхронной инициализации scope до первой загрузки
  const getInitialScope = () => {
    // Пробуем получить chatId из URL для определения правильного scope
    if (chatId) {
      // Если есть chatId в URL, попробуем быстро получить его данные из localStorage или сделать быстрый запрос
      try {
        // Быстрая проверка в localStorage для ранее загруженных чатов
        const cachedChats = localStorage.getItem('ww:cached_chats');
        if (cachedChats) {
          const parsedChats = JSON.parse(cachedChats);
          const foundChat = parsedChats.find((c: any) => c.id === chatId);
          if (foundChat?.telegram_supergroup_id) {
            return {
              type: 'supergroup' as const,
              supergroupId: foundChat.telegram_supergroup_id,
              companyId: foundChat.company_id
            };
          } else if (foundChat) {
            return {
              type: 'company' as const,
              companyId: foundChat.company_id || null
            };
          }
        }
      } catch (error) {
        logger.debug('Failed to parse cached chats for initial scope', { error, component: 'useRealtimeChat' });
      }
    }

    // Fallback к saved state из localStorage
    try {
      const savedState = localStorage.getItem('ww:chat.sidebar.state');
      if (savedState) {
        const state = JSON.parse(savedState);
        if (state.selectedSupergroupId && typeof state.selectedSupergroupId === 'number') {
          return {
            type: 'supergroup' as const,
            supergroupId: state.selectedSupergroupId,
            companyId: selectedCompany?.id || null
          };
        }
      }
    } catch (error) {
      logger.debug('Failed to restore scope from localStorage', { error, component: 'useRealtimeChat' });
    }

    // Окончательный fallback к company scope
    return {
      type: 'company' as const,
      companyId: selectedCompany?.id || null
    };
  };

  // Chat scope state - определяет контекст для загрузки чатов
  const [chatScope, setChatScope] = useState(() => getInitialScope());
  const [isScopeInitialized, setIsScopeInitialized] = useState(false);

  const typingTimeoutRef = useRef<NodeJS.Timeout>();
  const isTypingRef = useRef(false);
  const chatsSubscriptionRef = useRef<any>(null);
  const isSubscribedToChatsRef = useRef(false);

  // Подписка на глобальные обновления чатов
  const subscribeToChatsUpdates = useCallback(() => {
    if (!user || isSubscribedToChatsRef.current) return;

    // Отписываемся от предыдущей подписки
    if (chatsSubscriptionRef.current) {
      // WSE handles unsubscription automatically;
      chatsSubscriptionRef.current = null;
      isSubscribedToChatsRef.current = false;
    }

    logger.debug('Subscribing to global chats updates', { 
      userId: user.id, 
      companyId: selectedCompany?.id, 
      chatScope,
      component: 'useRealtimeChat' 
    });

    // WSE event listeners for chat list updates
    const handleChatCreated = async (event: CustomEvent) => {
      const newChatData = event.detail;
      logger.debug('New chat created via WSE', { chatId: newChatData.chat_id || newChatData.id, name: newChatData.name, component: 'useRealtimeChat' });

      // Reload chats to get full data with participants
      try {
        const userChats = await chatApi.getChats(false, 100, 0);
        const newChat = userChats.find(chat => chat.id === (newChatData.chat_id || newChatData.id));

        if (newChat) {
          setChats(prev => {
            const exists = prev.some(chat => chat.id === newChat.id);
            if (!exists) {
              return [newChat, ...prev];
            }
            return prev;
          });
        }
      } catch (error) {
        logger.error('Error loading new chat data', error, { component: 'useRealtimeChat' });
      }
    };

    const handleChatUpdated = (event: CustomEvent) => {
      const updatedChatData = event.detail;
      logger.debug('Chat updated via WSE', { chatId: updatedChatData.chat_id || updatedChatData.id, component: 'useRealtimeChat' });

      setChats(prev => prev.map(chat =>
        chat.id === (updatedChatData.chat_id || updatedChatData.id)
          ? {
              ...chat,
              name: updatedChatData.name || chat.name,
              metadata: updatedChatData.metadata || chat.metadata,
              updated_at: updatedChatData.updated_at || chat.updated_at,
              is_active: updatedChatData.is_active ?? chat.is_active
            }
          : chat
      ));

      // Update active chat if it's the one being updated
      setActiveChat(prev =>
        prev?.id === (updatedChatData.chat_id || updatedChatData.id)
          ? {
              ...prev,
              name: updatedChatData.name || prev.name,
              metadata: updatedChatData.metadata || prev.metadata,
              updated_at: updatedChatData.updated_at || prev.updated_at,
              is_active: updatedChatData.is_active ?? prev.is_active
            }
          : prev
      );
    };

    const handleChatDeleted = (event: CustomEvent) => {
      const deletedChatData = event.detail;
      logger.debug('Chat deleted via WSE', { chatId: deletedChatData.chat_id || deletedChatData.id, component: 'useRealtimeChat' });

      setChats(prev => prev.filter(chat => chat.id !== (deletedChatData.chat_id || deletedChatData.id)));

      // Clear active chat if it was deleted
      setActiveChat(prev => {
        if (prev?.id === (deletedChatData.chat_id || deletedChatData.id)) {
          setMessages([]);
          setTypingUsers([]);
          return null;
        }
        return prev;
      });
    };

    // Add event listeners
    window.addEventListener('chatCreated', handleChatCreated as EventListener);
    window.addEventListener('chatUpdated', handleChatUpdated as EventListener);
    window.addEventListener('chatDeleted', handleChatDeleted as EventListener);

    chatsSubscriptionRef.current = {
      userId: user.id,
      companyId: chatScope.type === 'company' ? (chatScope.companyId || null) : null,
      supergroupId: chatScope.type === 'supergroup' ? chatScope.supergroupId : null
    };
    isSubscribedToChatsRef.current = true;

    // Cleanup function
    return () => {
      window.removeEventListener('chatCreated', handleChatCreated as EventListener);
      window.removeEventListener('chatUpdated', handleChatUpdated as EventListener);
      window.removeEventListener('chatDeleted', handleChatDeleted as EventListener);
      isSubscribedToChatsRef.current = false;
    };
  }, [user, selectedCompany?.id, chatScope]);

  // Загрузка чатов пользователя с фильтрацией по компании или супергруппе
  const loadChats = useCallback(async () => {
    if (!user || isLoadingChats || !isScopeInitialized) return;
    
    setIsLoadingChats(true);
    try {
      // Показываем лоадер только если чатов нет (первая загрузка)
      setChats(prev => {
        if (prev.length === 0) {
          setInitialLoading(true);
        }
        return prev;
      });
      
      logger.debug('Loading chats for user', { 
        userId: user.id, 
        chatScope,
        component: 'useRealtimeChat' 
      });
      
      let userChats: Chat[];
      if (chatScope.type === 'supergroup' && chatScope.supergroupId) {
        userChats = await chatApi.getChats(false, 100, 0);
      } else {
        userChats = await chatApi.getChats(false, 100, 0);
      }
      
      logger.info('Chats loaded successfully', { 
        count: userChats.length, 
        scope: chatScope,
        component: 'useRealtimeChat' 
      });
      
      setChats(userChats);
    } catch (error) {
      logger.error('Error loading chats', error, { component: 'useRealtimeChat' });
    } finally {
      setInitialLoading(false);
      setIsLoadingChats(false);
    }
  }, [user, chatScope, isLoadingChats]);

  // Загрузка отфильтрованных сообщений для активного фильтра
  const loadFilteredMessages = useCallback(async (chatId: string, filter: string, reset: boolean = true) => {
    try {
      setFilteredLoading(true);
      
      const limit = 20;
      const offset = reset ? 0 : filteredOffset;
      
      logger.debug('Loading filtered messages', { chatId, filter, offset, limit, reset, component: 'useRealtimeChat' });
      const chatMessages = await chatApi.getMessages(chatId, { limit: limit, offset: offset });
      
      if (reset) {
        // Гидрируем размеры изображений для ВСЕХ image-сообщений первой страницы перед рендером
        let hydratedMessages = [...chatMessages];
        if (chatMessages.length > 0) {
          const imageMessages = chatMessages
            .filter(msg => msg.message_type === 'image' && msg.file_url && !msg.metadata?.imageDimensions);
          
          if (imageMessages.length > 0) {
            try {
              const { imageDimensionsCache } = await import('@/utils/imageDimensionsCache');
              const hydratedImageMessages = await imageDimensionsCache.hydrateMessagesWithLimiter(imageMessages);
              
              hydratedMessages = chatMessages.map(msg => {
                const hydratedMsg = hydratedImageMessages.find(h => h.id === msg.id);
                return hydratedMsg || msg;
              });
            } catch (error) {
              logger.warn('Failed to hydrate image dimensions for filtered messages', error);
            }
          }
        }
        
        // Сортируем по хронологии (старые -> новые) для отображения
        const sortedMessages = [...hydratedMessages].reverse();
        setFilteredMessages(sortedMessages);
        setFilteredOffset(chatMessages.length);
      } else {
        // Гидрируем размеры изображений для старых сообщений
        let hydratedMessages = [...chatMessages];
        const imageMessages = chatMessages
          .filter(msg => msg.message_type === 'image' && msg.file_url && !msg.metadata?.imageDimensions);
        
        if (imageMessages.length > 0) {
          try {
            const { imageDimensionsCache } = await import('@/utils/imageDimensionsCache');
            const hydratedImageMessages = await imageDimensionsCache.hydrateMessagesWithLimiter(imageMessages);
            
            hydratedMessages = chatMessages.map(msg => {
              const hydratedMsg = hydratedImageMessages.find(h => h.id === msg.id);
              return hydratedMsg || msg;
            });
          } catch (error) {
            logger.warn('Failed to hydrate image dimensions for older filtered messages', error);
          }
        }
        
        // Добавляем старые сообщения в начало
        const sortedMessages = [...hydratedMessages].reverse();
        setFilteredMessages(prev => [...sortedMessages, ...prev]);
        setFilteredOffset(prev => prev + chatMessages.length);
      }
      
      // Проверяем есть ли еще сообщения
      setFilteredHasMore(chatMessages.length === limit);
      
    } catch (error) {
      logger.error('Error loading filtered messages', error, { component: 'useRealtimeChat', chatId, filter });
    } finally {
      setFilteredLoading(false);
    }
  }, [filteredOffset]);

  // Загрузка сообщений чата (только последние 20)
  const loadChatMessages = useCallback(async (chatId: string, reset: boolean = true) => {
    try {
      setLoadingMessages(true);
      
      const limit = 20;
      const offset = reset ? 0 : messageOffset;
      
      logger.debug('Loading messages', { chatId, offset, limit, reset, component: 'useRealtimeChat' });
      const chatMessages = await chatApi.getMessages(chatId, { limit: limit, offset: offset });
      
      if (reset) {
        // Жёсткая гидрация размеров изображений для ВСЕХ image-сообщений первой страницы перед рендером
        let hydratedMessages = [...chatMessages];
        if (chatMessages.length > 0) {
          const imageMessages = chatMessages
            .filter(msg => msg.message_type === 'image' && msg.file_url && !msg.metadata?.imageDimensions);
          
          if (imageMessages.length > 0) {
            try {
              const { imageDimensionsCache } = await import('@/utils/imageDimensionsCache');
              // Ждём размеры для ВСЕХ изображений без таймаута, но с лимитом параллелизма
              const hydratedImageMessages = await imageDimensionsCache.hydrateMessagesWithLimiter(imageMessages);
              
              // Заменяем оригинальные сообщения гидрированными
              hydratedMessages = chatMessages.map(msg => {
                const hydratedMsg = hydratedImageMessages.find(h => h.id === msg.id);
                return hydratedMsg || msg;
              });
            } catch (error) {
              logger.warn('Failed to hydrate image dimensions', error);
            }
          }
        }
        
        // Сортируем по хронологии (старые -> новые) для отображения
        const sortedMessages = [...hydratedMessages].reverse();
        setMessages(sortedMessages);
        setMessageOffset(chatMessages.length);
      } else {
        // Гидрируем размеры изображений для старых сообщений перед добавлением (сохраняем скролл-якорь)
        let hydratedMessages = [...chatMessages];
        const imageMessages = chatMessages
          .filter(msg => msg.message_type === 'image' && msg.file_url && !msg.metadata?.imageDimensions);
        
        if (imageMessages.length > 0) {
          try {
            const { imageDimensionsCache } = await import('@/utils/imageDimensionsCache');
            const hydratedImageMessages = await imageDimensionsCache.hydrateMessagesWithLimiter(imageMessages);
            
            hydratedMessages = chatMessages.map(msg => {
              const hydratedMsg = hydratedImageMessages.find(h => h.id === msg.id);
              return hydratedMsg || msg;
            });
          } catch (error) {
            logger.warn('Failed to hydrate image dimensions for older messages', error);
          }
        }
        
        // Добавляем старые сообщения в начало
        const sortedMessages = [...hydratedMessages].reverse();
        setMessages(prev => [...sortedMessages, ...prev]);
        setMessageOffset(prev => prev + chatMessages.length);
      }
      
      // Проверяем есть ли еще сообщения
      setHasMoreMessages(chatMessages.length === limit);
      
    } catch (error) {
      logger.error('Error loading chat messages', error, { component: 'useRealtimeChat', chatId });
    } finally {
      setLoadingMessages(false);
    }
  }, [messageOffset]);

  // Загрузка более старых сообщений для infinite scroll
  const loadMoreMessages = useCallback(async () => {
    if (!activeChat || loadingMoreMessages) return;
    
    if (messageFilter === 'all') {
      if (!hasMoreMessages) return;
      
      try {
        setLoadingMoreMessages(true);
        await loadChatMessages(activeChat.id, false);
      } catch (error) {
        logger.error('Error loading more messages', error, { component: 'useRealtimeChat' });
      } finally {
        setLoadingMoreMessages(false);
      }
    } else {
      if (!filteredHasMore) return;
      
      try {
        setLoadingMoreMessages(true);
        await loadFilteredMessages(activeChat.id, messageFilter, false);
      } catch (error) {
        logger.error('Error loading more filtered messages', error, { component: 'useRealtimeChat' });
      } finally {
        setLoadingMoreMessages(false);
      }
    }
    }, [activeChat, loadingMoreMessages, hasMoreMessages, filteredHasMore, messageFilter, loadChatMessages, loadFilteredMessages]);

  // Обработчик смены фильтра
  const handleFilterChange = useCallback(async (newFilter: MessageFilter) => {
    setMessageFilter(newFilter);
    
    if (newFilter === 'all') {
      // Для 'all' используем обычные сообщения
      setFilteredMessages([]);
      setFilteredOffset(0);
      setFilteredHasMore(true);
    } else if (activeChat) {
      // Для конкретного фильтра загружаем отфильтрованные сообщения
      await loadFilteredMessages(activeChat.id, newFilter, true);
    }
  }, [activeChat, loadFilteredMessages]);

  // Removed loadClientCompany - admin-only system

  // Загрузка компании для конкретного чата (с кэшированием)
  const loadCompanyForChat = useCallback(async (chatId: string, forceRefresh = false): Promise<Company | null> => {
    // Проверяем кэш только если не принудительное обновление
    if (!forceRefresh && companiesCache.has(chatId)) {
      return companiesCache.get(chatId) || null;
    }

    try {
      // Get chat details to find company_id
      const chatDetail = await chatApi.getChatById(chatId);
      if (!chatDetail || !chatDetail.company_id) {
        setCompaniesCache(prev => new Map(prev.set(chatId, null)));
        return null;
      }

      // Get company details
      const company = await companyApi.getCompanyById(chatDetail.company_id);
      setCompaniesCache(prev => new Map(prev.set(chatId, company)));

      return company;
    } catch (error) {
      logger.error('Error in loadCompanyForChat', error, { component: 'useRealtimeChat', chatId });
      setCompaniesCache(prev => new Map(prev.set(chatId, null)));
      return null;
    }
  }, [companiesCache]);

  // Очистка кэша компаний для конкретного чата
  const clearCompanyCache = useCallback((chatId?: string) => {
    if (chatId) {
      setCompaniesCache(prev => {
        const newCache = new Map(prev);
        newCache.delete(chatId);
        return newCache;
      });
    } else {
      setCompaniesCache(new Map());
    }
  }, []);

  // Функция проверки соответствия сообщения фильтру (как в useMemo)
  const messageMatchesFilter = useCallback((message: Message, filter: string): boolean => {
    if (filter === 'all') return true;
    
    const getFileExtension = (msg: Message): string | null => {
      // Поддержка legacy типов и новых: 'file' и 'document'
      if (!['file'].includes(msg.message_type) && (msg.message_type as any) !== 'document') return null;
      const fileName = msg.file_name || msg.file_url;
      if (!fileName) return null;
      const cleanFileName = fileName.split('?')[0];
      const match = cleanFileName.match(/\.([^.]+)$/);
      return match ? match[1].toLowerCase() : null;
    };
    
    switch (filter) {
      case 'images':
        // Поддержка legacy типов: 'image' и 'photo' (через type assertion для legacy данных)
        // Но только если есть file_url (не пустые сообщения)
        return (message.message_type === 'image' || (message.message_type as any) === 'photo') && 
               Boolean(message.file_url);
      case 'voice':
        return message.message_type === 'voice';
      case 'pdf':
        const pdfExt = getFileExtension(message);
        return pdfExt === 'pdf';
      case 'doc':
        const docExt = getFileExtension(message);
        const isDocFile = docExt === 'doc' || docExt === 'docx';
        const hasGoogleDocsLink = message.content && 
          message.content.includes('docs.google.com/document');
        return isDocFile || hasGoogleDocsLink;
      case 'xls':
        const xlsExt = getFileExtension(message);
        const isXlsFile = xlsExt === 'xls' || xlsExt === 'xlsx';
        const hasGoogleSheetsLink = message.content && 
          (message.content.includes('docs.google.com/spreadsheets') || 
           message.content.includes('sheets.google.com'));
        return isXlsFile || hasGoogleSheetsLink;
      case 'other':
        // Файлы (включая legacy 'document') но НЕ известные расширения
        if (!['file'].includes(message.message_type) && (message.message_type as any) !== 'document') return false;
        
        const fileName = message.file_name || message.file_url;
        if (!fileName) return false; // Нет имени файла - не файл
        
        const otherExt = getFileExtension(message);
        // Если нет расширения или расширение не в списке известных - это Other
        return !otherExt || !['pdf', 'doc', 'docx', 'xls', 'xlsx'].includes(otherExt);
      default:
        return true;
    }
  }, []);

  // Reference for active chat subscription cleanup
  const chatSubscriptionCleanupRef = useRef<(() => void) | null>(null);

  // Subscribe to chat messages via WSE events
  const subscribeToChat = useCallback((chatId: string) => {
    // Cleanup previous chat subscription
    if (chatSubscriptionCleanupRef.current) {
      chatSubscriptionCleanupRef.current();
      chatSubscriptionCleanupRef.current = null;
    }

    logger.debug('Subscribing to chat messages via WSE', { chatId, component: 'useRealtimeChat' });

    // Handler for new messages
    const handleMessageCreated = async (event: CustomEvent) => {
      const messageData = event.detail;

      // Only process messages for the subscribed chat
      if (messageData.chat_id !== chatId) return;

      logger.info('Real-time message received via WSE', {
        messageId: messageData.id,
        senderId: messageData.sender_id,
        chatId: messageData.chat_id,
        content: messageData.content?.substring(0, 50) + '...',
        component: 'useRealtimeChat'
      });

      let processedMessage = messageData as Message;

      // For image messages, get dimensions first
      if (processedMessage.message_type === 'image' && processedMessage.file_url && !processedMessage.metadata?.imageDimensions) {
        try {
          const { imageDimensionsCache } = await import('@/utils/imageDimensionsCache');
          const dimensions = await imageDimensionsCache.getDimensions(processedMessage.file_url);

          if (dimensions) {
            processedMessage = {
              ...processedMessage,
              metadata: {
                ...processedMessage.metadata,
                imageDimensions: dimensions
              }
            };
          }
        } catch (error) {
          logger.warn('Failed to get dimensions for new image message', error);
        }
      }

      // Normalize reply_to
      if (Array.isArray(processedMessage.reply_to) || !processedMessage.reply_to || (typeof processedMessage.reply_to === 'object' && Object.keys(processedMessage.reply_to).length === 0)) {
        processedMessage = { ...processedMessage, reply_to: null };
      }

      // Add message to state
      setMessages(prev => {
        const exists = prev.some(m => m.id === processedMessage.id);
        if (exists) {
          logger.debug('Message already exists, ignoring', { messageId: processedMessage.id, component: 'useRealtimeChat' });
          return prev;
        }

        // Check for optimistic message replacement
        if (processedMessage.sender_id === user?.id) {
          const optimisticIndex = prev.findIndex(m => {
            if (!m.id.startsWith('temp-')) return false;
            if (m.content !== processedMessage.content || m.reply_to_id !== processedMessage.reply_to_id) return false;
            const optimisticTime = new Date(m.created_at).getTime();
            const realTime = new Date(processedMessage.created_at).getTime();
            return Math.abs(realTime - optimisticTime) <= 15000;
          });

          if (optimisticIndex !== -1) {
            const optimisticMessage = prev[optimisticIndex];
            logger.debug('Replacing optimistic message with real one', {
              tempId: optimisticMessage.id,
              realId: processedMessage.id,
              component: 'useRealtimeChat'
            });

            setSendingMessages(currentSending => {
              const newSet = new Set(currentSending);
              newSet.delete(optimisticMessage.id);
              return newSet;
            });

            const newMessages = [...prev];
            newMessages[optimisticIndex] = processedMessage;
            return newMessages;
          }
        }

        return [...prev, processedMessage];
      });

      if (messageData.sender_id !== user?.id) {
        playNotificationSound();
      }
    };

    // Handler for message updates
    const handleMessageUpdated = (event: CustomEvent) => {
      const messageData = event.detail;
      if (messageData.chat_id !== chatId) return;

      logger.debug('Message updated via WSE', { messageId: messageData.id, component: 'useRealtimeChat' });
      setMessages(prev => prev.map(m => m.id === messageData.id ? { ...m, ...messageData } : m));
    };

    // Handler for message deletions
    const handleMessageDeleted = (event: CustomEvent) => {
      const messageData = event.detail;
      if (messageData.chat_id !== chatId) return;

      logger.debug('Message deleted via WSE', { messageId: messageData.id, component: 'useRealtimeChat' });
      setMessages(prev => prev.filter(m => m.id !== messageData.id));
    };

    // Handler for typing indicator
    const handleUserTyping = (event: CustomEvent) => {
      const data = event.detail;
      if (data.chat_id !== chatId || data.user_id === user?.id) return;

      setTypingUsers(prev => {
        const filtered = prev.filter(t => t.user_id !== data.user_id);
        return [...filtered, data as TypingIndicator];
      });
    };

    // Handler for typing stop
    const handleUserStoppedTyping = (event: CustomEvent) => {
      const data = event.detail;
      if (data.chat_id !== chatId) return;

      setTypingUsers(prev => prev.filter(t => t.user_id !== data.user_id));
    };

    // Handler for messages read
    const handleMessagesRead = (event: CustomEvent) => {
      const data = event.detail;
      if (data.chat_id !== chatId) return;

      setMessages(prev => prev.map(m => {
        if (m.id === data.message_id) {
          const existingReads = m.read_by || [];
          const hasRead = existingReads.some(r => r.user_id === data.user_id);
          if (!hasRead) {
            return { ...m, read_by: [...existingReads, data] };
          }
        }
        return m;
      }));
    };

    // Add event listeners
    window.addEventListener('messageCreated', handleMessageCreated as EventListener);
    window.addEventListener('messageUpdated', handleMessageUpdated as EventListener);
    window.addEventListener('messageDeleted', handleMessageDeleted as EventListener);
    window.addEventListener('userTyping', handleUserTyping as EventListener);
    window.addEventListener('userStoppedTyping', handleUserStoppedTyping as EventListener);
    window.addEventListener('messagesRead', handleMessagesRead as EventListener);

    // Store cleanup function
    chatSubscriptionCleanupRef.current = () => {
      logger.debug('Cleaning up chat subscription', { chatId, component: 'useRealtimeChat' });
      window.removeEventListener('messageCreated', handleMessageCreated as EventListener);
      window.removeEventListener('messageUpdated', handleMessageUpdated as EventListener);
      window.removeEventListener('messageDeleted', handleMessageDeleted as EventListener);
      window.removeEventListener('userTyping', handleUserTyping as EventListener);
      window.removeEventListener('userStoppedTyping', handleUserStoppedTyping as EventListener);
      window.removeEventListener('messagesRead', handleMessagesRead as EventListener);
    };

    logger.debug('Chat subscription active', { chatId, component: 'useRealtimeChat' });
  }, [user?.id, playNotificationSound]);

  const selectChat = useCallback(async (chatId: string, updateUrl: boolean = true) => {
    logger.debug('Selecting chat', { chatId, updateUrl, component: 'useRealtimeChat' });
    
    // Если выбираем уже активный чат, просто скроллим вниз
    if (activeChat?.id === chatId) {
      logger.debug('Already selected chat, scrolling to bottom', { chatId, component: 'useRealtimeChat' });
      window.dispatchEvent(new CustomEvent('chat:scrollToBottom', { detail: { force: true } }));
      return;
    }
    
    const chat = chats.find(c => c.id === chatId);
    if (!chat) {
      logger.error('Chat not found', undefined, { chatId, component: 'useRealtimeChat' });
      return;
    }

    // Отписываемся от предыдущего чата
    if (activeChat) {
      // WSE handles chat unsubscription;
    }

    // Сразу устанавливаем активный чат для мгновенного переключения UI
    setActiveChat(chat);
    setMessages([]);
    setMessageOffset(0);
    setHasMoreMessages(true);
    
    // Сбрасываем фильтр сообщений на "все" при переключении чата
    setMessageFilter('all');
    
    // Обновляем URL если нужно
    if (updateUrl && setActiveSection) {
      setActiveSection('chat', chatId);
    }
    
    // ВАЖНО: Подписываемся на обновления ПЕРВЫМИ, чтобы не пропустить новые сообщения
    subscribeToChat(chat.id);
    
    // Загружаем данные в фоне
    try {
      await loadChatMessages(chat.id);
      // Removed loadClientCompany call - admin-only system
      
      // Помечаем сообщения как прочитанные
      if (user?.id) {
        const unreadMessages = messages.filter(message => {
          const isRead = message.read_by?.some(read => read.user_id === user.id);
          return !isRead && message.sender_id !== user.id;
        });
        
        unreadMessages.forEach(message => {
          chatApi.markAsRead(activeChat?.id || "", { message_ids: [message.id] });
        });
      }
    } catch (error) {
      logger.error('Error loading chat data', error, { component: 'useRealtimeChat', chatId: chat.id });
    }
  }, [chats, activeChat, loadChatMessages, user?.id, messages, subscribeToChat, setActiveSection]);

  // Создание нового чата с привязкой к выбранной компании
  const createChat = useCallback(async (name: string, type: 'direct' | 'group' | 'company' = 'direct', participantIds: string[] = []): Promise<Chat> => {
    if (!user) {
      throw new Error('Пользователь не авторизован');
    }

    // Предотвращаем множественное создание чатов
    if (isCreatingChat) {
      logger.warn('Chat creation already in progress, skipping', { component: 'useRealtimeChat' });
      throw new Error('Чат уже создается');
    }

    setIsCreatingChat(true);
    logger.info('Creating chat', { 
      name, 
      type, 
      userId: user.id, 
      participantIds: participantIds.length, 
      companyId: chatScope.companyId, 
      component: 'useRealtimeChat' 
    });
    
    try {
      // User profile is now managed via /auth/me endpoint and event sourcing
      // No need to check/create profile here - authentication handles it
      logger.info('Creating chat (profile managed via auth)', { userId: user.id, component: 'useRealtimeChat' });

      const newChat = await chatApi.createChat({ name: name, chat_type: type, company_id: chatScope.companyId || undefined, participant_ids: participantIds });
      logger.info('Chat created successfully', { chatId: newChat.id, name, component: 'useRealtimeChat' });
      
      setChats(prev => [newChat, ...prev]);
      
      return newChat;
    } catch (error) {
      logger.error('Error in createChat', error, { component: 'useRealtimeChat', name, type });
      throw error;
    } finally {
      setIsCreatingChat(false);
    }
  }, [user, isCreatingChat, chatScope]);

  // Добавление участников
  const addParticipants = useCallback(async (chatId: string, userIds: string[]) => {
    await Promise.all(userIds.map((uid: string) => chatApi.addParticipant(chatId, { user_id: uid })));
    // Перезагружаем чаты для обновления участников
    if (user) {
      let userChats: Chat[];
      if (chatScope.type === 'supergroup' && chatScope.supergroupId) {
        userChats = await chatApi.getChats(false, 100, 0);
      } else {
        userChats = await chatApi.getChats(false, 100, 0);
      }
      setChats(userChats);
    }
  }, [user, chatScope]);

  // Отправка текстового сообщения
  const sendMessage = useCallback(async (content: string, replyToId?: string) => {
    if (!user) {
      logger.error('Cannot send message: no user', undefined, { component: 'useRealtimeChat' });
      return;
    }

    // Если нет активного чата, создаем новый автоматически
    if (!activeChat) {
      logger.info('No active chat, creating new chat automatically', { component: 'useRealtimeChat' });
      try {
        // Генерируем название чата из первых слов сообщения (макс 30 символов)
        const chatName = content.length > 30 ? content.substring(0, 27) + '...' : content;
        
        // Создаем новый чат (тип определяется автоматически в зависимости от пользователя)
        const newChat = await createChat(chatName, 'direct');
        logger.info('Auto-created chat', { chatId: newChat.id, chatName, component: 'useRealtimeChat' });
        
        // Выбираем чат (устанавливает real-time подписку)
        await selectChat(newChat.id);
        logger.info('Chat selected with real-time subscription active', { chatId: newChat.id, component: 'useRealtimeChat' });
        
        // Создаем оптимистичное сообщение для немедленного отображения
        const optimisticMessage: Message = {
          id: `temp-${Date.now()}`,
          chat_id: newChat.id,
          sender_id: user.id,
          content: content,
          message_type: 'text',
          reply_to_id: replyToId || null,
          file_url: null,
          file_name: null,
          file_size: null,
          file_type: null,
          voice_duration: null,
          created_at: new Date().toISOString(),
          updated_at: new Date().toISOString(),
          is_edited: false,
          is_deleted: false,
          metadata: {},
          sender_profile: {
            first_name: user.user_metadata?.first_name || 'You',
            last_name: user.user_metadata?.last_name || '',
            avatar_url: user.user_metadata?.avatar_url || null,
            type: user.user_metadata?.user_type || 'ww_manager'
          },
          reply_to: replyToId ? messages.find(m => m.id === replyToId) : undefined
        };
        
        setMessages([optimisticMessage]);
        
        // Отправляем сообщение напрямую через сервис
        await chatApi.sendMessage(newChat.id, { content: content, message_type: "text", reply_to_id: replyToId });
        logger.info('Message sent to new chat', { chatId: newChat.id, component: 'useRealtimeChat' });
        
        return; // Выходим после успешной отправки
      } catch (error) {
        logger.error('Error auto-creating chat or sending message', error, { component: 'useRealtimeChat' });
        return;
      }
    }

    logger.debug('Sending message', { contentLength: content.length, chatId: activeChat.id, component: 'useRealtimeChat' });
    
    // Создаем временный ID для оптимистичного обновления
    const tempId = `temp-${Date.now()}-${Math.random()}`;
    
    // Добавляем сообщение локально для мгновенного отображения
    const optimisticMessage: Message = {
      id: tempId,
      chat_id: activeChat.id,
      sender_id: user.id,
      content: content,
      message_type: 'text',
      reply_to_id: replyToId || null,
      file_url: null,
      file_name: null,
      file_size: null,
      file_type: null,
      voice_duration: null,
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
      is_edited: false,
      is_deleted: false,
      metadata: {},
      sender_profile: {
        first_name: user.user_metadata?.first_name || 'You',
        last_name: user.user_metadata?.last_name || '',
        avatar_url: user.user_metadata?.avatar_url || null,
        type: user.user_metadata?.user_type || 'ww_manager'
      },
      reply_to: replyToId ? messages.find(m => m.id === replyToId) : undefined
    };

    setMessages(prev => [...prev, optimisticMessage]);
    setSendingMessages(prev => new Set([...prev, tempId]));
    
    try {
      const message = await chatApi.sendMessage(activeChat.id, { content: content, message_type: "text", reply_to_id: replyToId });
      logger.debug('Message sent successfully', { messageId: message.id, chatId: activeChat.id, component: 'useRealtimeChat' });
      
      // Заменяем временное сообщение на реальное
      setMessages(prev => prev.map(m => m.id === tempId ? message : m));
      setSendingMessages(prev => {
        const newSet = new Set(prev);
        newSet.delete(tempId);
        return newSet;
      });
    } catch (error) {
      logger.error('Error sending message', error, { component: 'useRealtimeChat', chatId: activeChat.id });
      
      // Удаляем неудачное сообщение
      setMessages(prev => prev.filter(m => m.id !== tempId));
      setSendingMessages(prev => {
        const newSet = new Set(prev);
        newSet.delete(tempId);
        return newSet;
      });
    }
    
    // Останавливаем индикатор печати
    if (isTypingRef.current) {
      await chatApi.stopTyping(activeChat.id);
      isTypingRef.current = false;
    }
  }, [user, activeChat, createChat, chats]);

  // Отправка файла
  const sendFile = useCallback(async (file: File, replyToId?: string) => {
    if (!user || !activeChat) return;

    // Determine message type based on file
    const isImage = file.type.startsWith('image/');
    const messageType = isImage ? 'image' : 'file';

    // Create optimistic message
    const tempId = `temp-${Date.now()}-${Math.random()}`;
    const optimisticMessage: Message = {
      id: tempId,
      chat_id: activeChat.id,
      sender_id: user.id,
      content: file.name,
      message_type: messageType,
      reply_to_id: replyToId || null,
      file_url: URL.createObjectURL(file), // Temporary local URL for preview
      file_name: file.name,
      file_size: file.size,
      file_type: file.type,
      voice_duration: null,
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
      is_edited: false,
      is_deleted: false,
      metadata: { uploading: true },
      sender_profile: {
        first_name: user.user_metadata?.first_name || 'You',
        last_name: user.user_metadata?.last_name || '',
        avatar_url: user.user_metadata?.avatar_url || null,
        type: user.user_metadata?.user_type || 'ww_manager'
      },
      reply_to: replyToId ? messages.find(m => m.id === replyToId) : undefined
    };

    setMessages(prev => [...prev, optimisticMessage]);
    setSendingMessages(prev => new Set([...prev, tempId]));

    try {
      // Upload file first
      const uploadResult = await chatApi.uploadChatFile(activeChat.id, file);

      if (!uploadResult.success || !uploadResult.file_url) {
        throw new Error(uploadResult.error || 'File upload failed');
      }

      // Send message with file URL
      await chatApi.sendMessage(activeChat.id, {
        content: file.name,
        message_type: messageType,
        reply_to_id: replyToId,
        file_url: uploadResult.file_url,
        file_name: uploadResult.file_name,
        file_size: uploadResult.file_size,
        file_type: uploadResult.file_type,
      });

      // Remove optimistic message - WSE will bring the real one
      setSendingMessages(prev => {
        const newSet = new Set(prev);
        newSet.delete(tempId);
        return newSet;
      });

      logger.debug('File message sent', { chatId: activeChat.id, fileName: file.name, component: 'useRealtimeChat' });

    } catch (error) {
      logger.error('Error sending file', error, { component: 'useRealtimeChat', chatId: activeChat.id });

      // Remove failed optimistic message
      setMessages(prev => prev.filter(m => m.id !== tempId));
      setSendingMessages(prev => {
        const newSet = new Set(prev);
        newSet.delete(tempId);
        return newSet;
      });
    }
  }, [user, activeChat, messages]);

  // Отправка голосового сообщения
  const sendVoice = useCallback(async (audioBlob: Blob, duration: number, replyToId?: string) => {
    if (!user || !activeChat) return;

    // Create optimistic message
    const tempId = `temp-voice-${Date.now()}-${Math.random()}`;
    const optimisticMessage: Message = {
      id: tempId,
      chat_id: activeChat.id,
      sender_id: user.id,
      content: '',
      message_type: 'voice',
      reply_to_id: replyToId || null,
      file_url: URL.createObjectURL(audioBlob),
      file_name: 'voice-message.webm',
      file_size: audioBlob.size,
      file_type: 'audio/webm',
      voice_duration: duration,
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
      is_edited: false,
      is_deleted: false,
      metadata: { uploading: true },
      sender_profile: {
        first_name: user.user_metadata?.first_name || 'You',
        last_name: user.user_metadata?.last_name || '',
        avatar_url: user.user_metadata?.avatar_url || null,
        type: user.user_metadata?.user_type || 'ww_manager'
      },
      reply_to: replyToId ? messages.find(m => m.id === replyToId) : undefined
    };

    setMessages(prev => [...prev, optimisticMessage]);
    setSendingMessages(prev => new Set([...prev, tempId]));

    try {
      // Upload voice file first
      const uploadResult = await chatApi.uploadVoiceMessage(activeChat.id, audioBlob, duration);

      if (!uploadResult.success || !uploadResult.file_url) {
        throw new Error(uploadResult.error || 'Voice upload failed');
      }

      // Send message with voice URL
      await chatApi.sendMessage(activeChat.id, {
        content: '',
        message_type: 'voice',
        reply_to_id: replyToId,
        file_url: uploadResult.file_url,
        voice_duration: duration,
      });

      // Remove optimistic message - WSE will bring the real one
      setSendingMessages(prev => {
        const newSet = new Set(prev);
        newSet.delete(tempId);
        return newSet;
      });

      logger.debug('Voice message sent', { chatId: activeChat.id, duration, component: 'useRealtimeChat' });

    } catch (error) {
      logger.error('Error sending voice message', error, { component: 'useRealtimeChat', chatId: activeChat.id });

      // Remove failed optimistic message
      setMessages(prev => prev.filter(m => m.id !== tempId));
      setSendingMessages(prev => {
        const newSet = new Set(prev);
        newSet.delete(tempId);
        return newSet;
      });
    }
  }, [user, activeChat, messages]);

  // Отправка интерактивного сообщения
  const sendInteractiveMessage = useCallback(async (interactiveData: any, title?: string) => {
    if (!user) {
      logger.error('Cannot send interactive message: no user', undefined, { component: 'useRealtimeChat' });
      throw new Error('Пользователь не авторизован');
    }

    if (!activeChat) {
      logger.error('Cannot send interactive message: no active chat', undefined, { component: 'useRealtimeChat' });
      throw new Error('Выберите чат для отправки сообщения');
    }

    logger.debug('Sending interactive message', { chatId: activeChat.id, component: 'useRealtimeChat' });
    
    try {
      const message = await chatApi.sendMessage(activeChat.id, { content: JSON.stringify(interactiveData), message_type: "interactive" });
      logger.debug('Interactive message sent successfully', { messageId: message.id, chatId: activeChat.id, component: 'useRealtimeChat' });
      
      // Останавливаем индикатор печати
      if (isTypingRef.current) {
        await chatApi.stopTyping(activeChat.id);
        isTypingRef.current = false;
      }
    } catch (error) {
      logger.error('Error sending interactive message', error, { component: 'useRealtimeChat', chatId: activeChat.id });
      throw error; // Re-throw to allow UI to handle the error
    }
  }, [user, activeChat, createChat]);

  // Отметка сообщения как прочитанного
  const markAsRead = useCallback(async (messageId: string) => {
    if (!user) return;

    try {
      await chatApi.markAsRead(activeChat?.id || "", { message_ids: [messageId] });
    } catch (error) {
      logger.warn('Failed to mark message as read', { error, messageId, component: 'useRealtimeChat' });
      // Silently continue - marking as read is not critical for functionality
    }
  }, [user]);

  // Начало печати
  // Debounced typing для оптимизации производительности
  const startTyping = useCallback(async () => {
    if (!user || !activeChat) return;

    // Отменяем предыдущий таймер
    if (typingTimeoutRef.current) {
      clearTimeout(typingTimeoutRef.current);
    }

    // Отправляем typing только если не было активности 300мс
    if (!isTypingRef.current) {
      isTypingRef.current = true;
      await chatApi.startTyping(activeChat.id);
    }

    // Автоматически останавливаем typing через 3 секунды бездействия
    typingTimeoutRef.current = setTimeout(async () => {
      if (isTypingRef.current && activeChat) {
        isTypingRef.current = false;
        await chatApi.stopTyping(activeChat.id);
      }
    }, 3000);
  }, [user, activeChat]);

  // Остановка печати с debouncing
  const stopTyping = useCallback(async () => {
    if (!user || !activeChat) return;

    if (typingTimeoutRef.current) {
      clearTimeout(typingTimeoutRef.current);
    }

    if (isTypingRef.current) {
      isTypingRef.current = false;
      await chatApi.stopTyping(activeChat.id);
    }
  }, [user, activeChat]);

  // Инициализация scope при монтировании и смене пользователя
  useEffect(() => {
    if (user) {
      // Инициализируем scope и позволяем загрузке чатов
      setIsScopeInitialized(true);
      
      // Сохраняем чаты в localStorage для быстрого доступа при следующей загрузке
      const cacheChats = () => {
        try {
          localStorage.setItem('ww:cached_chats', JSON.stringify(chats));
        } catch (error) {
          logger.debug('Failed to cache chats', { error, component: 'useRealtimeChat' });
        }
      };
      
      if (chats.length > 0) {
        cacheChats();
      }
    } else {
      // Очищаем состояние при выходе пользователя
      // WSE handles unsubscription automatically;
      chatsSubscriptionRef.current = null;
      isSubscribedToChatsRef.current = false;
      setChats([]);
      setActiveChat(null);
      setMessages([]);
      setTypingUsers([]);
      setInitialLoading(false);
      setIsScopeInitialized(false);
    }
  }, [user]);

  // Загрузка чатов при инициализации scope
  useEffect(() => {
    if (user && isScopeInitialized) {
      loadChats();
    }
  }, [user, isScopeInitialized, loadChats]);

  // Кэширование чатов при изменении
  useEffect(() => {
    if (chats.length > 0) {
      try {
        localStorage.setItem('ww:cached_chats', JSON.stringify(chats));
      } catch (error) {
        logger.debug('Failed to cache chats', { error, component: 'useRealtimeChat' });
      }
    }
  }, [chats]);

  // Смена области чатов (компания или супергруппа)
  useEffect(() => {
    if (!user) return;

    // Очищаем activeChat при смене scope если он не принадлежит новому контексту
    if (activeChat) {
      let chatBelongsToScope = false;
      
      if (chatScope.type === 'supergroup' && chatScope.supergroupId) {
        chatBelongsToScope = activeChat.telegram_supergroup_id === chatScope.supergroupId;
      } else {
        chatBelongsToScope = chatScope.companyId 
          ? activeChat.company_id === chatScope.companyId
          : activeChat.company_id === null;
      }

      if (!chatBelongsToScope) {
        logger.info('Active chat does not belong to selected scope, clearing it', { 
          chatId: activeChat.id, 
          chatScope,
          component: 'useRealtimeChat' 
        });
        // WSE handles chat unsubscription;
        setActiveChat(null);
        setMessages([]);
        setTypingUsers([]);
      }
    }

    // Очищаем чаты перед загрузкой новых для правильного срабатывания initialLoading
    logger.info('Chat scope changed, clearing chats and loading new ones', { 
      chatScope,
      component: 'useRealtimeChat' 
    });
    setChats([]);
    
    // Перезагружаем чаты для нового scope
    loadChats();
  }, [chatScope, user]);

  // Подписка на обновления чатов после их загрузки
  useEffect(() => {
    if (user && chats.length > 0) {
      subscribeToChatsUpdates();
    }
  }, [chats.length, user]);

  // ОТКЛЮЧАЕМ автоматический выбор "последнего чата" - он мешает при смене групп
  // useEffect(() => {
  //   if (chats.length > 0 && !activeChat && !initialLoading) {
  //     // Если в URL есть chatId, пытаемся выбрать этот чат
  //     if (chatId) {
  //       const targetChat = chats.find(c => c.id === chatId);
  //       if (targetChat) {
  //         logger.debug('Auto-selecting chat from URL', { chatId, component: 'useRealtimeChat' });
  //         selectChat(chatId, false); // не обновляем URL, так как мы уже по нему перешли
  //         return;
  //       } else {
  //         logger.warn('Chat from URL not found, selecting last chat instead', { chatId, component: 'useRealtimeChat' });
        //         toast({
        //           title: 'Чат не найден',
        //           description: 'Чат из ссылки не найден',
        //           variant: "error"
        //         });
  //       }
  //     }
      
  //     // Если чата из URL нет или он не найден, выбираем последний чат
  //     const sortedChats = [...chats].sort((a, b) => 
  //       new Date(b.updated_at || b.created_at).getTime() - 
  //       new Date(a.updated_at || a.created_at).getTime()
  //     );
  //     const lastChat = sortedChats[0];
  //     logger.debug('Auto-selecting last chat', { chatId: lastChat.id, component: 'useRealtimeChat' });
  //     selectChat(lastChat.id, true); // обновляем URL для consistency
  //   }
  // }, [chats.length, activeChat, initialLoading, chatId, selectChat]);

  // Автовыбор чата по URL только если чат существует (без уведомлений)
  useEffect(() => {
    if (chats.length > 0 && !activeChat && !initialLoading && chatId) {
      const targetChat = chats.find(c => c.id === chatId);
      if (targetChat) {
        logger.debug('Auto-selecting chat from URL', { chatId, component: 'useRealtimeChat' });
        selectChat(chatId, false); // не обновляем URL, так как мы уже по нему перешли
      }
      // Убрали уведомление - просто ждем пока пользователь сам выберет чат
    }
  }, [chats.length, activeChat, initialLoading, chatId, selectChat]);

  // Очищаем состояние при смене пользователя
  useEffect(() => {
    if (activeChat) {
      // WSE handles chat unsubscription;
    }
    setActiveChat(null);
    setMessages([]);
    setTypingUsers([]);
    
    // Очищаем индикатор печати при смене пользователя
    if (isTypingRef.current) {
      isTypingRef.current = false;
    }
    if (typingTimeoutRef.current) {
      clearTimeout(typingTimeoutRef.current);
      typingTimeoutRef.current = undefined;
    }
  }, [user?.id]);

  // Очистка подписок при размонтировании
  useEffect(() => {
    return () => {
      if (activeChat) {
        // WSE handles chat unsubscription;
      }
      
      // Очищаем глобальную подписку на чаты
      // WSE handles unsubscription automatically;
      chatsSubscriptionRef.current = null;
      isSubscribedToChatsRef.current = false;
      
      // Очищаем индикатор печати при размонтировании
      if (isTypingRef.current) {
        isTypingRef.current = false;
      }
      if (typingTimeoutRef.current) {
        clearTimeout(typingTimeoutRef.current);
      }
    };
  }, []);

  // Обновление чата с optimistic update
  const updateChat = useCallback(async (chatId: string, name: string, description: string = '') => {
    if (!user) return;

    // Optimistic update - мгновенно обновляем UI
    const previousChatState = chats.find(chat => chat.id === chatId);
    const previousActiveChatState = activeChat?.id === chatId ? activeChat : null;
    
    // Локально обновляем название чата
    setChats(prev => prev.map(chat => 
      chat.id === chatId 
        ? { ...chat, name, updated_at: new Date().toISOString() }
        : chat
    ));
    
    // Обновляем активный чат если это он
    if (activeChat?.id === chatId) {
      setActiveChat(prev => prev ? { ...prev, name, updated_at: new Date().toISOString() } : prev);
    }
    
    try {
      await chatApi.updateChat(chatId, { name: name });
      logger.info('Chat updated successfully', { chatId, name, component: 'useRealtimeChat' });
    } catch (error) {
      logger.error('Error updating chat, rolling back', error, { component: 'useRealtimeChat', chatId });
      
      // Rollback при ошибке
      if (previousChatState) {
        setChats(prev => prev.map(chat => 
          chat.id === chatId ? previousChatState : chat
        ));
      }
      if (previousActiveChatState) {
        setActiveChat(previousActiveChatState);
      }
      
      throw error;
    }
  }, [user, chats, activeChat]);

  // Computed filtered messages - возвращаем правильный массив в зависимости от фильтра
  const displayedMessages = useMemo(() => {
    return messageFilter === 'all' ? messages : filteredMessages;
  }, [messages, filteredMessages, messageFilter]);

  const deleteChat = useCallback(async (chatId: string) => {
    if (!user) return;

    try {
      await chatApi.archiveChat(chatId);

      // Удаляем из локального состояния
      setChats(prev => prev.filter(chat => chat.id !== chatId));
      
      // Если это был активный чат, очищаем его
      if (activeChat?.id === chatId) {
        setActiveChat(null);
        setMessages([]);
      }
    } catch (error) {
      logger.error('Error deleting chat', error, { component: 'useRealtimeChat', chatId });
      throw error;
    }
  }, [user, activeChat]);

  return {
    // Состояние
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
    isCreatingChat,
    // Removed clientCompany and isLoadingClientCompany - admin-only system
    loadCompanyForChat,
    clearCompanyCache,
    isLoadingChats,
    
    // Функции для чатов
    loadChats,
    createChat,
    selectChat,
    loadMoreMessages,
    addParticipants,
    updateChat,
    deleteChat,
    
    // Функции для сообщений
    sendMessage,
    sendFile,
    sendVoice,
    sendInteractiveMessage,
    markAsRead,
    
    // Message filtering
    setMessageFilter: handleFilterChange,
    
    // Индикатор печати
    startTyping,
    stopTyping,
    
    // Chat scope управление
    setScopeBySupergroup: useCallback((supergroup: any) => {
      const platformContext = usePlatformSafe();
      
      // Проверяем, изменилась ли supergroup - если нет, не очищаем состояние
      const isSameSupergroup = chatScope.type === 'supergroup' && 
                               chatScope.supergroupId === supergroup.id &&
                               chatScope.companyId === supergroup.company_id;
      
      if (isSameSupergroup) {
        logger.debug('setScopeBySupergroup: same supergroup, skipping state reset', {
          supergroupId: supergroup.id,
          companyId: supergroup.company_id,
          component: 'useRealtimeChat'
        });
        return;
      }
      
      // Устанавливаем флаг ручного выбора группы для предотвращения автосинхронизации
      // Это делается через custom event, чтобы SidebarChat мог это отловить
      window.dispatchEvent(new CustomEvent('manualGroupSelection', {
        detail: { supergroupId: supergroup.id, timestamp: Date.now() }
      }));
      
      logger.debug('setScopeBySupergroup: switching supergroup, clearing state', {
        from: chatScope,
        to: { supergroupId: supergroup.id, companyId: supergroup.company_id },
        component: 'useRealtimeChat'
      });
      
      // СРАЗУ очищаем ВСЁ состояние чтобы справа ничего не показывалось
      setChats([]);
      setInitialLoading(true);
      
      if (activeChat) {
        // WSE handles chat unsubscription;
        setActiveChat(null);
        setMessages([]);
        setTypingUsers([]);
      }
      
      // Обновляем chat scope
      setChatScope({
        type: 'supergroup',
        supergroupId: supergroup.id,
        companyId: supergroup.company_id
      });
      
      // Синхронизируем выбранную компанию в PlatformContext если она отличается
      if (supergroup.company_id && platformContext.selectedCompany?.id !== supergroup.company_id && platformContext.setSelectedCompany) {
        platformContext.setSelectedCompany({ id: supergroup.company_id } as any);
      }
    }, [chatScope]),
    
    setScopeByCompany: useCallback((companyId: number | null) => {
      setChatScope({
        type: 'company',
        companyId: companyId
      });
    }, []),
    
    // Smart scrolling - incremental load history until target message is found
    loadHistoryUntilMessage: useCallback(async (messageId: string): Promise<boolean> => {
      if (!activeChat) {
        logger.warn('No active chat for loadHistoryUntilMessage', { messageId, component: 'useRealtimeChat' });
        return false;
      }

      logger.info('Starting incremental history load until message', { messageId, chatId: activeChat.id, component: 'useRealtimeChat' });

      try {
        // Get target message metadata
        const messageMeta = null;
        if (!messageMeta) {
          logger.warn('Target message not found', { messageId, component: 'useRealtimeChat' });
          return false;
        }

        // Count messages newer than target to calculate required load
        const newerCount = 0;
        
        // Calculate how many total messages we need loaded (including buffer for context)
        const buffer = 10; // Small context buffer
        const targetTotal = newerCount + 1 + buffer;
        
        logger.debug('History loading calculation', { 
          messageId, 
          targetTimestamp: messageMeta.created_at, 
          newerCount, 
          targetTotal,
          currentOffset: messageOffset,
          component: 'useRealtimeChat' 
        });

        // If we already have enough messages loaded, target should be visible
        if (messageOffset >= targetTotal) {
          logger.info('Target message should already be loaded', { 
            messageId,
            messageOffset,
            targetTotal,
            component: 'useRealtimeChat'
          });
          return true;
        }

        // Calculate how many additional messages we need to load
        const needed = targetTotal - messageOffset;
        
        logger.info('Loading additional history incrementally', {
          messageId,
          needed,
          currentOffset: messageOffset,
          component: 'useRealtimeChat'
        });

        // Load the needed older messages incrementally
        const olderMessages = await chatApi.getMessages(activeChat.id, { limit: needed, offset: messageOffset });
        
        if (olderMessages.length === 0) {
          logger.info('No more history available', { messageId, component: 'useRealtimeChat' });
          return false;
        }

        // Hydrate image dimensions for new messages (without resetting)
        let messagesWithDimensions = [...olderMessages];
        const imageMessages = olderMessages
          .filter(msg => msg.message_type === 'image' && msg.file_url && !msg.metadata?.imageDimensions);
        
        if (imageMessages.length > 0) {
          try {
            const { imageDimensionsCache } = await import('@/utils/imageDimensionsCache');
            const hydratedImageMessages = await imageDimensionsCache.hydrateMessagesWithLimiter(imageMessages);
            
            messagesWithDimensions = olderMessages.map(msg => {
              const hydratedMsg = hydratedImageMessages.find(h => h.id === msg.id);
              return hydratedMsg || msg;
            });
          } catch (error) {
            logger.warn('Failed to hydrate image dimensions for incremental messages', error);
          }
        }

        // Reverse to get old->new order and prepend to current messages
        const newOlderAsc = messagesWithDimensions.reverse();
        
        setMessages(prev => [...newOlderAsc, ...prev]);
        setMessageOffset(prev => prev + olderMessages.length);
        setHasMoreMessages(olderMessages.length === needed);
        
        // Check if target message is now in the loaded set
        const targetFound = [...newOlderAsc, ...messages].some(msg => msg.id === messageId);
        
        logger.info('Incremental history load completed', { 
          messageId, 
          loaded: olderMessages.length,
          targetFound,
          newOffset: messageOffset + olderMessages.length,
          component: 'useRealtimeChat' 
        });

        return targetFound;
      } catch (error) {
        logger.error('Error in loadHistoryUntilMessage', error, { messageId, component: 'useRealtimeChat' });
        return false;
      }
    }, [activeChat, messageOffset, messages]),
    
    chatScope
  };
}
