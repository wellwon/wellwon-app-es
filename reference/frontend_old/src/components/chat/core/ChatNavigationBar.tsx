
import React, { useState } from 'react';
import { useRealtimeChatContext } from '@/contexts/RealtimeChatContext';
import { usePlatform } from '@/contexts/PlatformContext';
import { MessageSquare, Edit, Share2 } from 'lucide-react';
import { Button } from '@/components/ui/button';

import { useToast } from '@/hooks/use-toast';
import ChatDialog from './ChatDialog';

// Filter button component
const FilterButton: React.FC<{
  label: string;
  active: boolean;
  onClick: () => void;
}> = ({ label, active, onClick }) => (
  <Button
    variant="ghost"
    size="sm"
    onClick={onClick}
    className={`
      h-7 px-2 text-xs font-medium rounded-md transition-all
      ${active 
        ? 'bg-accent-red/20 text-accent-red border border-accent-red/30' 
        : 'text-gray-400 hover:text-white hover:bg-white/10'
      }
    `}
  >
    {label}
  </Button>
);

const ChatNavigationBar: React.FC = () => {
  const { activeChat, updateChat, initialLoading, sendInteractiveMessage, createChat, selectChat, messageFilter, setMessageFilter } = useRealtimeChatContext();
  const { isDeveloper } = usePlatform();
  const [editDialogOpen, setEditDialogOpen] = useState(false);
  const { toast } = useToast();
  
  const isAdmin = isDeveloper;

  const handleSendTemplate = async () => {
    try {
      if (!activeChat) {
        const newChat = await createChat('Новый чат', 'direct');
        await selectChat(newChat.id);
      }

      const templateData = {
        type: 'company_registration_v2',
        title: 'Требуется регистрация компании',
        description: 'Для продолжения работы необходимо зарегистрировать вашу компанию в системе.',
        buttons: [
          {
            text: 'Зарегистрировать компанию',
            action: 'open_registration_form',
            style: 'primary'
          },
          {
            text: 'Отменить',
            action: 'cancel',
            style: 'secondary'
          }
        ]
      };

      if (sendInteractiveMessage) {
        await sendInteractiveMessage(templateData, 'Регистрация компании');
      }
    } catch (error) {
      
    }
  };

  

  // Определяем цвет в зависимости от типа пользователя
  const getAccentColor = () => {
    return 'accent-gray';
  };

  const accentColor = getAccentColor();

  const handleEditChat = () => {
    setEditDialogOpen(true);
  };

  const handleShareChat = async () => {
    if (!activeChat) return;
    
    const chatUrl = `${window.location.origin}/platform/chat/${activeChat.id}`;
    
    try {
      await navigator.clipboard.writeText(chatUrl);
      toast({
        title: 'Ссылка скопирована',
        description: 'Ссылка на чат скопирована в буфер обмена',
        variant: "info"
      });
    } catch (error) {
      toast({
        title: 'Ошибка',
        description: 'Не удалось скопировать ссылку',
        variant: "error"
      });
    }
  };

  return (
    <div className="h-16 bg-dark-gray border-b border-white/10 flex items-center justify-between px-6 relative z-20">
      <div className="flex items-center gap-3 relative z-10">
        {activeChat && (
          <div className="w-8 h-8 bg-accent-gray rounded-lg flex items-center justify-center">
            <MessageSquare size={16} className="text-white" />
          </div>
        )}
        
        <div>
          {initialLoading ? (
            <>
              <h1 className="text-white font-semibold text-lg"></h1>
              <p className="text-gray-400 text-sm"></p>
            </>
          ) : (
            <>
              <h1 className="text-white font-semibold text-lg">
                {activeChat ? activeChat.name || `Чат ${activeChat.id.slice(-8)}` : ''}
              </h1>
              <p className="text-gray-400 text-sm">
                {activeChat 
                  ? (activeChat.metadata as any)?.description || 'Краткое описание чата'
                  : ''
                }
              </p>
            </>
          )}
        </div>
      </div>

      <div className="flex items-center gap-2">
        {/* Message filter buttons */}
        {activeChat && (
          <div className="flex items-center gap-1 mr-4">
            <FilterButton 
              label="ALL" 
              active={messageFilter === 'all'} 
              onClick={() => setMessageFilter('all')} 
            />
            <FilterButton 
              label="PIC" 
              active={messageFilter === 'images'} 
              onClick={() => setMessageFilter('images')} 
            />
            <FilterButton 
              label="PDF" 
              active={messageFilter === 'pdf'} 
              onClick={() => setMessageFilter('pdf')} 
            />
            <FilterButton 
              label="DOC" 
              active={messageFilter === 'doc'} 
              onClick={() => setMessageFilter('doc')} 
            />
            <FilterButton 
              label="XLS" 
              active={messageFilter === 'xls'} 
              onClick={() => setMessageFilter('xls')} 
            />
            <FilterButton 
              label="MIC" 
              active={messageFilter === 'voice'} 
              onClick={() => setMessageFilter('voice')} 
            />
            <FilterButton 
              label="OTH" 
              active={messageFilter === 'other'} 
              onClick={() => setMessageFilter('other')} 
            />
          </div>
        )}
        
        {/* Кнопка "Поделиться ссылкой" */}
        {activeChat && (
          <Button
            variant="ghost"
            size="icon"
            onClick={handleShareChat}
            className="text-gray-400 hover:text-white hover:bg-white/10 h-8 w-8"
          >
            <Share2 size={14} />
          </Button>
        )}

        {/* Кнопка "Изменить" для админов */}
        {isAdmin && activeChat && (
          <Button
            variant="ghost"
            size="icon"
            onClick={handleEditChat}
            className="text-gray-400 hover:text-white hover:bg-white/10 h-8 w-8"
          >
            <Edit size={14} />
          </Button>
        )}
      </div>

        <ChatDialog
          open={editDialogOpen}
          onOpenChange={setEditDialogOpen}
          chat={activeChat}
          mode="edit"
          onUpdate={updateChat}
        />
    </div>
  );
};

export default ChatNavigationBar;
