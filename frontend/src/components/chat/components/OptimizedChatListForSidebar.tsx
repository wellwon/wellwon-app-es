import React, { memo } from 'react';
import { cn } from '@/lib/utils';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Edit3, Trash2 } from 'lucide-react';
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
  const isAdmin = effectiveUserType === 'ww_admin' || effectiveUserType === 'ww_manager' || effectiveUserType === 'ww_developer';

  const handleChatClick = () => {
    onChatSelect(conversation.id);
  };

  return (
    <div>
      <div
        onClick={handleChatClick}
        className={cn(
          "group relative px-3 py-2.5 rounded-lg cursor-pointer border-l-2",
          isActive
            ? isLightTheme
              ? 'bg-gray-100 border-l-accent-red border-r border-t border-b border-gray-300'
              : 'bg-white/10 border-l-accent-red border-r border-t border-b border-white/20'
            : isLightTheme
              ? 'bg-white hover:bg-gray-50 border-l-transparent group-hover:border-l-accent-red/60 border-r border-t border-b border-gray-200 hover:border-gray-300'
              : 'hover:bg-white/5 border-l-transparent group-hover:border-l-accent-red/60 border-r border-t border-b border-transparent hover:border-white/10'
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
            {/* Company badge for admins */}
            {isAdmin ? (
              <CompanyBadge chatId={conversation.id} />
            ) : (
              <p className={`text-xs ${isLightTheme ? 'text-gray-500' : 'text-gray-400'}`}>
                {formatDate(conversation.updatedAt)}
              </p>
            )}
          </div>
        </div>

        {/* Rename and Delete buttons - only for admin users */}
        {isAdmin && (
          <>
            {/* Rename button */}
            <Button
              variant="ghost"
              size="icon"
              onClick={e => handleRenameChat(e, conversation.id)}
              className={`absolute top-2 right-8 opacity-0 group-hover:opacity-100 h-6 w-6 ${
                isLightTheme
                  ? 'hover:bg-gray-200 text-gray-500 hover:text-gray-900'
                  : 'hover:bg-white/20 text-gray-400 hover:text-white'
              }`}
            >
              <Edit3 size={12} />
            </Button>

            {/* Delete button */}
            <Button
              variant="ghost"
              size="icon"
              onClick={e => handleDeleteConversation(e, conversation.id)}
              className="absolute top-2 right-2 opacity-0 group-hover:opacity-100 h-6 w-6 hover:bg-red-500/20 text-gray-400 hover:text-red-400"
            >
              <Trash2 size={12} />
            </Button>
          </>
        )}
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
  return (
    prevProps.conversations.length === nextProps.conversations.length &&
    prevProps.activeChat?.id === nextProps.activeChat?.id &&
    prevProps.editingChatId === nextProps.editingChatId &&
    prevProps.isLightTheme === nextProps.isLightTheme &&
    prevProps.conversations.every((conv, index) =>
      conv.id === nextProps.conversations[index]?.id &&
      conv.title === nextProps.conversations[index]?.title &&
      conv.unreadCount === nextProps.conversations[index]?.unreadCount
    )
  );
});

OptimizedChatListForSidebar.displayName = 'OptimizedChatListForSidebar';