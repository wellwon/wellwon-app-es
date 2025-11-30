
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
  isLightTheme?: boolean;
}> = ({ label, active, onClick, isLightTheme }) => (
  <Button
    variant="ghost"
    size="sm"
    onClick={onClick}
    className={`
      h-7 px-2 text-xs font-medium rounded-md transition-all
      ${active
        ? 'bg-accent-red/20 text-accent-red border border-accent-red/30'
        : isLightTheme
          ? 'text-gray-600 hover:text-gray-900 hover:bg-gray-100'
          : 'text-gray-400 hover:text-white hover:bg-white/10'
      }
    `}
  >
    {label}
  </Button>
);

const ChatNavigationBar: React.FC = () => {
  const { activeChat, updateChat, initialLoading, sendInteractiveMessage, createChat, selectChat, messageFilter, setMessageFilter } = useRealtimeChatContext();
  const { isDeveloper, isLightTheme } = usePlatform();
  const [editDialogOpen, setEditDialogOpen] = useState(false);
  const { toast } = useToast();

  const isAdmin = isDeveloper;

  // Theme-aware styles (like Declarant page)
  const theme = isLightTheme ? {
    header: 'bg-white border-gray-300 shadow-sm',
    text: {
      primary: 'text-gray-900',
      secondary: 'text-[#6b7280]'
    },
    button: 'text-gray-600 hover:text-gray-900 hover:bg-gray-100',
    icon: 'bg-gray-200'
  } : {
    header: 'bg-dark-gray border-white/10',
    text: {
      primary: 'text-white',
      secondary: 'text-gray-400'
    },
    button: 'text-gray-400 hover:text-white hover:bg-white/10',
    icon: 'bg-accent-gray'
  };

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
    <div className={`h-16 border-b flex items-center gap-4 px-4 md:px-6 relative z-20 ${theme.header}`}>
      {/* Left side - chat name (flex-1 to fill, but min-w-0 to allow shrinking) */}
      <div className="flex items-center gap-2 md:gap-3 relative z-10 min-w-0 flex-1">
        {activeChat && (
          <div className={`w-8 h-8 rounded-lg flex items-center justify-center flex-shrink-0 ${theme.icon}`}>
            <MessageSquare size={16} className={isLightTheme ? 'text-gray-600' : 'text-white'} />
          </div>
        )}

        <div className="min-w-0 flex-1">
          {initialLoading ? (
            <>
              <h1 className={`font-semibold text-lg ${theme.text.primary}`}></h1>
              <p className={`text-sm ${theme.text.secondary}`}></p>
            </>
          ) : (
            <>
              <h1 className={`font-semibold text-base md:text-lg truncate max-w-[200px] md:max-w-none ${theme.text.primary}`}>
                {activeChat ? activeChat.name || `Чат ${activeChat.id.slice(-8)}` : ''}
              </h1>
            </>
          )}
        </div>
      </div>

      {/* Right side - filters and actions (flex-shrink-0 to keep size) */}
      <div className="flex items-center gap-1 md:gap-2 flex-shrink-0">
        {/* Message filter buttons - scrollable on small screens */}
        {activeChat && (
          <div className="flex items-center gap-0.5 md:gap-1 mr-2 md:mr-4 overflow-x-auto scrollbar-hide">
            <FilterButton
              label="ALL"
              active={messageFilter === 'all'}
              onClick={() => setMessageFilter('all')}
              isLightTheme={isLightTheme}
            />
            <FilterButton
              label="PIC"
              active={messageFilter === 'images'}
              onClick={() => setMessageFilter('images')}
              isLightTheme={isLightTheme}
            />
            <FilterButton
              label="PDF"
              active={messageFilter === 'pdf'}
              onClick={() => setMessageFilter('pdf')}
              isLightTheme={isLightTheme}
            />
            <FilterButton
              label="DOC"
              active={messageFilter === 'doc'}
              onClick={() => setMessageFilter('doc')}
              isLightTheme={isLightTheme}
            />
            <FilterButton
              label="XLS"
              active={messageFilter === 'xls'}
              onClick={() => setMessageFilter('xls')}
              isLightTheme={isLightTheme}
            />
            <FilterButton
              label="MIC"
              active={messageFilter === 'voice'}
              onClick={() => setMessageFilter('voice')}
              isLightTheme={isLightTheme}
            />
            <FilterButton
              label="OTH"
              active={messageFilter === 'other'}
              onClick={() => setMessageFilter('other')}
              isLightTheme={isLightTheme}
            />
          </div>
        )}

        {/* Кнопка "Поделиться ссылкой" */}
        {activeChat && (
          <Button
            variant="ghost"
            size="icon"
            onClick={handleShareChat}
            className={`h-8 w-8 ${theme.button}`}
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
            className={`h-8 w-8 ${theme.button}`}
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
