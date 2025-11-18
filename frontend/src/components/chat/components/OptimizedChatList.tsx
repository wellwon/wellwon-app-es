import React, { memo } from 'react';
import { cn } from '@/lib/utils';
import type { Chat } from '@/types/realtime-chat';

interface OptimizedChatListProps {
  chats: Chat[];
  activeChat: Chat | null;
  onChatSelect: (chatId: string) => void;
  className?: string;
}

interface ChatItemProps {
  chat: Chat;
  isActive: boolean;
  onSelect: (chatId: string) => void;
}

// Memoized chat item to prevent unnecessary re-renders
const ChatItem = memo<ChatItemProps>(({ chat, isActive, onSelect }) => {
  return (
    <div
      className={cn(
        "p-3 cursor-pointer hover:bg-white/5 transition-colors border-l-2",
        isActive ? "bg-white/10 border-accent-blue" : "border-transparent"
      )}
      onClick={() => onSelect(chat.id)}
    >
      <div className="flex items-center justify-between mb-1">
        <h4 className="text-white font-medium text-sm truncate flex-1">
          {chat.name}
        </h4>
        {chat.unread_count > 0 && (
          <span className="bg-accent-red text-white text-xs px-2 py-1 rounded-full ml-2">
            {chat.unread_count}
          </span>
        )}
      </div>
      
      {chat.last_message && (
        <p className="text-white/60 text-xs truncate">
          {chat.last_message.content}
        </p>
      )}
      
      <div className="flex items-center justify-between mt-2">
        <span className="text-white/40 text-xs">
          {chat.participants?.length || 0} участник{chat.participants?.length === 1 ? '' : 'ов'}
        </span>
        
        {chat.updated_at && (
          <span className="text-white/40 text-xs">
            {new Date(chat.updated_at).toLocaleTimeString('ru', { 
              hour: '2-digit', 
              minute: '2-digit' 
            })}
          </span>
        )}
      </div>
    </div>
  );
}, (prevProps, nextProps) => {
  // Custom comparison function for optimization
  return (
    prevProps.chat.id === nextProps.chat.id &&
    prevProps.chat.name === nextProps.chat.name &&
    prevProps.chat.unread_count === nextProps.chat.unread_count &&
    prevProps.chat.updated_at === nextProps.chat.updated_at &&
    prevProps.isActive === nextProps.isActive &&
    JSON.stringify(prevProps.chat.last_message) === JSON.stringify(nextProps.chat.last_message)
  );
});

ChatItem.displayName = 'ChatItem';

// Main optimized chat list component
export const OptimizedChatList = memo<OptimizedChatListProps>(({ 
  chats, 
  activeChat, 
  onChatSelect, 
  className 
}) => {
  return (
    <div className={cn("flex flex-col", className)}>
      {chats.map(chat => (
        <ChatItem
          key={chat.id}
          chat={chat}
          isActive={activeChat?.id === chat.id}
          onSelect={onChatSelect}
        />
      ))}
    </div>
  );
}, (prevProps, nextProps) => {
  // Optimize list re-renders
  return (
    prevProps.chats.length === nextProps.chats.length &&
    prevProps.activeChat?.id === nextProps.activeChat?.id &&
    prevProps.chats.every((chat, index) => 
      chat.id === nextProps.chats[index]?.id &&
      chat.updated_at === nextProps.chats[index]?.updated_at &&
      chat.unread_count === nextProps.chats[index]?.unread_count
    )
  );
});

OptimizedChatList.displayName = 'OptimizedChatList';