// =============================================================================
// File: src/hooks/chat/useChatUIStore.ts
// Description: Zustand store for chat UI-only state (not server state)
// Pattern: Zustand for local UI, React Query for server state, TkDodo pattern
// =============================================================================

import { create } from 'zustand';
import { subscribeWithSelector, persist } from 'zustand/middleware';
import type { Message } from '@/api/chat';

// -----------------------------------------------------------------------------
// Types
// -----------------------------------------------------------------------------

interface TypingUser {
  user_id: string;
  user_name: string;
  started_at: string;
}

interface ChatScope {
  type: 'company' | 'supergroup';
  companyId: string | null;
  supergroupId?: number;
}

// Display options (merged from ChatDisplayOptionsContext)
interface ChatDisplayOptions {
  showTelegramNames: boolean;
  showTelegramIcon: boolean;
  preferUsernameOverName: boolean;
}

interface ChatUIState {
  // Active chat selection
  activeChatId: string | null;
  setActiveChatId: (chatId: string | null) => void;

  // Reply state
  replyingTo: Message | null;
  setReplyingTo: (message: Message | null) => void;
  clearReply: () => void;

  // Typing indicators
  typingUsers: Map<string, TypingUser[]>; // chatId -> typing users
  addTypingUser: (chatId: string, user: TypingUser) => void;
  removeTypingUser: (chatId: string, userId: string) => void;
  clearTypingUsers: (chatId: string) => void;
  getTypingUsers: (chatId: string) => TypingUser[];

  // Message filter
  messageFilter: 'all' | 'images' | 'voice' | 'pdf' | 'doc' | 'xls' | 'other';
  setMessageFilter: (filter: ChatUIState['messageFilter']) => void;

  // Chat scope (company/supergroup selection)
  chatScope: ChatScope;
  setChatScope: (scope: ChatScope) => void;
  setScopeBySupergroup: (supergroupId: number, companyId: string | null) => void;
  setScopeByCompany: (companyId: string | null) => void;

  // Scroll position (for restoring after filter change)
  scrollPositions: Map<string, number>;
  saveScrollPosition: (chatId: string, position: number) => void;
  getScrollPosition: (chatId: string) => number;

  // UI flags
  isCreatingChat: boolean;
  setIsCreatingChat: (creating: boolean) => void;

  isSendingMessage: boolean;
  setIsSendingMessage: (sending: boolean) => void;

  // Editing message
  editingMessageId: string | null;
  setEditingMessageId: (messageId: string | null) => void;

  // PERSISTED: Sidebar state (from SidebarChat localStorage)
  sidebarMode: 'supergroups' | 'personal';
  groupsPanelCollapsed: boolean;
  selectedSupergroupId: number | null;
  setSidebarMode: (mode: 'supergroups' | 'personal') => void;
  setGroupsPanelCollapsed: (collapsed: boolean) => void;
  setSelectedSupergroupId: (id: number | null) => void;

  // PERSISTED: Display options (from ChatDisplayOptionsContext)
  displayOptions: ChatDisplayOptions;
  updateDisplayOption: <K extends keyof ChatDisplayOptions>(key: K, value: ChatDisplayOptions[K]) => void;
  resetDisplayOptions: () => void;

  // Reset all state
  reset: () => void;
}

// -----------------------------------------------------------------------------
// Initial State
// -----------------------------------------------------------------------------

const defaultDisplayOptions: ChatDisplayOptions = {
  showTelegramNames: true,
  showTelegramIcon: true,
  preferUsernameOverName: false,
};

const initialState = {
  // Ephemeral state (not persisted)
  activeChatId: null,
  replyingTo: null,
  typingUsers: new Map<string, TypingUser[]>(),
  messageFilter: 'all' as const,
  chatScope: {
    type: 'company' as const,
    companyId: null,
  },
  scrollPositions: new Map<string, number>(),
  isCreatingChat: false,
  isSendingMessage: false,
  editingMessageId: null,

  // Persisted state
  sidebarMode: 'supergroups' as const,
  groupsPanelCollapsed: false,
  selectedSupergroupId: null as number | null,
  displayOptions: defaultDisplayOptions,
};

// -----------------------------------------------------------------------------
// Store
// -----------------------------------------------------------------------------

export const useChatUIStore = create<ChatUIState>()(
  subscribeWithSelector(
    persist(
      (set, get) => ({
        ...initialState,

        // Active chat
        setActiveChatId: (chatId) => {
          set({ activeChatId: chatId, replyingTo: null, editingMessageId: null });
        },

        // Reply
        setReplyingTo: (message) => set({ replyingTo: message }),
        clearReply: () => set({ replyingTo: null }),

        // Typing indicators
        addTypingUser: (chatId, user) => {
          const typingUsers = new Map(get().typingUsers);
          const chatTyping = typingUsers.get(chatId) || [];

          // Remove existing entry for this user
          const filtered = chatTyping.filter((t) => t.user_id !== user.user_id);
          filtered.push(user);

          typingUsers.set(chatId, filtered);
          set({ typingUsers });

          // Auto-remove after 5 seconds
          setTimeout(() => {
            get().removeTypingUser(chatId, user.user_id);
          }, 5000);
        },

        removeTypingUser: (chatId, userId) => {
          const typingUsers = new Map(get().typingUsers);
          const chatTyping = typingUsers.get(chatId) || [];
          const filtered = chatTyping.filter((t) => t.user_id !== userId);

          if (filtered.length === 0) {
            typingUsers.delete(chatId);
          } else {
            typingUsers.set(chatId, filtered);
          }

          set({ typingUsers });
        },

        clearTypingUsers: (chatId) => {
          const typingUsers = new Map(get().typingUsers);
          typingUsers.delete(chatId);
          set({ typingUsers });
        },

        getTypingUsers: (chatId) => {
          return get().typingUsers.get(chatId) || [];
        },

        // Message filter
        setMessageFilter: (filter) => set({ messageFilter: filter }),

        // Chat scope
        setChatScope: (scope) => set({ chatScope: scope }),

        setScopeBySupergroup: (supergroupId, companyId) => {
          const currentScope = get().chatScope;
          // Don't reset if same supergroup is already selected
          if (currentScope.type === 'supergroup' && currentScope.supergroupId === supergroupId) {
            return;
          }
          set({
            chatScope: {
              type: 'supergroup',
              supergroupId,
              companyId,
            },
            // Don't clear activeChatId - let SidebarChat auto-select first chat
            replyingTo: null,
          });
        },

        setScopeByCompany: (companyId) => {
          const currentScope = get().chatScope;
          // Don't reset if same company is already selected
          if (currentScope.type === 'company' && currentScope.companyId === companyId) {
            return;
          }
          set({
            chatScope: {
              type: 'company',
              companyId,
            },
            // Don't clear activeChatId - let SidebarChat auto-select first chat
            replyingTo: null,
          });
        },

        // Scroll positions
        saveScrollPosition: (chatId, position) => {
          const scrollPositions = new Map(get().scrollPositions);
          scrollPositions.set(chatId, position);
          set({ scrollPositions });
        },

        getScrollPosition: (chatId) => {
          return get().scrollPositions.get(chatId) || 0;
        },

        // UI flags
        setIsCreatingChat: (creating) => set({ isCreatingChat: creating }),
        setIsSendingMessage: (sending) => set({ isSendingMessage: sending }),
        setEditingMessageId: (messageId) => set({ editingMessageId: messageId }),

        // PERSISTED: Sidebar state actions
        setSidebarMode: (mode) => set({ sidebarMode: mode }),
        setGroupsPanelCollapsed: (collapsed) => set({ groupsPanelCollapsed: collapsed }),
        setSelectedSupergroupId: (id) => set({ selectedSupergroupId: id }),

        // PERSISTED: Display options actions
        updateDisplayOption: (key, value) => set((state) => ({
          displayOptions: { ...state.displayOptions, [key]: value },
        })),
        resetDisplayOptions: () => set({ displayOptions: defaultDisplayOptions }),

        // Reset (preserves persisted state by default)
        reset: () => set({
          ...initialState,
          // Preserve persisted state on reset
          sidebarMode: get().sidebarMode,
          groupsPanelCollapsed: get().groupsPanelCollapsed,
          selectedSupergroupId: get().selectedSupergroupId,
          displayOptions: get().displayOptions,
        }),
      }),
      {
        name: 'wellwon-chat-ui',
        // Only persist specific fields (TkDodo pattern - partialize)
        partialize: (state) => ({
          sidebarMode: state.sidebarMode,
          groupsPanelCollapsed: state.groupsPanelCollapsed,
          selectedSupergroupId: state.selectedSupergroupId,
          displayOptions: state.displayOptions,
        }),
      }
    )
  )
);

// -----------------------------------------------------------------------------
// Selectors (for optimized re-renders)
// -----------------------------------------------------------------------------

export const selectActiveChatId = (state: ChatUIState) => state.activeChatId;
export const selectReplyingTo = (state: ChatUIState) => state.replyingTo;
export const selectMessageFilter = (state: ChatUIState) => state.messageFilter;
export const selectChatScope = (state: ChatUIState) => state.chatScope;
export const selectIsCreatingChat = (state: ChatUIState) => state.isCreatingChat;
export const selectIsSendingMessage = (state: ChatUIState) => state.isSendingMessage;
export const selectEditingMessageId = (state: ChatUIState) => state.editingMessageId;

// Persisted state selectors
export const selectSidebarMode = (state: ChatUIState) => state.sidebarMode;
export const selectGroupsPanelCollapsed = (state: ChatUIState) => state.groupsPanelCollapsed;
export const selectSelectedSupergroupId = (state: ChatUIState) => state.selectedSupergroupId;
export const selectDisplayOptions = (state: ChatUIState) => state.displayOptions;

// -----------------------------------------------------------------------------
// Atomic Selector Hooks (TkDodo pattern - return single values)
// -----------------------------------------------------------------------------

export const useSidebarMode = () => useChatUIStore(selectSidebarMode);
export const useGroupsPanelCollapsed = () => useChatUIStore(selectGroupsPanelCollapsed);
export const useSelectedSupergroupId = () => useChatUIStore(selectSelectedSupergroupId);
export const useDisplayOptions = () => useChatUIStore(selectDisplayOptions);

// -----------------------------------------------------------------------------
// Hook for typing indicators (with auto-cleanup)
// -----------------------------------------------------------------------------

export function useTypingIndicator(chatId: string | null) {
  const typingUsers = useChatUIStore((state) =>
    chatId ? state.getTypingUsers(chatId) : []
  );

  return typingUsers;
}

// -----------------------------------------------------------------------------
// Compatibility hook for ChatDisplayOptionsContext migration
// -----------------------------------------------------------------------------

export function useChatDisplayOptions() {
  const displayOptions = useChatUIStore((state) => state.displayOptions);
  const updateDisplayOption = useChatUIStore((state) => state.updateDisplayOption);
  const resetDisplayOptions = useChatUIStore((state) => state.resetDisplayOptions);

  return {
    options: displayOptions,
    updateOption: updateDisplayOption,
    resetToDefaults: resetDisplayOptions,
  };
}
