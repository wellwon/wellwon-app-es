// =============================================================================
// File: src/hooks/chat/index.ts
// Description: Chat hooks barrel export
// Architecture: React Query (server state) + Zustand (UI state) + WSE (real-time)
// =============================================================================

// React Query hooks for server state
export { useChatMessages, chatKeys, addOptimisticMessage, removeMessageFromCache } from './useChatMessages';
export { useChatList, useChatDetail, useChatParticipants, useUnreadCount } from './useChatList';
export {
  useSendMessage,
  useEditMessage,
  useDeleteMessage,
  useMarkAsRead,
  useUploadFile,
  useUploadVoice,
} from './useChatMutations';

// Zustand store for UI-only state
export {
  useChatUIStore,
  useTypingIndicator,
  selectActiveChatId,
  selectReplyingTo,
  selectMessageFilter,
  selectChatScope,
  selectIsCreatingChat,
  selectIsSendingMessage,
  selectEditingMessageId,
} from './useChatUIStore';

// Typing indicator hooks
export { useTypingEvents, useSendTypingIndicator } from './useTypingEvents';

// Message templates
export { useMessageTemplates, useTemplateList, templateKeys } from './useMessageTemplates';

// Re-export types
export type { Message, ChatListItem, ChatDetail, ChatParticipant } from '@/api/chat';
