import React, { useEffect, useMemo, useRef } from 'react';
import { useUnifiedSidebar } from '@/contexts/chat';
import { usePlatform } from '@/contexts/PlatformContext';
import { useRealtimeChatContext } from '@/contexts/RealtimeChatContext';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Badge } from '@/components/ui/badge';
import { AppConfirmDialog } from '@/components/shared';
import { GlassButton } from '@/components/design-system/GlassButton';
import { Plus, Trash2, Archive, Search, Filter, Edit3, Users, Briefcase } from 'lucide-react';
import { useAuth } from '@/contexts/AuthContext';
import { useToast } from '@/hooks/use-toast';
import ChatDialog from '@/components/chat/core/ChatDialog';
import CompanyBadge from './CompanyBadge';

import { OptimizedChatListForSidebar } from '@/components/chat/components/OptimizedChatListForSidebar';
import { logger } from '@/utils/logger';
import { SupergroupsList } from './SupergroupsList';
import { GroupsPanel } from './GroupsPanel';

const SidebarChat: React.FC = () => {
  const {
    chats,
    activeChat,
    selectChat,
    createChat,
    initialLoading,
    deleteChat,
    hardDeleteChat,
    updateChat,
    setScopeBySupergroup,
    setScopeByCompany,
    loadChats
  } = useRealtimeChatContext();
  const {
    openSidebar,
    isOpen,
    contentType,
    selectedDeal
  } = useUnifiedSidebar();
  const {
    setActiveSection,
    isDeveloper
  } = usePlatform();
  const {
    user,
    profile
  } = useAuth();
  const {
    toast
  } = useToast();
  const [activeFilter, setActiveFilter] = React.useState<'archive' | 'search' | 'filter' | null>(null);
  const [isCreatingChat, setIsCreatingChat] = React.useState(false);
  const [editingChatId, setEditingChatId] = React.useState<string | null>(null);
  const [isDialogOpen, setIsDialogOpen] = React.useState(false);
  const [showNoChatsHint, setShowNoChatsHint] = React.useState(false);
  
  
  // Ref для отслеживания последнего ручного выбора группы
  const lastManualGroupSelectionRef = useRef<{ supergroupId: number | null; timestamp: number } | null>(null);
  // Ref для автовыбора первого чата при загрузке
  const selectFirstChatOnLoadRef = useRef(false);
  // Функция для восстановления состояния из localStorage
  const getInitialSidebarState = () => {
    try {
      const saved = localStorage.getItem('ww:chat.sidebar.state');
      if (!saved) return { mode: 'supergroups', collapsed: false, supergroupId: null };

      const state = JSON.parse(saved);
      
      // Проверяем валидность сохранённых данных
      if (typeof state !== 'object' || state === null) return { mode: 'supergroups', collapsed: false, supergroupId: null };
      if (state.timestamp && Date.now() - state.timestamp > 7 * 24 * 60 * 60 * 1000) {
        // Удаляем устаревшие данные (старше 7 дней)
        localStorage.removeItem('ww:chat.sidebar.state');
        return { mode: 'supergroups', collapsed: false, supergroupId: null };
      }

      // Если сохранён mode 'requests', принудительно заменяем на 'supergroups'
      const savedMode = state.activeMode === 'requests' ? 'supergroups' : state.activeMode;

      return {
        mode: ['supergroups', 'personal'].includes(savedMode) ? savedMode : 'supergroups',
        collapsed: typeof state.groupsPanelCollapsed === 'boolean' ? state.groupsPanelCollapsed : false,
        supergroupId: typeof state.selectedSupergroupId === 'number' ? state.selectedSupergroupId : null
      };
    } catch (error) {
      logger.error('Failed to restore sidebar state from localStorage', error, { component: 'SidebarChat' });
      return { mode: 'supergroups', collapsed: false, supergroupId: null };
    }
  };

  // Инициализация состояния напрямую из localStorage
  const initialState = getInitialSidebarState();
  const [activeMode, setActiveMode] = React.useState<'supergroups' | 'personal'>(initialState.mode as 'supergroups' | 'personal');
  const [groupsPanelCollapsed, setGroupsPanelCollapsed] = React.useState(initialState.collapsed);
  const [selectedSupergroupId, setSelectedSupergroupId] = React.useState<number | null>(initialState.supergroupId);
  const groupPanelWidth = groupsPanelCollapsed ? 80 : 320;

  // Ref для предотвращения циклических обновлений
  const isRestoringState = useRef(false);

  // LocalStorage key для сохранения состояния сайдбара
  const SIDEBAR_STATE_KEY = 'ww:chat.sidebar.state';

  // Функция для сохранения состояния в localStorage
  const saveSidebarState = React.useCallback((
    supergroupId: number | null,
    collapsed: boolean,
    mode: 'supergroups' | 'personal'
  ) => {
    if (isRestoringState.current) return;
    
    try {
      const state = {
        selectedSupergroupId: supergroupId,
        groupsPanelCollapsed: collapsed,
        activeMode: mode,
        timestamp: Date.now()
      };
      localStorage.setItem(SIDEBAR_STATE_KEY, JSON.stringify(state));
      logger.debug('Sidebar state saved', { state, component: 'SidebarChat' });
    } catch (error) {
      logger.error('Failed to save sidebar state to localStorage', error, { component: 'SidebarChat' });
    }
  }, [SIDEBAR_STATE_KEY]);


  // Ref to track last synced chat id
  const lastSyncedChatIdRef = useRef<string | null>(null);

  // Синхронизация с активным чатом: если есть активный чат и он принадлежит к supergroup,
  // автоматически показываем темы этой группы (только при смене активного чата)
  // НО уважаем ручной выбор группы пользователем
  useEffect(() => {
    if (!activeChat || isRestoringState.current) return;

    // Prevent running if we already synced this chat
    if (lastSyncedChatIdRef.current === activeChat.id) return;
    lastSyncedChatIdRef.current = activeChat.id;

    // Проверяем, был ли недавний ручной выбор группы (в течение 5 секунд)
    const manualSelection = lastManualGroupSelectionRef.current;
    const isRecentManualSelection = manualSelection &&
      (Date.now() - manualSelection.timestamp < 5000);

    if (isRecentManualSelection) {
      logger.debug('Skipping auto-sync: recent manual group selection detected', {
        manualSelection,
        component: 'SidebarChat'
      });
      return;
    }

    const chat = chats.find(c => c.id === activeChat.id);
    if (chat?.telegram_supergroup_id) {
      // У активного чата есть supergroup - настраиваем UI для отображения тем этой группы
      setSelectedSupergroupId(chat.telegram_supergroup_id);
      setActiveMode('supergroups');

      // Устанавливаем scope только если supergroup изменилась
      if (selectedSupergroupId !== chat.telegram_supergroup_id) {
        setScopeBySupergroup({
          id: chat.telegram_supergroup_id,
          company_id: chat.company_id
        });

        logger.debug('Sidebar state synchronized with active chat', {
          chatId: activeChat.id,
          supergroupId: chat.telegram_supergroup_id,
          companyId: chat.company_id,
          component: 'SidebarChat'
        });
      }
    } else if (chat && !chat.telegram_supergroup_id) {
      // Чат без supergroup - переключаемся на company scope
      setScopeByCompany(chat.company_id || null);
      setSelectedSupergroupId(null);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [activeChat?.id, chats]);

  // Event listener for chat mode changes from main sidebar
  useEffect(() => {
    const handleChatModeChange = (event: CustomEvent<'groups' | 'personal'>) => {
      const mode = event.detail;
      if (mode === 'groups') {
        handleModeChange('supergroups');
      } else if (mode === 'personal') {
        handleModeChange('personal');
      }
    };

    window.addEventListener('chatModeChange', handleChatModeChange as EventListener);
    return () => window.removeEventListener('chatModeChange', handleChatModeChange as EventListener);
  }, []);

  // Sync chatMode with main sidebar when activeMode changes
  useEffect(() => {
    const syncMode = activeMode === 'supergroups' ? 'groups' : 'personal';
    window.dispatchEvent(new CustomEvent('chatModeSync', { detail: syncMode }));
  }, [activeMode]);

  // Ref to prevent re-running scope sync
  const scopeSyncedRef = useRef<number | null>(null);

  // Синхронизация scope с визуально выбранной группой на старте (когда нет активного чата)
  useEffect(() => {
    // Выполняем только если нет активного чата, но есть визуально выбранная supergroup
    if (activeChat || selectedSupergroupId === null || isRestoringState.current) return;

    // Prevent infinite loop - only sync if supergroup actually changed
    if (scopeSyncedRef.current === selectedSupergroupId) return;
    scopeSyncedRef.current = selectedSupergroupId;

    // Устанавливаем scope для загрузки чатов выбранной группы
    setScopeBySupergroup({
      id: selectedSupergroupId,
      company_id: null // company_id определится автоматически при загрузке чатов
    });

    logger.debug('Setting scope for visually selected supergroup', {
      supergroupId: selectedSupergroupId,
      component: 'SidebarChat'
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedSupergroupId, activeChat]);

  // Обработчик события manual group selection из useRealtimeChat
  useEffect(() => {
    const handleManualGroupSelection = (event: CustomEvent) => {
      lastManualGroupSelectionRef.current = event.detail;
      logger.debug('Received manual group selection event', { detail: event.detail, component: 'SidebarChat' });
    };
    
    window.addEventListener('manualGroupSelection', handleManualGroupSelection as EventListener);
    return () => window.removeEventListener('manualGroupSelection', handleManualGroupSelection as EventListener);
  }, []);

  // Сохранение состояния при изменениях (с дебаунсом)
  useEffect(() => {
    const timeoutId = setTimeout(() => {
      saveSidebarState(selectedSupergroupId, groupsPanelCollapsed, activeMode);
    }, 500);

    return () => clearTimeout(timeoutId);
  }, [selectedSupergroupId, groupsPanelCollapsed, activeMode, saveSidebarState]);

  // Преобразуем realtime чаты в формат для отображения (мемоизировано)
  const conversations = useMemo(() => chats.map(chat => {
    // Chat transformation for display
    // Use last_message_at > updated_at > created_at for display, fallback to current time
    const dateStr = chat.last_message_at || chat.updated_at || chat.created_at;
    const parsedDate = dateStr ? new Date(dateStr) : new Date();
    // Guard against Invalid Date
    const validDate = isNaN(parsedDate.getTime()) ? new Date() : parsedDate;

    return {
      id: chat.id,
      title: chat.name || 'Новый чат',
      updatedAt: validDate,
      unreadCount: 0,
      company_id: chat.company_id, // Add company_id for CompanyBadge
      // Note: unread messages count to be implemented
      dealInfo: chat.metadata?.dealNumber ? {
        dealNumber: chat.metadata.dealNumber
      } : undefined,
      telegram_supergroup_id: chat.telegram_supergroup_id // Для фильтрации
    };
  }), [chats]);

  // Фильтруем conversations по режиму
  const filteredConversations = React.useMemo(() => {
    if (activeMode === 'personal') {
      // В режиме персональных чатов показываем только чаты без supergroup_id
      return conversations.filter(conversation => {
        return conversation.telegram_supergroup_id === null;
      });
    }

    // В режиме групповых чатов (оригинальная логика)
    let filtered = conversations.filter(conversation => {
      if (selectedSupergroupId !== null) {
        const matches = conversation.telegram_supergroup_id === selectedSupergroupId;
        if (!matches) {
          console.log('[SidebarChat] Chat filtered out:', conversation.id, 'supergroup:', conversation.telegram_supergroup_id, 'expected:', selectedSupergroupId);
        }
        return matches;
      }
      return !groupsPanelCollapsed ? conversation.telegram_supergroup_id == null : true;
    });

    // Фильтруем по топикам - показываем только активные чаты
    if (selectedSupergroupId !== null) {
      filtered = filtered.filter(conversation => {
        const chat = chats.find(c => c.id === conversation.id);
        if (!chat) return true;

        // Показываем только активные чаты
        if (chat.is_active === false) return false;

        // Показываем:
        // 1. General (topic_id = 1 или null)
        // 2. Проверенные топики (обнаруженные через webhook и подтвержденные)
        // 3. Топики созданные через приложение (имеют topic_id > 1, не требуют верификации)
        const isGeneral = chat.telegram_topic_id === 1 || chat.telegram_topic_id === null;
        const isVerified = chat.metadata?.topic_verified === true;
        const isAppCreatedTopic = chat.telegram_topic_id !== null && chat.telegram_topic_id > 1;

        const passes = isGeneral || isVerified || isAppCreatedTopic;
        return passes;
      });
    }

    return filtered;
  }, [conversations, selectedSupergroupId, groupsPanelCollapsed, chats, activeMode]);

  // Автовыбор первого чата при смене группы - НУЖЕН!
  React.useEffect(() => {
    if (selectFirstChatOnLoadRef.current && !initialLoading && filteredConversations.length > 0) {
      // Ищем чат general, если нет - берем первый
      const generalChat = chats.find(chat => 
        chat.telegram_supergroup_id === selectedSupergroupId && 
        (chat.name?.toLowerCase() === 'general' || chat.name?.toLowerCase() === 'генерал')
      );
      const targetChat = generalChat || chats.find(chat => chat.telegram_supergroup_id === selectedSupergroupId);
      
      if (targetChat) {
        selectChat(targetChat.id, true);
        selectFirstChatOnLoadRef.current = false;
      }
    }
  }, [filteredConversations.length, initialLoading, selectedSupergroupId, chats, selectChat]);

  // Управление показом hint "Нет чатов в выбранной группе" с задержкой 2 секунды
  React.useEffect(() => {
    if (selectedSupergroupId !== null && !initialLoading && filteredConversations.length === 0) {
      const timer = setTimeout(() => {
        setShowNoChatsHint(true);
      }, 2000);
      return () => clearTimeout(timer);
    } else {
      setShowNoChatsHint(false);
    }
  }, [selectedSupergroupId, initialLoading, filteredConversations.length]);

  // Отладочная информация
  React.useEffect(() => {
    logger.debug('SidebarChat state update', {
      selectedSupergroupId,
      totalChats: chats.length,
      conversationsCount: conversations.length,
      filteredConversationsCount: filteredConversations.length,
      chatsWithSupergroupId: chats.filter(c => c.telegram_supergroup_id).length,
      component: 'SidebarChat'
    });
  }, [selectedSupergroupId, chats.length, conversations.length, filteredConversations.length]);
  // Conversations ready for display

  // Мемоизированная функция создания dealInfo для предотвращения пересоздания объекта
  const createDealInfo = useMemo(() => (dealNumber: string) => ({
    dealNumber,
    product: "Телефоны Samsung Galaxy",
    weight: 12.5,
    volume: 0.8,
    quantity: 25,
    cost: 450000,
    deliveryTime: "14-16 рабочих дней",
    deliveryAddress: "Москва, ул. Тверская, 15",
    services: [{
      name: "Страхование груза",
      cost: 12500,
      status: "paid" as const
    }, {
      name: "Экспресс-доставка",
      cost: 8500,
      status: "pending" as const
    }, {
      name: "Упаковка",
      cost: 3200,
      status: "unpaid" as const
    }],
    payments: [{
      name: "Предоплата 50%",
      amount: 225000,
      status: "paid" as const
    }, {
      name: "Доплата",
      amount: 225000,
      status: "pending" as const,
      dueDate: "25.12.2024"
    }]
  }), []);

  // Единственная точка открытия sidebar - автоматически для активного чата с данными о сделке
  useEffect(() => {
    const activeConversation = conversations.find(conv => conv.id === activeChat?.id);
    if (activeConversation?.dealInfo) {
      // Проверяем, не открыт ли уже sidebar с теми же данными
      if (isOpen && contentType === 'deal-summary' && selectedDeal?.dealNumber === activeConversation.dealInfo.dealNumber) {
        return; // Не открываем повторно, если уже открыт с теми же данными
      }
      const dealInfo = createDealInfo(activeConversation.dealInfo.dealNumber);
      openSidebar('deal-summary', dealInfo);
    }
  }, [activeChat?.id, conversations, createDealInfo, openSidebar, isOpen, contentType, selectedDeal?.dealNumber]);

  const handleNewChat = async () => {
    if (!user?.id) {
      logger.error('Cannot create chat: user not authenticated', null, { user, component: 'SidebarChat' });
      toast({
        title: "Ошибка",
        description: "Вы должны быть авторизованы для создания чата",
        variant: "error"
      });
      return;
    }
    // Starting chat creation
    setIsCreatingChat(true);
    try {
      const newChat = await createChat('Новый чат', 'direct');
      // Chat created successfully
      setActiveSection('chat');
      toast({
        title: "Успешно",
        description: "Чат успешно создан"
      });
    } catch (error) {
      logger.error('Error creating chat from sidebar', error, { component: 'SidebarChat' });
      let errorMessage = "Не удалось создать чат. Попробуйте ещё раз.";
      if (error instanceof Error) {
        if (error.message.includes('row-level security')) {
          errorMessage = "Ошибка доступа к базе данных. Обратитесь к администратору.";
        } else if (error.message.includes('не авторизован')) {
          errorMessage = "Вы должны быть авторизованы для создания чата";
        }
      }
      toast({
        title: "Ошибка",
        description: errorMessage,
        variant: "error"
      });
    } finally {
      setIsCreatingChat(false);
    }
  };


  const handleChatClick = (conversation: any) => {
    logger.debug('Chat clicked', { conversationId: conversation.id, component: 'SidebarChat' });
    const chat = chats.find(c => c.id === conversation.id);
    if (chat) {
      logger.debug('Found chat, selecting', { chat, component: 'SidebarChat' });
      selectChat(chat.id, true); // обновляем URL при клике
    } else {
      logger.error('Chat not found in chats list', null, { conversationId: conversation.id, component: 'SidebarChat' });
    }
  };

  const formatDate = (date: Date) => {
    const now = new Date();
    const diffMs = now.getTime() - date.getTime();
    const diffHours = diffMs / (1000 * 60 * 60);
    const diffDays = diffMs / (1000 * 60 * 60 * 24);
    if (diffHours < 1) return 'Только что';
    if (diffHours < 24) return `${Math.floor(diffHours)}ч назад`;
    if (diffDays < 7) return `${Math.floor(diffDays)}д назад`;
    return date.toLocaleDateString('ru-RU', {
      day: '2-digit',
      month: '2-digit'
    });
  };

  const handleRenameChat = (e: React.MouseEvent, chatId: string) => {
    e.stopPropagation();
    setEditingChatId(chatId);
  };

  const handleSaveRename = async (chatId: string, newName: string) => {
    try {
      await updateChat(chatId, newName, '');
    } catch (error) {
      throw error; // Пробрасываем ошибку для обработки в диалоге
    }
  };

  const handleDeleteConversation = async (e: React.MouseEvent, conversationId: string) => {
    e.stopPropagation();
    if (window.confirm('Удалить этот диалог навсегда? Это действие нельзя отменить.')) {
      try {
        await hardDeleteChat(conversationId);
        toast({
          title: "Успешно",
          description: "Чат удален навсегда"
        });
      } catch (error) {
        logger.error('Error hard deleting chat', error, { component: 'SidebarChat' });
        toast({
          title: "Ошибка",
          description: "Не удалось удалить чат",
          variant: "error"
        });
      }
    }
  };

  // Обработчики для иерархического интерфейса
  const handleGroupsToggle = () => {
    setGroupsPanelCollapsed(prev => !prev);
    // выбранную группу не сбрасываем
  };

  const handleSelectGroup = (supergroupId: number | null) => {
    logger.debug('Group selected manually', { supergroupId, previousSelection: selectedSupergroupId, component: 'SidebarChat' });
    
    // Записываем время ручного выбора группы
    lastManualGroupSelectionRef.current = {
      supergroupId,
      timestamp: Date.now()
    };
    
    // Сбрасываем hint состояние при смене группы
    setShowNoChatsHint(false);
    
    // Очищаем chatId из URL при ручном выборе группы и устанавливаем активную секцию
    const url = new URL(window.location.href);
    if (url.pathname.includes('/chat/')) {
      const newPath = url.pathname.split('/chat/')[0] + '/chat';
      window.history.replaceState({}, '', newPath + url.search + url.hash);
    }
    setActiveSection('chat');
    
    // Отмечаем, что нужно выбрать первый чат после загрузки
    selectFirstChatOnLoadRef.current = true;
    
    setSelectedSupergroupId(supergroupId);
  };

  const handleModeChange = (mode: 'supergroups' | 'personal') => {
    if (mode === 'supergroups') {
      setGroupsPanelCollapsed(false);
      setActiveMode('supergroups');
    } else {
      setActiveMode(mode);
      setGroupsPanelCollapsed(true);
      setSelectedSupergroupId(null);
    }
  };

  return (
    <div className="h-full flex overflow-hidden">
      {/* Левая панель групп - показываем только в режиме супергрупп */}
      {activeMode === 'supergroups' && (
        <GroupsPanel
          selectedSupergroupId={selectedSupergroupId}
          onSelectGroup={handleSelectGroup}
          onToggleGroups={handleGroupsToggle}
          width={groupPanelWidth}
          collapsed={groupsPanelCollapsed}
          activeMode={activeMode}
          onModeChange={handleModeChange}
        />
      )}

      {/* Основная панель чатов */}
      <div
        className="h-full flex-1 min-w-0 border-r border-white/10 flex flex-col overflow-hidden"
        style={{
          backgroundColor: '#232328'
        }}
      >
        {/* Заголовок с кнопкой создания */}
        <div className="h-16 flex items-center justify-between pl-6 pr-4 border-b border-white/10">
          <div className="flex-1">
            {activeMode === 'personal' ? (
              <div className="text-white">
                <h2 className="font-semibold text-lg">Чаты с ботом</h2>
                <p className="text-xs text-gray-400">
                  {filteredConversations.length} чатов
                </p>
              </div>
            ) : selectedSupergroupId !== null ? (
              <div className="text-white">
                <h2 className="font-semibold text-lg">Темы / запросы</h2>
                <p className="text-xs text-gray-400">
                  {filteredConversations.length} тем
                </p>
              </div>
            ) : !groupsPanelCollapsed ? (
              <div className="text-white">
                <h2 className="font-semibold text-lg">Все чаты</h2>
                <p className="text-xs text-gray-400">
                  {conversations.length} диалогов
                </p>
              </div>
            ) : null}
          </div>
          
          {/* Кнопка создания новой темы */}
          <Button
            size="icon"
            variant="ghost"
            onClick={() => selectedSupergroupId ? setIsDialogOpen(true) : undefined}
            disabled={isCreatingChat || selectedSupergroupId === null}
            className={`h-8 w-8 p-0 transition-colors ${
              selectedSupergroupId !== null
                ? 'bg-accent-red hover:bg-accent-red-dark text-white'
                : 'text-gray-500 cursor-not-allowed'
            }`}
            title={selectedSupergroupId ? "Создать новую тему" : "Выберите группу для создания темы"}
          >
            <Plus size={16} />
          </Button>
        </div>

        {/* Панель поиска и фильтров */}
        <div className="h-16 pl-6 pr-4 border-b border-white/10 flex flex-col justify-center space-y-1">
          <div className="flex items-center gap-3">
            {/* Поле поиска слева */}
            <div className="relative flex-1">
              <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 h-4 w-4 text-gray-400" />
              <Input 
                placeholder="Поиск чатов..." 
                className="pl-10 bg-white/5 border-white/10 text-white placeholder:!text-[#9da3af] focus:border-white/20" 
              />
            </div>
            
            {/* Кнопки фильтров справа */}
            <div className="flex items-center gap-2">
              <Button 
                size="icon"
                variant="ghost" 
                onClick={() => setActiveFilter(activeFilter === 'archive' ? null : 'archive')} 
                className={`h-8 w-8 transition-colors ${
                  activeFilter === 'archive' 
                    ? 'text-accent-red border border-accent-red/60 bg-accent-red/10 hover:bg-accent-red/20' 
                    : 'text-gray-400 hover:text-white hover:bg-white/10'
                }`}
              >
                <Archive size={14} />
              </Button>
              <Button 
                size="icon"
                variant="ghost" 
                onClick={() => setActiveFilter(activeFilter === 'filter' ? null : 'filter')} 
                className={`h-8 w-8 transition-colors ${
                  activeFilter === 'filter' 
                    ? 'text-accent-red border border-accent-red/60 bg-accent-red/10 hover:bg-accent-red/20' 
                    : 'text-gray-400 hover:text-white hover:bg-white/10'
                }`}
              >
                <Filter size={14} />
              </Button>
            </div>
          </div>
        </div>

        {/* Контент в зависимости от активного режима */}
        <div className="flex-1 min-h-0">
          <ScrollArea className="h-full pt-4">
            {(activeMode === 'personal' || (!groupsPanelCollapsed || selectedSupergroupId !== null)) && (
              <>
                {initialLoading ? (
                  <div className="hidden">
                    
                  </div>
                ) : filteredConversations.length === 0 ? (
                  <div className="space-y-2 pb-4">
                    {selectedSupergroupId && showNoChatsHint ? (
                      <div className="text-center py-4">
                        <p className="text-gray-500 text-xs">
                          Нет чатов в выбранной группе
                        </p>
                      </div>
                    ) : !user?.id ? (
                      <div className="text-center py-4">
                        <p className="text-gray-500 text-xs">
                          Войдите в систему для создания чатов
                        </p>
                      </div>
                    ) : null}
                  </div>
                ) : (
                  <OptimizedChatListForSidebar
                    chats={chats.filter(chat => {
                      if (activeMode === 'personal') {
                        return chat.telegram_supergroup_id === null;
                      }
                      if (selectedSupergroupId !== null) {
                        return chat.telegram_supergroup_id === selectedSupergroupId;
                      }
                      return !groupsPanelCollapsed ? chat.telegram_supergroup_id == null : true;
                    })}
                    activeChat={activeChat}
                    onChatSelect={selectChat}
                    conversations={filteredConversations}
                    effectiveUserType={profile?.role || 'user'}
                    formatDate={formatDate}
                    handleRenameChat={handleRenameChat}
                    handleDeleteConversation={handleDeleteConversation}
                    isOpen={isOpen}
                    contentType={contentType}
                    selectedDeal={selectedDeal}
                    editingChatId={editingChatId}
                    handleSaveRename={handleSaveRename}
                    setEditingChatId={setEditingChatId}
                    className="space-y-2 pb-4 px-4"
                  />
                )}
              </>
            )}
          </ScrollArea>
        </div>
        
        {/* Bottom alignment container - buttons removed, now controlled by main sidebar */}
        <div className={`border-t border-white/10 mt-auto min-h-24 flex items-center ${!groupsPanelCollapsed ? 'p-2' : 'p-3'}`}>
          {/* Empty container for potential future use */}
        </div>
        
        {/* Диалог переименования чата */}
        <ChatDialog 
          open={!!editingChatId} 
          onOpenChange={open => !open && setEditingChatId(null)} 
          chat={editingChatId ? chats.find(c => c.id === editingChatId) || null : null}
          mode="rename"
          onUpdate={handleSaveRename} 
        />
        
        {/* Диалог создания нового чата */}
        <AppConfirmDialog
          open={isDialogOpen}
          onOpenChange={setIsDialogOpen}
          onConfirm={() => {
            handleNewChat();
            setIsDialogOpen(false);
          }}
          title="Создание нового диалога"
          description="Вы уверены, что хотите создать новую тему?"
          confirmText="Создать"
          cancelText="Отмена"
          icon={Plus}
        />

      </div>
    </div>
  );
};

export default SidebarChat;