// =============================================================================
// File: src/hooks/chat/useTypingEvents.ts
// Description: Hook for typing indicator WSE events
// =============================================================================

import { useEffect, useCallback, useRef } from 'react';
import { useChatUIStore } from './useChatUIStore';
import * as chatApi from '@/api/chat';
import { useAuth } from '@/contexts/AuthContext';
import { logger } from '@/utils/logger';

// -----------------------------------------------------------------------------
// useTypingEvents - Listen to WSE typing events
// -----------------------------------------------------------------------------

export function useTypingEvents(chatId: string | null) {
  const { user } = useAuth();
  const addTypingUser = useChatUIStore((state) => state.addTypingUser);
  const removeTypingUser = useChatUIStore((state) => state.removeTypingUser);

  useEffect(() => {
    if (!chatId) return;

    const handleUserTyping = (event: CustomEvent) => {
      const data = event.detail;
      if (data.chat_id !== chatId) return;
      if (data.user_id === user?.id) return; // Ignore own typing

      addTypingUser(chatId, {
        user_id: data.user_id,
        user_name: data.user_name || 'Someone',
        started_at: new Date().toISOString(),
      });
    };

    const handleUserStoppedTyping = (event: CustomEvent) => {
      const data = event.detail;
      if (data.chat_id !== chatId) return;

      removeTypingUser(chatId, data.user_id);
    };

    window.addEventListener('userTyping', handleUserTyping as EventListener);
    window.addEventListener('userStoppedTyping', handleUserStoppedTyping as EventListener);

    return () => {
      window.removeEventListener('userTyping', handleUserTyping as EventListener);
      window.removeEventListener('userStoppedTyping', handleUserStoppedTyping as EventListener);
    };
  }, [chatId, user?.id, addTypingUser, removeTypingUser]);
}

// -----------------------------------------------------------------------------
// useSendTypingIndicator - Send typing indicator with debounce
// -----------------------------------------------------------------------------

export function useSendTypingIndicator(chatId: string | null) {
  const { user } = useAuth();
  const isTypingRef = useRef(false);
  const typingTimeoutRef = useRef<NodeJS.Timeout | null>(null);

  const startTyping = useCallback(async () => {
    if (!chatId || !user) return;

    // Clear previous timeout
    if (typingTimeoutRef.current) {
      clearTimeout(typingTimeoutRef.current);
    }

    // Send typing indicator only if not already typing
    if (!isTypingRef.current) {
      isTypingRef.current = true;
      try {
        await chatApi.startTyping(chatId);
      } catch (error) {
        logger.debug('Failed to send typing indicator', { error });
      }
    }

    // Auto-stop after 3 seconds of inactivity
    typingTimeoutRef.current = setTimeout(async () => {
      if (isTypingRef.current && chatId) {
        isTypingRef.current = false;
        try {
          await chatApi.stopTyping(chatId);
        } catch (error) {
          logger.debug('Failed to stop typing indicator', { error });
        }
      }
    }, 3000);
  }, [chatId, user]);

  const stopTyping = useCallback(async () => {
    if (!chatId || !user) return;

    if (typingTimeoutRef.current) {
      clearTimeout(typingTimeoutRef.current);
      typingTimeoutRef.current = null;
    }

    if (isTypingRef.current) {
      isTypingRef.current = false;
      try {
        await chatApi.stopTyping(chatId);
      } catch (error) {
        logger.debug('Failed to stop typing indicator', { error });
      }
    }
  }, [chatId, user]);

  // Cleanup on unmount or chat change
  useEffect(() => {
    return () => {
      if (typingTimeoutRef.current) {
        clearTimeout(typingTimeoutRef.current);
      }
      // Don't call stopTyping here to avoid async cleanup issues
    };
  }, [chatId]);

  return { startTyping, stopTyping };
}
