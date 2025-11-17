import React, { useState, useMemo } from 'react';
import { Input } from '@/components/ui/input';
import { Button } from '@/components/ui/button';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Search, X, MessageSquare } from 'lucide-react';
import { formatDistanceToNow } from 'date-fns';
import { ru } from 'date-fns/locale';
import type { Message } from '@/types/realtime-chat';

interface ChatSearchProps {
  messages: Message[];
  onMessageSelect: (messageId: string) => void;
  onClose: () => void;
}

export function ChatSearch({ messages, onMessageSelect, onClose }: ChatSearchProps) {
  const [searchQuery, setSearchQuery] = useState('');

  const filteredMessages = useMemo(() => {
    if (!searchQuery.trim()) return [];
    
    const query = searchQuery.toLowerCase();
    return messages
      .filter(message => 
        message.content?.toLowerCase().includes(query) ||
        message.sender_profile?.first_name?.toLowerCase().includes(query) ||
        message.sender_profile?.last_name?.toLowerCase().includes(query)
      )
      .slice(0, 50) // Limit results for performance
      .reverse(); // Show newest first
  }, [messages, searchQuery]);

  const highlightText = (text: string, query: string) => {
    if (!query) return text;
    
    const parts = text.split(new RegExp(`(${query})`, 'gi'));
    return parts.map((part, index) => 
      part.toLowerCase() === query.toLowerCase() ? (
        <mark key={index} className="bg-yellow-200 text-black">{part}</mark>
      ) : part
    );
  };

  return (
    <div className="absolute inset-0 bg-background z-50 flex flex-col">
      {/* Search Header */}
      <div className="border-b p-4 flex items-center gap-3">
        <Search size={20} />
        <Input
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          placeholder="Поиск по сообщениям..."
          className="flex-1"
          autoFocus
        />
        <Button
          size="sm"
          variant="ghost"
          onClick={onClose}
        >
          <X size={16} />
        </Button>
      </div>

      {/* Search Results */}
      <div className="flex-1 overflow-hidden">
        {searchQuery.trim() === '' ? (
          <div className="flex items-center justify-center h-full text-muted-foreground">
            <div className="text-center">
              <Search size={48} className="mx-auto mb-4 opacity-50" />
              <p>Введите запрос для поиска по сообщениям</p>
            </div>
          </div>
        ) : filteredMessages.length === 0 ? (
          <div className="flex items-center justify-center h-full text-muted-foreground">
            <div className="text-center">
              <MessageSquare size={48} className="mx-auto mb-4 opacity-50" />
              <p>Сообщения не найдены</p>
              <p className="text-sm mt-2">Попробуйте изменить поисковый запрос</p>
            </div>
          </div>
        ) : (
          <ScrollArea className="h-full">
            <div className="p-4 space-y-3">
              {filteredMessages.map((message) => (
                <div
                  key={message.id}
                  className="p-3 border rounded-lg hover:bg-accent cursor-pointer transition-colors"
                  onClick={() => {
                    onMessageSelect(message.id);
                    onClose();
                  }}
                >
                  <div className="flex items-start gap-3">
                    <div className="w-8 h-8 rounded-full bg-muted flex items-center justify-center text-xs">
                      {message.sender_profile?.first_name?.[0] || 'П'}
                    </div>
                    
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 mb-1">
                        <span className="font-medium text-sm">
                          {message.sender_profile?.first_name || 'Пользователь'}
                        </span>
                        <span className="text-xs text-muted-foreground">
                          {formatDistanceToNow(new Date(message.created_at), { 
                            addSuffix: true, 
                            locale: ru 
                          })}
                        </span>
                      </div>
                      
                      <div className="text-sm text-foreground line-clamp-2">
                        {message.content ? (
                          highlightText(message.content, searchQuery)
                        ) : (
                          <span className="text-muted-foreground italic">
                            {message.message_type === 'image' ? 'Изображение' :
                             message.message_type === 'file' ? 'Файл' :
                             message.message_type === 'voice' ? 'Голосовое сообщение' :
                             'Медиа-сообщение'}
                          </span>
                        )}
                      </div>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </ScrollArea>
        )}
      </div>
    </div>
  );
}