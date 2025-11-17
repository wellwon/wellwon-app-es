import React from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Avatar, AvatarFallback, AvatarImage } from '@/components/ui/avatar';
import { Badge } from '@/components/ui/badge';
import { Separator } from '@/components/ui/separator';
import { Building2, Users, Crown, UserCog, User } from 'lucide-react';
import { useRealtimeChatContext } from '@/contexts/RealtimeChatContext';
import { usePlatform } from '@/contexts/PlatformContext';

const ChatInfoPanel: React.FC = () => {
  const { activeChat } = useRealtimeChatContext();
  const { isDeveloper, selectedCompany } = usePlatform();

  // Если нет активного чата, не показываем панель
  if (!activeChat) {
    return null;
  }

  // Проверяем, что activeChat соответствует выбранной компании
  if (selectedCompany && activeChat.company_id !== selectedCompany.id) {
    return (
      <div className="p-4">
        <Card style={{ backgroundColor: '#2c2c33' }} className="border-white/10">
          <CardContent className="pt-4">
            <p className="text-gray-400 text-sm text-center">
              Чат не принадлежит выбранной компании
            </p>
          </CardContent>
        </Card>
      </div>
    );
  }

  const isAdmin = isDeveloper;

  const getRoleIcon = (role: string) => {
    switch (role) {
      case 'admin':
        return <Crown className="h-3 w-3" />;
      case 'moderator':
        return <UserCog className="h-3 w-3" />;
      default:
        return <User className="h-3 w-3" />;
    }
  };

  const getRoleColor = (role: string) => {
    switch (role) {
      case 'admin':
        return 'bg-accent-red/20 text-accent-red border-accent-red/30';
      case 'moderator':
        return 'bg-blue-500/20 text-blue-400 border-blue-500/30';
      default:
        return 'bg-gray-500/20 text-gray-300 border-gray-500/30';
    }
  };

  const getRoleName = (role: string) => {
    switch (role) {
      case 'admin':
        return 'Администратор';
      case 'moderator':
        return 'Модератор';
      case 'member':
        return 'Участник';
      default:
        return 'Участник';
    }
  };

  return (
    <div className="space-y-4">
      {/* Chat Participants */}
      <Card style={{ backgroundColor: '#2c2c33' }} className="border-white/10">
        <CardHeader className="pb-3">
          <CardTitle className="text-white text-sm flex items-center gap-2">
            <Users className="h-4 w-4" />
            Участники чата
            {activeChat.company_id ? (
              <Badge variant="outline" className="text-xs bg-accent-red/20 text-accent-red border-accent-red/30">
                {`Компания #${activeChat.company_id}`}
              </Badge>
            ) : (
              <Badge variant="outline" className="text-xs bg-gray-500/20 text-gray-400 border-gray-500/30">
                Не привязан к компании
              </Badge>
            )}
          </CardTitle>
        </CardHeader>
        <CardContent className="pt-0">
          {activeChat.participants && activeChat.participants.length > 0 ? (
            <div className="space-y-3">
              {activeChat.participants
                .filter(p => p.is_active)
                .map((participant, index) => (
                  <div key={participant.user_id} className="space-y-2">
                    <div className="flex items-center gap-3">
                      <Avatar className="h-8 w-8">
                        <AvatarImage src={participant.profile?.avatar_url || undefined} />
                        <AvatarFallback className="bg-white/10 text-white text-xs">
                          {participant.profile?.first_name?.[0] || participant.profile?.last_name?.[0] || 'U'}
                        </AvatarFallback>
                      </Avatar>
                      
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2">
                          <span className="text-white text-sm truncate">
                            {participant.profile?.first_name || participant.profile?.last_name ? 
                              `${participant.profile?.first_name || ''} ${participant.profile?.last_name || ''}`.trim() :
                              'Пользователь'
                            }
                          </span>
                          <Badge 
                            variant="outline" 
                            className={`text-xs ${getRoleColor(participant.role)}`}
                          >
                            <div className="flex items-center gap-1">
                              {getRoleIcon(participant.role)}
                              {getRoleName(participant.role)}
                            </div>
                          </Badge>
                        </div>
                        
                        {participant.profile?.type && (
                          <p className="text-gray-400 text-xs">
                            {participant.profile.type === 'ww_manager' ? 'Менеджер' :
                             participant.profile.type === 'ww_developer' ? 'Разработчик' :
                             'Пользователь'}
                          </p>
                        )}
                      </div>
                    </div>
                    
                    {index < activeChat.participants.filter(p => p.is_active).length - 1 && (
                      <Separator className="bg-white/10" />
                    )}
                  </div>
                ))}
            </div>
          ) : (
            <p className="text-gray-400 text-xs">
              Нет активных участников
            </p>
          )}
        </CardContent>
      </Card>

      {/* Chat Metadata */}
      <Card style={{ backgroundColor: '#2c2c33' }} className="border-white/10">
        <CardContent className="pt-4">
          <div className="space-y-2">
            {activeChat.chat_number !== undefined && activeChat.chat_number !== null && (
              <div className="flex justify-between text-xs">
                <span className="text-gray-400">ID диалога:</span>
                <span className="text-white font-sans">
                  {activeChat.chat_number}
                </span>
              </div>
            )}
            
            <div className="flex justify-between text-xs">
              <span className="text-gray-400">Создан:</span>
              <span className="text-white">
                {new Date(activeChat.created_at).toLocaleDateString('ru-RU')}
              </span>
            </div>
            
            <div className="flex justify-between text-xs">
              <span className="text-gray-400">Тип чата:</span>
              <span className="text-white">
                {activeChat.type === 'direct' ? 'Прямой' :
                 activeChat.type === 'group' ? 'Групповой' :
                 activeChat.type === 'company' ? 'Компания' :
                 'Неизвестно'}
              </span>
            </div>
            
            {activeChat.last_message && (
              <div className="flex justify-between text-xs">
                <span className="text-gray-400">Последнее сообщение:</span>
                <span className="text-white">
                  {new Date(activeChat.last_message.created_at).toLocaleDateString('ru-RU')}
                </span>
              </div>
            )}
          </div>
        </CardContent>
      </Card>
    </div>
  );
};

export default ChatInfoPanel;