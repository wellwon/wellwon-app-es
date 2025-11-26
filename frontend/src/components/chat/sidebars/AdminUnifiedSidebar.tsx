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
    isDeveloper,
    isLightTheme
  } = usePlatform();
  const { activeChat } = useRealtimeChatContext();
  const isMobile = useIsMobile();

  // Проверяем, является ли пользователь админом
  const isAdmin = isDeveloper;

  // Theme-aware styles (like Declarant page)
  const theme = isLightTheme ? {
    text: {
      primary: 'text-gray-900',
      secondary: 'text-[#6b7280]',
      muted: 'text-gray-500'
    },
    card: 'bg-white border border-gray-200',
    cardText: {
      label: 'text-gray-500',
      value: 'text-gray-900'
    },
    button: {
      primary: 'bg-gray-100 hover:bg-gray-200 border-gray-300 text-gray-900',
      ghost: 'text-gray-600 hover:text-gray-900 hover:bg-gray-100'
    }
  } : {
    text: {
      primary: 'text-white',
      secondary: 'text-gray-400',
      muted: 'text-gray-500'
    },
    card: 'bg-white/5 border border-white/10',
    cardText: {
      label: 'text-gray-400',
      value: 'text-white'
    },
    button: {
      primary: 'bg-light-gray hover:bg-light-gray/90 border-white/10 text-white',
      ghost: 'text-gray-400 hover:text-white hover:bg-white/10'
    }
  };

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

  const renderEmptyState = () => (
    <div className="flex flex-col items-center justify-center h-full text-center py-16">
      <Info size={48} className={`mb-4 ${theme.text.secondary}`} />
      <h3 className={`font-medium mb-2 ${theme.text.primary}`}>Информация о заказе</h3>
      <p className={`text-sm max-w-xs ${theme.text.secondary}`}>
        Информация о заказе появится здесь после выбора чата
      </p>
    </div>
  );

  const renderDealContent = () => (
    <div className="space-y-6">
      {/* Кнопка создания сделки в Odoo */}
      <div className="mb-6">
        <Button
          className="w-full bg-accent-red hover:bg-accent-red/90 text-white font-medium py-3 flex items-center justify-center gap-2"
          onClick={() => {
            logger.info('Creating deal in Odoo system');
          }}
        >
          <ExternalLink size={16} />
          Создать сделку в Odoo
        </Button>
      </div>

      {/* Информация о сделке */}
      <div>
        <h3 className={`text-lg font-semibold mb-4 flex items-center gap-2 ${theme.text.primary}`}>
          <ShoppingCart size={20} className="text-accent-red" />
          Информация о сделке
        </h3>

        <div className="space-y-4">
          <div className={`rounded-xl p-4 ${theme.card}`}>
            <div className="space-y-3">
              <div className="flex justify-between items-center">
                <span className={`text-sm ${theme.cardText.label}`}>Статус:</span>
                <span className={`font-medium ${theme.cardText.value}`}>В обработке</span>
              </div>
              <div className="flex justify-between items-center">
                <span className={`text-sm ${theme.cardText.label}`}>Сумма:</span>
                <span className={`font-medium ${theme.cardText.value}`}>€15,500</span>
              </div>
              <div className="flex justify-between items-center">
                <span className={`text-sm ${theme.cardText.label}`}>Клиент:</span>
                <span className={`font-medium ${theme.cardText.value}`}>ООО "Импорт-Экспорт"</span>
              </div>
              <div className="flex justify-between items-center">
                <span className={`text-sm ${theme.cardText.label}`}>Дата создания:</span>
                <span className={`font-medium ${theme.cardText.value}`}>15.01.2024</span>
              </div>
            </div>
          </div>

          <div className={`rounded-xl p-4 ${theme.card}`}>
            <h4 className={`font-medium mb-3 ${theme.cardText.value}`}>Товары</h4>
            <div className="space-y-2">
              <div className="text-sm">
                <div className={theme.cardText.value}>• Товар A - 100 шт.</div>
                <div className={`ml-2 ${theme.cardText.label}`}>€5,000</div>
              </div>
              <div className="text-sm">
                <div className={theme.cardText.value}>• Товар B - 50 шт.</div>
                <div className={`ml-2 ${theme.cardText.label}`}>€10,500</div>
              </div>
            </div>
          </div>

          <div className={`rounded-xl p-4 ${theme.card}`}>
            <h4 className={`font-medium mb-3 ${theme.cardText.value}`}>Логистика</h4>
            <div className="space-y-2 text-sm">
              <div className="flex justify-between">
                <span className={theme.cardText.label}>Откуда:</span>
                <span className={theme.cardText.value}>Шанхай, Китай</span>
              </div>
              <div className="flex justify-between">
                <span className={theme.cardText.label}>Куда:</span>
                <span className={theme.cardText.value}>Москва, Россия</span>
              </div>
              <div className="flex justify-between">
                <span className={theme.cardText.label}>Тип доставки:</span>
                <span className={theme.cardText.value}>Морской транспорт</span>
              </div>
              <div className="flex justify-between">
                <span className={theme.cardText.label}>ETA:</span>
                <span className={theme.cardText.value}>25.02.2024</span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );

  const renderServicesContent = () => <ServicesContent />;

  const renderSystemSettingsContent = () => (
    <div className="flex flex-col items-center justify-center h-full text-center py-16">
      <Settings size={48} className={`mb-4 ${theme.text.secondary}`} />
      <h3 className={`font-medium mb-2 ${theme.text.primary}`}>Настройки</h3>
      <p className={`text-sm max-w-xs ${theme.text.secondary}`}>
        Раздел в разработке. Здесь будут системные настройки.
      </p>
    </div>
  );

  const renderAnalyticsContent = () => (
    <div className="flex flex-col items-center justify-center h-full text-center py-16">
      <BarChart3 size={48} className={`mb-4 ${theme.text.secondary}`} />
      <h3 className={`font-medium mb-2 ${theme.text.primary}`}>Аналитика</h3>
      <p className={`text-sm max-w-xs ${theme.text.secondary}`}>
        Раздел в разработке. Здесь будет аналитика платформы.
      </p>
    </div>
  );

  const renderUsersContent = () => (
    <div className="h-full">
      <ChatParticipantsSection activeChat={activeChat} />
    </div>
  );

  const renderChatListContent = () => (
    <div className="h-full">
      <SidebarChat />
    </div>
  );

  const renderMessageTemplatesContent = () => (
    <div className="h-full">
      <MessageTemplatesContent />
    </div>
  );

  const renderAdminActionsContent = () => (
    <div className="h-full">
      <AdminActionsContent />
    </div>
  );

  const renderAccessDenied = () => (
    <div className="flex flex-col items-center justify-center h-full text-center py-16">
      <Shield size={48} className={`mb-4 ${theme.text.secondary}`} />
      <h3 className={`font-medium mb-2 ${theme.text.primary}`}>Доступ запрещен</h3>
      <p className={`text-sm max-w-xs ${theme.text.secondary}`}>
        У вас недостаточно прав для просмотра этого раздела
      </p>
    </div>
  );

  // Filter-style button component (like in ChatNavigationBar)
  const FilterButton: React.FC<{
    label: string;
    icon: React.ReactNode;
    active: boolean;
    onClick: () => void;
  }> = ({ label, icon, active, onClick }) => (
    <Button
      variant="ghost"
      size="sm"
      onClick={onClick}
      className={`
        h-9 px-4 text-sm font-medium rounded-md transition-all flex items-center gap-2
        ${active
          ? 'bg-accent-red/20 text-accent-red border border-accent-red/30'
          : isLightTheme
            ? 'text-gray-600 hover:text-gray-900 hover:bg-gray-200 border border-gray-300'
            : 'text-gray-400 hover:text-white hover:bg-white/10 border border-white/10'
        }
      `}
    >
      {icon}
      {label}
    </Button>
  );

  const adminFooter = (
    <div className="w-full flex items-center justify-center gap-3">
      <FilterButton
        label="Шаблоны"
        icon={<MessageSquare size={16} />}
        active={contentType === 'message-templates'}
        onClick={() => openSidebar('message-templates')}
      />
      <FilterButton
        label="Действия"
        icon={<Zap size={16} />}
        active={contentType === 'admin-actions'}
        onClick={() => openSidebar('admin-actions')}
      />
    </div>
  );

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
