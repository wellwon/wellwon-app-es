import React, { memo } from 'react';
import { cn } from '@/lib/utils';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Edit3, Trash2, Archive } from 'lucide-react';
import CompanyBadge from '@/components/platform/sidebar/CompanyBadge';
import ChatDialog from '@/components/chat/core/ChatDialog';
import TelegramIndicator from '../components/TelegramIndicator';
import type { Chat } from '@/types/realtime-chat';

interface OptimizedChatListForSidebarProps {
  chats: Chat[];
  activeChat: Chat | null;
  onChatSelect: (chatId: string) => void;
  conversations: any[];
  effectiveUserType: string;
  formatDate: (date: Date) => string;
  handleRenameChat: (e: React.MouseEvent, chatId: string) => void;
  handleArchiveChat: (e: React.MouseEvent, chatId: string) => void;
  handleDeleteConversation: (e: React.MouseEvent, conversationId: string) => void;
  isOpen: boolean;
  contentType: string | null;
  selectedDeal: any;
  editingChatId: string | null;
  handleSaveRename: (chatId: string, newName: string) => Promise<void>;
  setEditingChatId: (id: string | null) => void;
  className?: string;
  isLightTheme?: boolean;
}

interface ChatItemProps {
  conversation: any;
  chats: Chat[];
  activeChat: Chat | null;
  onChatSelect: (chatId: string) => void;
  effectiveUserType: string;
  formatDate: (date: Date) => string;
  handleRenameChat: (e: React.MouseEvent, chatId: string) => void;
  handleArchiveChat: (e: React.MouseEvent, chatId: string) => void;
  handleDeleteConversation: (e: React.MouseEvent, conversationId: string) => void;
  isOpen: boolean;
  contentType: string | null;
  selectedDeal: any;
  editingChatId: string | null;
  handleSaveRename: (chatId: string, newName: string) => Promise<void>;
  setEditingChatId: (id: string | null) => void;
  isLightTheme?: boolean;
}

// Мемоизированный элемент чата
const ChatItem = memo<ChatItemProps>(({
  conversation,
  chats,
  activeChat,
  onChatSelect,
  effectiveUserType,
  formatDate,
  handleRenameChat,
  handleArchiveChat,
  handleDeleteConversation,
  isOpen,
  contentType,
  selectedDeal,
  editingChatId,
  handleSaveRename,
  setEditingChatId,
  isLightTheme
}) => {
  const isActive = activeChat?.id === conversation.id;
  // Admin check for delete button visibility
  // effectiveUserType now receives profile.role (not user_type)
  const isAdmin = effectiveUserType === 'admin';

  const handleChatClick = () => {
    onChatSelect(conversation.id);
  };

  return (
    <div>
      <div
        onClick={handleChatClick}
        className={cn(
          "group relative px-3 py-2.5 rounded-lg cursor-pointer border",
          isActive
            ? isLightTheme
              ? 'bg-gray-100 border-l-2 border-l-accent-red border-gray-300'
              : 'bg-white/10 border-l-2 border-l-accent-red border-white/20'
            : isLightTheme
              ? 'bg-white hover:bg-gray-50 border-gray-200 hover:border-gray-300 hover:border-l-2 hover:border-l-accent-red/60'
              : 'bg-[#2e2e33] hover:bg-[#3a3a40] border-white/10 hover:border-white/20 hover:border-l-2 hover:border-l-accent-red/60'
        )}
      >
        <div className="flex justify-between items-start gap-2">
          <div className="flex-1 min-w-0 mr-2">
            <div className="flex items-center justify-between gap-2 mb-1">
              <div className="flex items-center gap-1 flex-1 min-w-0">
                <h4 className={`text-sm font-medium truncate pr-2 ${isLightTheme ? 'text-gray-900' : 'text-white'}`}>
                  {conversation.title}
                </h4>
                <TelegramIndicator chat={conversation} className="flex-shrink-0" />
              </div>
              <div className="flex items-center gap-2">
                {(conversation.unreadCount || 0) > 0 && (
                  <div className="h-4 w-4 bg-accent-red rounded-full flex items-center justify-center">
                    <span className="text-white text-[10px] font-bold">
                      {(conversation.unreadCount || 0) > 9 ? '9+' : conversation.unreadCount}
                    </span>
                  </div>
                )}
                {/* Deal badge */}
                {conversation.dealInfo && (
                  <Badge
                    variant="secondary"
                    className={cn(
                      "text-[10px] h-auto shadow-lg px-1.5 py-0.5 flex-shrink-0 border",
                      isOpen && contentType === 'deal-summary' && selectedDeal?.dealNumber === conversation.dealInfo.dealNumber
                        ? 'bg-accent-red text-white border-accent-red'
                        : 'bg-accent-red/20 text-accent-red border-accent-red/30'
                    )}
                  >
                    {conversation.dealInfo.dealNumber}
                  </Badge>
                )}
              </div>
            </div>
            {/* Company badge - visible for all users */}
            <CompanyBadge chatId={conversation.id} companyId={conversation.company_id} />
          </div>
        </div>

        {/* Chat controls - Rename, Archive, Delete - always visible */}
        <div className="absolute top-2 right-2 flex gap-0.5">
            {/* Rename button */}
            <Button
              variant="ghost"
              size="icon"
              onClick={e => handleRenameChat(e, conversation.id)}
              className={`h-6 w-6 ${
                isLightTheme
                  ? 'hover:bg-gray-200 text-gray-500 hover:text-gray-900'
                  : 'hover:bg-white/20 text-gray-400 hover:text-white'
              }`}
              title="Переименовать"
            >
              <Edit3 size={12} />
            </Button>

            {/* Archive button (soft delete) */}
            <Button
              variant="ghost"
              size="icon"
              onClick={e => handleArchiveChat(e, conversation.id)}
              className={`h-6 w-6 ${
                isLightTheme
                  ? 'hover:bg-amber-100 text-gray-500 hover:text-amber-600'
                  : 'hover:bg-amber-500/20 text-gray-400 hover:text-amber-400'
              }`}
              title="Архивировать"
            >
              <Archive size={12} />
            </Button>

            {/* Delete button - admin only */}
            {isAdmin && (
              <Button
                variant="ghost"
                size="icon"
                onClick={e => handleDeleteConversation(e, conversation.id)}
                className="h-6 w-6 hover:bg-red-500/20 text-gray-400 hover:text-red-400"
                title="Удалить"
              >
                <Trash2 size={12} />
              </Button>
            )}
          </div>
      </div>

      {/* Rename dialog is handled in parent component */}
    </div>
  );
}, (prevProps, nextProps) => {
  // Оптимизация ре-рендеров
  return (
    prevProps.conversation.id === nextProps.conversation.id &&
    prevProps.conversation.title === nextProps.conversation.title &&
    prevProps.conversation.unreadCount === nextProps.conversation.unreadCount &&
    prevProps.activeChat?.id === nextProps.activeChat?.id &&
    prevProps.editingChatId === nextProps.editingChatId &&
    prevProps.isOpen === nextProps.isOpen &&
    prevProps.contentType === nextProps.contentType &&
    prevProps.isLightTheme === nextProps.isLightTheme &&
    prevProps.effectiveUserType === nextProps.effectiveUserType &&
    JSON.stringify(prevProps.selectedDeal) === JSON.stringify(nextProps.selectedDeal)
  );
});

ChatItem.displayName = 'ChatItem';

// Главный оптимизированный компонент списка чатов для сайдбара
export const OptimizedChatListForSidebar = memo<OptimizedChatListForSidebarProps>(({
  chats,
  activeChat,
  onChatSelect,
  conversations,
  effectiveUserType,
  formatDate,
  handleRenameChat,
  handleArchiveChat,
  handleDeleteConversation,
  isOpen,
  contentType,
  selectedDeal,
  editingChatId,
  handleSaveRename,
  setEditingChatId,
  className,
  isLightTheme
}) => {
  return (
    <div className={cn("space-y-2 pb-4", className)}>
      {conversations.map(conversation => (
        <ChatItem
          key={conversation.id}
          conversation={conversation}
          chats={chats}
          activeChat={activeChat}
          onChatSelect={onChatSelect}
          effectiveUserType={effectiveUserType}
          formatDate={formatDate}
          handleRenameChat={handleRenameChat}
          handleArchiveChat={handleArchiveChat}
          handleDeleteConversation={handleDeleteConversation}
          isOpen={isOpen}
          contentType={contentType}
          selectedDeal={selectedDeal}
          editingChatId={editingChatId}
          handleSaveRename={handleSaveRename}
          setEditingChatId={setEditingChatId}
          isLightTheme={isLightTheme}
        />
      ))}
    </div>
  );
}, (prevProps, nextProps) => {
  // Оптимизация ре-рендеров списка
  // IMPORTANT: effectiveUserType must be compared for reactive admin status updates
  return (
    prevProps.conversations.length === nextProps.conversations.length &&
    prevProps.activeChat?.id === nextProps.activeChat?.id &&
    prevProps.editingChatId === nextProps.editingChatId &&
    prevProps.isLightTheme === nextProps.isLightTheme &&
    prevProps.effectiveUserType === nextProps.effectiveUserType &&
    prevProps.conversations.every((conv, index) =>
      conv.id === nextProps.conversations[index]?.id &&
      conv.title === nextProps.conversations[index]?.title &&
      conv.unreadCount === nextProps.conversations[index]?.unreadCount
    )
  );
});

OptimizedChatListForSidebar.displayName = 'OptimizedChatListForSidebar';