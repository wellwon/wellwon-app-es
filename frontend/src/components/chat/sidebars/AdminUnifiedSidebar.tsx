import React from 'react';
import { useUnifiedSidebar } from '@/contexts/chat/UnifiedSidebarProvider';
import { useRealtimeChatContext } from '@/contexts/RealtimeChatContext';
import { Shield, Settings, BarChart3, Users, Info, MessageSquare, ShoppingCart, ExternalLink, Zap } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { GlassCard } from '@/components/design-system/GlassCard';
import SidebarChat from '@/components/platform/sidebar/SidebarChat';
import { usePlatform } from '@/contexts/PlatformContext';
import { useIsMobile } from '@/hooks/use-mobile';
import ServicesContent from '@/components/chat/services/ServicesContent';
import { MessageTemplatesContent } from '../components/MessageTemplatesContent';
import AdminActionsContent from '../components/AdminActionsContent';
import { ChatParticipantsSection } from '../components/ChatParticipantsSection';
import UnifiedSidebarBase from './UnifiedSidebarBase';
import { logger } from '@/utils/logger';
const AdminUnifiedSidebar = () => {
  const {
    contentType,
    openSidebar
  } = useUnifiedSidebar();
  const {
    isDeveloper
  } = usePlatform();
  const { activeChat } = useRealtimeChatContext();
  const isMobile = useIsMobile();

  // Проверяем, является ли пользователь админом
  const isAdmin = isDeveloper;

  // На мобильных устройствах скрываем правый сайдбар
  if (isMobile) {
    return null;
  }
  const getHeaderTitle = () => {
    if (!contentType) return 'Панель диалога';
    switch (contentType) {
      case 'deal':
        return 'Сделка';
      case 'services':
        return 'Услуги';
      case 'system-settings':
        return 'Системные настройки';
      case 'analytics':
        return 'Аналитика системы';
      case 'users':
        return 'Управление пользователями';
      case 'chat-list':
        return 'Все чаты';
      case 'message-templates':
        return 'Шаблоны сообщений';
      case 'admin-actions':
        return 'Действия администратора';
      default:
        return 'Панель диалога';
    }
  };
  const getContent = () => {
    if (!contentType) {
      return renderEmptyState();
    }
    switch (contentType) {
      case 'deal':
        return renderDealContent();
      case 'services':
        return renderServicesContent();
      case 'system-settings':
        return renderSystemSettingsContent();
      case 'analytics':
        return renderAnalyticsContent();
      case 'users':
        return renderUsersContent();
      case 'chat-list':
        return isAdmin ? renderChatListContent() : renderAccessDenied();
      case 'message-templates':
        return isAdmin ? renderMessageTemplatesContent() : renderAccessDenied();
      case 'admin-actions':
        return isAdmin ? renderAdminActionsContent() : renderAccessDenied();
      default:
        return renderEmptyState();
    }
  };
  const renderEmptyState = () => <div className="flex flex-col items-center justify-center h-full text-center py-16">
      <Info size={48} className="text-gray-400 mb-4" />
      <h3 className="text-white font-medium mb-2">Информация о заказе </h3>
      <p className="text-gray-400 text-sm max-w-xs">
        Информация о заказе появится здесь после выбора чата
      </p>
    </div>;
  const renderDealContent = () => <div className="space-y-6">
      {/* Кнопка создания сделки в Odoo */}
      <div className="mb-6">
        <Button className="w-full bg-accent-red hover:bg-accent-red/90 text-white font-medium py-3 flex items-center justify-center gap-2" onClick={() => {
        logger.info('Creating deal in Odoo system');
      }}>
          <ExternalLink size={16} />
          Создать сделку в Odoo
        </Button>
      </div>

      {/* Информация о сделке */}
      <div>
        <h3 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
          <ShoppingCart size={20} className="text-accent-red" />
          Информация о сделке
        </h3>
        
        <div className="space-y-4">
          <GlassCard variant="default" className="p-4">
            <div className="space-y-3">
              <div className="flex justify-between items-center">
                <span className="text-gray-400 text-sm">Статус:</span>
                <span className="text-white font-medium">В обработке</span>
              </div>
              <div className="flex justify-between items-center">
                <span className="text-gray-400 text-sm">Сумма:</span>
                <span className="text-white font-medium">€15,500</span>
              </div>
              <div className="flex justify-between items-center">
                <span className="text-gray-400 text-sm">Клиент:</span>
                <span className="text-white font-medium">ООО "Импорт-Экспорт"</span>
              </div>
              <div className="flex justify-between items-center">
                <span className="text-gray-400 text-sm">Дата создания:</span>
                <span className="text-white font-medium">15.01.2024</span>
              </div>
            </div>
          </GlassCard>

          <GlassCard variant="default" className="p-4">
            <h4 className="text-white font-medium mb-3">Товары</h4>
            <div className="space-y-2">
              <div className="text-sm">
                <div className="text-gray-300">• Товар A - 100 шт.</div>
                <div className="text-gray-400 ml-2">€5,000</div>
              </div>
              <div className="text-sm">
                <div className="text-gray-300">• Товар B - 50 шт.</div>
                <div className="text-gray-400 ml-2">€10,500</div>
              </div>
            </div>
          </GlassCard>

          <GlassCard variant="default" className="p-4">
            <h4 className="text-white font-medium mb-3">Логистика</h4>
            <div className="space-y-2 text-sm">
              <div className="flex justify-between">
                <span className="text-gray-400">Откуда:</span>
                <span className="text-gray-300">Шанхай, Китай</span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-400">Куда:</span>
                <span className="text-gray-300">Москва, Россия</span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-400">Тип доставки:</span>
                <span className="text-gray-300">Морской транспорт</span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-400">ETA:</span>
                <span className="text-gray-300">25.02.2024</span>
              </div>
            </div>
          </GlassCard>
        </div>
      </div>
    </div>;
  const renderServicesContent = () => <ServicesContent />;
  const renderSystemSettingsContent = () => <div className="space-y-6">
      <div>
        <h3 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
          <Settings size={20} className="text-accent-red" />
          Настройки системы
        </h3>
        
        <GlassCard variant="default" className="text-center py-8">
          <Settings size={32} className="text-gray-400 mx-auto mb-3" />
          <h4 className="text-white font-medium mb-2">Раздел в разработке</h4>
          <p className="text-gray-400 text-sm">Здесь будут системные настройки</p>
        </GlassCard>
      </div>
    </div>;
  const renderAnalyticsContent = () => <div className="space-y-6">
      <div>
        <h3 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
          <BarChart3 size={20} className="text-accent-red" />
          Аналитика платформы
        </h3>
        
        <GlassCard variant="default" className="text-center py-8">
          <BarChart3 size={32} className="text-gray-400 mx-auto mb-3" />
          <h4 className="text-white font-medium mb-2">Раздел в разработке</h4>
          <p className="text-gray-400 text-sm">Здесь будет аналитика использования платформы</p>
        </GlassCard>
      </div>
    </div>;
  const renderUsersContent = () => <div className="h-full">
      <ChatParticipantsSection activeChat={activeChat} />
    </div>;
  const renderChatListContent = () => <div className="h-full">
      <SidebarChat />
    </div>;
  const renderMessageTemplatesContent = () => <div className="h-full">
      <MessageTemplatesContent />
    </div>;
  const renderAdminActionsContent = () => <div className="h-full">
      <AdminActionsContent />
    </div>;
  const renderAccessDenied = () => <div className="flex flex-col items-center justify-center h-full text-center py-16">
      <Shield size={48} className="text-gray-400 mb-4" />
      <h3 className="text-white font-medium mb-2">Доступ запрещен</h3>
      <p className="text-gray-400 text-sm max-w-xs">
        У вас недостаточно прав для просмотра этого раздела
      </p>
    </div>;
  const adminFooter = isAdmin ? (
    <div className="w-full flex items-center justify-center gap-4">
      <Button
        onClick={() => openSidebar('message-templates')}
        className="flex-1 h-11 bg-light-gray hover:bg-light-gray/90 border border-white/20 transition-all duration-300 hover:scale-105 shadow-lg text-white flex items-center gap-2"
      >
        <MessageSquare size={18} />
        Шаблоны
      </Button>
      <Button
        onClick={() => openSidebar('admin-actions')}
        className="flex-1 h-11 bg-light-gray hover:bg-light-gray/90 border border-white/20 transition-all duration-300 hover:scale-105 shadow-lg text-white flex items-center gap-2"
      >
        <Zap size={18} />
        Действия
      </Button>
    </div>
  ) : undefined;

  return (
    <UnifiedSidebarBase
      title={getHeaderTitle()}
      footer={adminFooter}
    >
      {getContent()}
    </UnifiedSidebarBase>
  );
};
export default AdminUnifiedSidebar;