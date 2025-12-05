// =============================================================================
// File: src/contexts/RealtimeChatContext.tsx
// Description: Chat context using React Query + WSE + Zustand (TkDodo pattern)
// =============================================================================

import React, { createContext, useContext, useCallback, useEffect, useMemo } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { useAuth } from '@/contexts/AuthContext';
import { usePlatform } from '@/contexts/PlatformContext';
import { logger } from '@/utils/logger';

// API types
import type { ChatListItem, ChatDetail } from '@/api/chat';

// React Query hooks
import {
  useChatMessages,
  useChatList,
  useChatDetail,
  useChatParticipants,
  useSendMessage,
  useDeleteMessage,
  useMarkAsRead,
  useUploadFile,
  useUploadVoice,
  useChatUIStore,
  useTypingIndicator,
  chatKeys,
} from '@/hooks/chat';

import { useTypingEvents, useSendTypingIndicator } from '@/hooks/chat/useTypingEvents';
import { companyKeys } from '@/hooks/company';

// API
import * as chatApi from '@/api/chat';
import * as companyApi from '@/api/company';

// Types
import type { RealtimeChatContextType, Chat, Message, Company, MessageFilter } from '@/types/realtime-chat';

// -----------------------------------------------------------------------------
// Context
// -----------------------------------------------------------------------------

const RealtimeChatContext = createContext<RealtimeChatContextType | null>(null);

// -----------------------------------------------------------------------------
// Provider
// -----------------------------------------------------------------------------

export const RealtimeChatProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const { user } = useAuth();
  const queryClient = useQueryClient();

  // Platform context for navigation
  const platform = usePlatformSafe();

  // UI State (Zustand)
  const {
    activeChatId,
    setActiveChatId,
    replyingTo,
    setReplyingTo,
    messageFilter,
    setMessageFilter,
    chatScope,
    setScopeBySupergroup,
    setScopeByCompany,
    isCreatingChat,
    setIsCreatingChat,
  } = useChatUIStore();

  // React Query: Chat List
  const { chats, isLoading: isLoadingChats, refetch: refetchChats } = useChatList({
    enabled: !!user,
  });

  // React Query: Active Chat Detail
  const { data: activeChat } = useChatDetail(activeChatId);

  // React Query: Messages (infinite scroll with seamless prefetch)
  const {
    messages,
    isLoading: loadingMessages,
    hasNextPage: hasMoreMessages,
    isFetchingNextPage: loadingMoreMessages,
    isFetching: isFetchingMessages,
    fetchNextPage,
    prefetchNextPage,
    checkPrefetch,
  } = useChatMessages(activeChatId, { enabled: !!activeChatId });

  // React Query: Participants
  const { participants } = useChatParticipants(activeChatId);

  // Typing indicators
  const typingUsers = useTypingIndicator(activeChatId);
  useTypingEvents(activeChatId);
  const { startTyping, stopTyping } = useSendTypingIndicator(activeChatId);

  // Mutations
  const sendMessageMutation = useSendMessage();
  const deleteMessageMutation = useDeleteMessage();
  const markAsReadMutation = useMarkAsRead();
  const uploadFileMutation = useUploadFile();
  const uploadVoiceMutation = useUploadVoice();

  // -----------------------------------------------------------------------------
  // Actions
  // -----------------------------------------------------------------------------

  const loadChats = useCallback(async () => {
    await refetchChats();
  }, [refetchChats]);

  const selectChat = useCallback(async (chatId: string, updateUrl = true) => {
    console.log('[SELECT-CHAT] selectChat called with:', chatId, 'current activeChatId:', activeChatId);

    if (activeChatId === chatId) {
      console.log('[SELECT-CHAT] Same chat, scrolling to bottom');
      window.dispatchEvent(new CustomEvent('chat:scrollToBottom', { detail: { force: true } }));
      return;
    }

    console.log('[SELECT-CHAT] Setting activeChatId to:', chatId);
    setActiveChatId(chatId);
    setReplyingTo(null);

    if (updateUrl && platform.setActiveSection) {
      platform.setActiveSection('chat', chatId);
    }

    logger.debug('Chat selected', { chatId });
  }, [activeChatId, setActiveChatId, setReplyingTo, platform]);

  // Seamless load more - checks isFetching to prevent conflicts
  const loadMoreMessages = useCallback(async () => {
    if (hasMoreMessages && !loadingMoreMessages && !isFetchingMessages) {
      await fetchNextPage();
    }
  }, [hasMoreMessages, loadingMoreMessages, isFetchingMessages, fetchNextPage]);

  const createChat = useCallback(async (
    name: string,
    chatType: Chat['chat_type'] = 'direct',
    participantIds: string[] = []
  ): Promise<Chat> => {
    if (!user) throw new Error('User not authenticated');
    if (isCreatingChat) throw new Error('Chat creation in progress');

    setIsCreatingChat(true);

    try {
      // CRITICAL: Validate company_id when creating chat in supergroup context
      // If a supergroup is selected but no company_id, warn and log
      const supergroupId = chatScope.type === 'supergroup' ? chatScope.supergroupId : undefined;
      const companyId = chatScope.companyId || undefined;

      if (supergroupId && !companyId) {
        logger.warn('Creating chat with supergroup but no company_id! This indicates scope sync issue', {
          supergroupId,
          chatScopeType: chatScope.type,
          chatScopeCompanyId: chatScope.companyId,
          component: 'RealtimeChatContext.createChat'
        });
      }

      const newChat = await chatApi.createChat({
        name,
        chat_type: chatType,
        company_id: companyId,
        participant_ids: participantIds,
        telegram_supergroup_id: supergroupId,
      });

      // OPTIMISTIC UI: Dispatch chatCreated event immediately for instant UI update
      // This triggers useChatList WSE handler to add chat to list instantly
      window.dispatchEvent(new CustomEvent('chatCreated', {
        detail: {
          id: newChat.id,
          chat_id: newChat.id,
          name: name,
          chat_name: name,
          chat_type: chatType,
          company_id: companyId || null,
          telegram_supergroup_id: supergroupId || null,
          created_at: new Date().toISOString(),
        }
      }));

      logger.info('Chat created with optimistic dispatch', { chatId: newChat.id, name });
      return newChat;
    } finally {
      setIsCreatingChat(false);
    }
  }, [user, isCreatingChat, setIsCreatingChat, chatScope]);

  const sendMessage = useCallback(async (content: string, replyToId?: string) => {
    if (!activeChatId || !user) {
      logger.warn('Cannot send message: no active chat or user');
      return;
    }

    await sendMessageMutation.mutateAsync({
      chatId: activeChatId,
      content,
      replyToId: replyToId || replyingTo?.id,
    });

    setReplyingTo(null);
    await stopTyping();
  }, [activeChatId, user, sendMessageMutation, replyingTo, setReplyingTo, stopTyping]);

  const sendFile = useCallback(async (file: File, replyToId?: string) => {
    if (!activeChatId || !user) return;

    const isImage = file.type.startsWith('image/');
    const messageType = isImage ? 'image' : 'file';

    // Upload first
    const uploadResult = await uploadFileMutation.mutateAsync({
      chatId: activeChatId,
      file,
    });

    // Then send message with file URL
    await sendMessageMutation.mutateAsync({
      chatId: activeChatId,
      content: file.name,
      messageType,
      replyToId: replyToId || replyingTo?.id,
      fileUrl: uploadResult.file_url,
      fileName: uploadResult.file_name,
      fileSize: uploadResult.file_size,
      fileType: uploadResult.file_type,
    });

    setReplyingTo(null);
  }, [activeChatId, user, uploadFileMutation, sendMessageMutation, replyingTo, setReplyingTo]);

  const sendVoice = useCallback(async (audioBlob: Blob, duration: number, replyToId?: string) => {
    if (!activeChatId || !user) return;

    // Upload first
    const uploadResult = await uploadVoiceMutation.mutateAsync({
      chatId: activeChatId,
      audioBlob,
      duration,
    });

    // Then send message
    await sendMessageMutation.mutateAsync({
      chatId: activeChatId,
      content: '',
      messageType: 'voice',
      replyToId: replyToId || replyingTo?.id,
      fileUrl: uploadResult.file_url,
      voiceDuration: duration,
    });

    setReplyingTo(null);
  }, [activeChatId, user, uploadVoiceMutation, sendMessageMutation, replyingTo, setReplyingTo]);

  const sendInteractiveMessage = useCallback(async (interactiveData: any, _title?: string) => {
    if (!activeChatId || !user) throw new Error('No active chat');

    await sendMessageMutation.mutateAsync({
      chatId: activeChatId,
      content: JSON.stringify(interactiveData),
      messageType: 'interactive',
    });
  }, [activeChatId, user, sendMessageMutation]);

  const deleteMessage = useCallback(async (messageId: string) => {
    if (!activeChatId) return;

    await deleteMessageMutation.mutateAsync({
      chatId: activeChatId,
      messageId,
    });
  }, [activeChatId, deleteMessageMutation]);

  const markAsRead = useCallback(async (messageId: string) => {
    if (!activeChatId) return;

    await markAsReadMutation.mutateAsync({
      chatId: activeChatId,
      messageId: messageId,
    });
  }, [activeChatId, markAsReadMutation]);

  const addParticipants = useCallback(async (chatId: string, userIds: string[]) => {
    await Promise.all(userIds.map(uid => chatApi.addParticipant(chatId, { user_id: uid })));
    queryClient.invalidateQueries({ queryKey: chatKeys.participants(chatId) });
  }, [queryClient]);

  const updateChat = useCallback(async (chatId: string, name: string, _description?: string) => {
    // Optimistic update FIRST - immediately update UI before API call completes
    // This ensures instant feedback regardless of backend projection timing
    queryClient.setQueryData(
      chatKeys.list({ includeArchived: false, limit: 100 }),
      (oldData: ChatListItem[] | undefined) => {
        if (!oldData) return oldData;
        return oldData.map((chat) =>
          chat.id === chatId ? { ...chat, name } : chat
        );
      }
    );

    // Also update detail cache if exists
    queryClient.setQueryData(
      chatKeys.detail(chatId),
      (oldData: ChatDetail | undefined) => {
        if (!oldData) return oldData;
        return { ...oldData, name };
      }
    );

    // Then call API (fire and forget - WSE will confirm)
    await chatApi.updateChat(chatId, { name });
    // No refetch needed - optimistic update already done, WSE will sync if needed
  }, [queryClient]);

  const deleteChat = useCallback(async (chatId: string) => {
    // Optimistic update FIRST - immediately remove from UI
    queryClient.setQueryData(
      chatKeys.list({ includeArchived: false, limit: 100 }),
      (oldData: ChatListItem[] | undefined) => {
        if (!oldData) return oldData;
        return oldData.filter((chat) => chat.id !== chatId);
      }
    );

    if (activeChatId === chatId) {
      setActiveChatId(null);
    }

    // Then call API - WSE will confirm via chatArchived event
    await chatApi.archiveChat(chatId);
  }, [activeChatId, setActiveChatId, queryClient]);

  const hardDeleteChat = useCallback(async (chatId: string, reason?: string) => {
    // Optimistic update FIRST - immediately remove from UI
    queryClient.setQueryData(
      chatKeys.list({ includeArchived: false, limit: 100 }),
      (oldData: ChatListItem[] | undefined) => {
        if (!oldData) return oldData;
        return oldData.filter((chat) => chat.id !== chatId);
      }
    );

    // Also remove from archived list
    queryClient.setQueryData(
      chatKeys.list({ includeArchived: true, limit: 100 }),
      (oldData: ChatListItem[] | undefined) => {
        if (!oldData) return oldData;
        return oldData.filter((chat) => chat.id !== chatId);
      }
    );

    // Remove detail cache
    queryClient.removeQueries({ queryKey: chatKeys.detail(chatId) });

    if (activeChatId === chatId) {
      setActiveChatId(null);
    }

    // Then call API - WSE will confirm via chatDeleted event
    await chatApi.hardDeleteChat(chatId, reason);
  }, [activeChatId, setActiveChatId, queryClient]);

  const handleSetMessageFilter = useCallback(async (filter: MessageFilter) => {
    setMessageFilter(filter);
    // React Query will refetch with new filter if needed
  }, [setMessageFilter]);

  const loadCompanyForChat = useCallback(async (chatId: string, forceRefresh = false): Promise<Company | null> => {
    try {
      // First get the chat to find company_id
      const chatDetail = await queryClient.fetchQuery({
        queryKey: chatKeys.detail(chatId),
        queryFn: () => chatApi.getChatById(chatId),
        staleTime: forceRefresh ? 0 : 5 * 60 * 1000,
      });

      if (!chatDetail?.company_id) {
        return null;
      }

      // Then fetch company using React Query cache
      const company = await queryClient.fetchQuery({
        queryKey: companyKeys.detail(chatDetail.company_id),
        queryFn: () => companyApi.getCompanyById(chatDetail.company_id),
        staleTime: forceRefresh ? 0 : 5 * 60 * 1000,
      });

      return company;
    } catch (error) {
      logger.error('Error loading company for chat', { error, chatId });
      return null;
    }
  }, [queryClient]);

  const clearCompanyCache = useCallback((chatId?: string) => {
    if (chatId) {
      // Get chat detail to find company_id, then invalidate
      const chatDetail = queryClient.getQueryData<Chat>(chatKeys.detail(chatId));
      if (chatDetail?.company_id) {
        queryClient.removeQueries({ queryKey: companyKeys.detail(chatDetail.company_id) });
      }
    } else {
      // Clear all company cache
      queryClient.removeQueries({ queryKey: companyKeys.all });
    }
  }, [queryClient]);

  const loadHistoryUntilMessage = useCallback(async (_messageId: string): Promise<boolean> => {
    // Load more pages until message is found
    // For now, just load next page
    if (hasMoreMessages) {
      await fetchNextPage();
    }
    return true;
  }, [hasMoreMessages, fetchNextPage]);

  // Auto-select chat from URL
  useEffect(() => {
    if (chats.length > 0 && !activeChatId && platform.chatId) {
      const targetChat = chats.find(c => c.id === platform.chatId);
      if (targetChat) {
        selectChat(platform.chatId, false);
      }
    }
  }, [chats, activeChatId, platform.chatId, selectChat]);

  // -----------------------------------------------------------------------------
  // Context Value
  // -----------------------------------------------------------------------------

  const contextValue: RealtimeChatContextType = useMemo(() => ({
    // State
    chats,
    activeChat: activeChat || null,
    messages,
    filteredMessages: messages, // Filtering done via React Query
    displayedMessages: messages,
    messageFilter,
    typingUsers,
    initialLoading: isLoadingChats && chats.length === 0,
    loadingMessages,
    loadingMoreMessages,
    sendingMessages: new Set(sendMessageMutation.isPending ? ['pending'] : []),
    hasMoreMessages: !!hasMoreMessages,
    filteredHasMore: !!hasMoreMessages,
    isCreatingChat,
    isLoadingChats,
    loadCompanyForChat,
    clearCompanyCache,

    // Chat actions
    loadChats,
    createChat,
    selectChat,
    loadMoreMessages,
    prefetchNextPage,
    checkPrefetch,
    addParticipants,
    updateChat,
    deleteChat,
    hardDeleteChat,

    // Message actions
    sendMessage,
    sendFile,
    sendVoice,
    sendInteractiveMessage,
    deleteMessage,
    markAsRead,

    // Message filtering
    setMessageFilter: handleSetMessageFilter,

    // Typing
    startTyping,
    stopTyping,

    // Smart scrolling
    loadHistoryUntilMessage,

    // Chat scope
    setScopeBySupergroup: (supergroup: any) => {
      setScopeBySupergroup(supergroup.id, supergroup.company_id);
    },
    setScopeByCompany: (companyId: string | null) => {
      setScopeByCompany(companyId);
    },
    chatScope,
  }), [
    chats,
    activeChat,
    messages,
    messageFilter,
    typingUsers,
    isLoadingChats,
    loadingMessages,
    loadingMoreMessages,
    sendMessageMutation.isPending,
    hasMoreMessages,
    isCreatingChat,
    loadCompanyForChat,
    clearCompanyCache,
    loadChats,
    createChat,
    selectChat,
    loadMoreMessages,
    prefetchNextPage,
    checkPrefetch,
    addParticipants,
    updateChat,
    deleteChat,
    hardDeleteChat,
    sendMessage,
    sendFile,
    sendVoice,
    sendInteractiveMessage,
    deleteMessage,
    markAsRead,
    handleSetMessageFilter,
    startTyping,
    stopTyping,
    loadHistoryUntilMessage,
    setScopeBySupergroup,
    setScopeByCompany,
    chatScope,
  ]);

  return (
    <RealtimeChatContext.Provider value={contextValue}>
      {children}
    </RealtimeChatContext.Provider>
  );
};

// -----------------------------------------------------------------------------
// Hook
// -----------------------------------------------------------------------------

export const useRealtimeChatContext = () => {
  const context = useContext(RealtimeChatContext);
  if (!context) {
    throw new Error('useRealtimeChatContext must be used within a RealtimeChatProvider');
  }
  return context;
};

// Alias for backward compatibility
export const useRealtimeChat = useRealtimeChatContext;

// -----------------------------------------------------------------------------
// Safe Platform Hook
// -----------------------------------------------------------------------------

function usePlatformSafe() {
  try {
    const platform = usePlatform();
    return {
      selectedCompany: platform.selectedCompany,
      chatId: platform.chatId,
      setActiveSection: platform.setActiveSection,
      setSelectedCompany: platform.setSelectedCompany,
    };
  } catch {
    return {
      selectedCompany: null,
      chatId: undefined,
      setActiveSection: () => {},
      setSelectedCompany: () => {},
    };
  }
}
