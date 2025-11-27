
import React, { useState, useEffect, useMemo } from 'react';
import { TelegramChatService } from '@/services/TelegramChatService';
import { CompanyService } from '@/services/CompanyService';
import { useRealtimeChatContext } from '@/contexts/RealtimeChatContext';
import { usePlatform } from '@/contexts/PlatformContext';
import { supabase } from '@/integrations/supabase/client';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { GlassButton } from '@/components/design-system';
import { OptimizedImage } from '@/components/chat/components/OptimizedImage';
import { Users, ChevronLeft, ChevronRight, Search, Archive, Filter, Edit3, Building, Plus, Briefcase, DollarSign, Truck, Package, ShoppingCart, Layers, Settings } from 'lucide-react';
import { logger } from '@/utils/logger';
import { AdminFormsModal } from '@/components/chat/components/AdminFormsModal';
import { EditCompanyGroupModal } from '@/components/chat/components/EditCompanyGroupModal';
import AppConfirmDialog from '@/components/shared/AppConfirmDialog';
import type { TelegramSupergroup } from '@/types/chat';
import type { CompanyFormData, SupergroupFormData } from '@/types/company-form';

interface GroupsPanelProps {
  selectedSupergroupId: number | null;
  onSelectGroup: (supergroupId: number | null) => void;
  onToggleGroups: () => void;
  width: number;
  collapsed: boolean;
  activeMode: 'supergroups' | 'personal';
  onModeChange: (mode: 'supergroups' | 'personal') => void;
}

export const GroupsPanel: React.FC<GroupsPanelProps> = ({
  selectedSupergroupId,
  onSelectGroup,
  onToggleGroups,
  width,
  collapsed,
  activeMode,
  onModeChange
}) => {
  const { setScopeBySupergroup } = useRealtimeChatContext();
  const { isLightTheme } = usePlatform();

  // Theme-aware styles
  const theme = isLightTheme ? {
    bg: 'bg-[#e8e8e8]',
    bgCard: 'bg-white',
    bgCardHover: 'hover:bg-gray-50',
    bgCardSelected: 'bg-gray-100',
    border: 'border-gray-300',
    text: {
      primary: 'text-gray-900',
      secondary: 'text-gray-600',
      muted: 'text-gray-500'
    },
    input: 'bg-white border-gray-300 text-gray-900 placeholder:text-gray-400',
    button: {
      ghost: 'bg-white border border-gray-300 text-gray-600 hover:text-gray-900 hover:bg-gray-50 hover:border-gray-400 hover:scale-105',
      active: 'bg-white border border-accent-red text-accent-red hover:bg-accent-red/10'
    }
  } : {
    bg: 'bg-[#232328]',
    bgCard: 'bg-[#2e2e33]',
    bgCardHover: 'hover:bg-[#3a3a40]',
    bgCardSelected: 'bg-white/5',
    border: 'border-white/10',
    text: {
      primary: 'text-white',
      secondary: 'text-gray-400',
      muted: 'text-gray-500'
    },
    input: 'bg-white/5 border-white/10 text-white placeholder:!text-[#9da3af]',
    button: {
      ghost: 'bg-white/5 border border-white/10 text-gray-400 hover:text-white hover:bg-white/10 hover:border-white/20 hover:scale-105',
      active: 'text-accent-red border-accent-red/60 bg-accent-red/10 hover:bg-accent-red/20'
    }
  };
  const [activeSupergroups, setActiveSupergroups] = useState<TelegramSupergroup[]>([]);
  const [archivedSupergroups, setArchivedSupergroups] = useState<TelegramSupergroup[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [chatCounts, setChatCounts] = useState<Record<number, number>>({});
  const [companyBalances, setCompanyBalances] = useState<Record<number, number>>({});
  const [isCreateCompanyModalOpen, setIsCreateCompanyModalOpen] = useState(false);
  const [showArchived, setShowArchived] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');
  const [expandedGroupId, setExpandedGroupId] = useState<number | null>(null);
  const [editingGroupId, setEditingGroupId] = useState<number | null>(null);
  const [editingCompanyId, setEditingCompanyId] = useState<number | null>(null);
  const [preloadedCompanyType, setPreloadedCompanyType] = useState<string>('company');
  const [preloadedCompanyData, setPreloadedCompanyData] = useState<CompanyFormData | null>(null);
  const [preloadedSupergroupData, setPreloadedSupergroupData] = useState<SupergroupFormData | null>(null);
  const [archiveConfirmOpen, setArchiveConfirmOpen] = useState<number | null>(null);
  const [selectedTypeFilter, setSelectedTypeFilter] = useState<string | null>(null);

  useEffect(() => {
    const loadSupergroups = async () => {
      try {
        setLoading(true);
        setError(null);
        
        // Загружаем активные и архивные супергруппы параллельно
        const [activeSupergroupsData, archivedSupergroupsData, chatCountsData] = await Promise.all([
          TelegramChatService.getAllSupergroups(true),  // active
          TelegramChatService.getAllSupergroups(false), // archived
          TelegramChatService.getSupergroupChatCounts()
        ]);
        
        setActiveSupergroups(activeSupergroupsData);
        setArchivedSupergroups(archivedSupergroupsData);
        setChatCounts(chatCountsData);
        
        // Загружаем балансы компаний для всех групп
        const allSupergroups = [...activeSupergroupsData, ...archivedSupergroupsData];
        const companyIds = allSupergroups
          .filter(group => group.company_id)
          .map(group => group.company_id!);
        
        if (companyIds.length > 0) {
          try {
            const balances: Record<number, number> = {};
            await Promise.all(
              companyIds.map(async (companyId) => {
                try {
                  // Since there's no getCompany method, we'll create a SQL query to get company balance
                  const { data: company } = await supabase
                    .from('companies')
                    .select('balance')
                    .eq('id', companyId)
                    .single();
                  if (company) {
                    balances[companyId] = company.balance || 0;
                  }
                } catch (err) {
                  logger.warn('Failed to load company balance', { companyId, error: err });
                  balances[companyId] = 0;
                }
              })
            );
            setCompanyBalances(balances);
          } catch (err) {
            logger.error('Failed to load company balances', err);
          }
        }
        
        logger.info('Loaded supergroups and chat counts for panel', { 
          activeCount: activeSupergroupsData.length,
          archivedCount: archivedSupergroupsData.length,
          chatCounts: chatCountsData
        });
      } catch (err) {
        logger.error('Failed to load supergroups for panel', err);
        setError('Ошибка загрузки');
      } finally {
        setLoading(false);
      }
    };

    loadSupergroups();
  }, []);

  const handleCreateCompanySuccess = () => {
    // Перезагружаем супергруппы после создания компании
    const loadSupergroups = async () => {
      try {
        const [activeSupergroupsData, archivedSupergroupsData, chatCountsData] = await Promise.all([
          TelegramChatService.getAllSupergroups(true),
          TelegramChatService.getAllSupergroups(false),
          TelegramChatService.getSupergroupChatCounts()
        ]);
        
        setActiveSupergroups(activeSupergroupsData);
        setArchivedSupergroups(archivedSupergroupsData);
        setChatCounts(chatCountsData);
        
        // Перезагружаем балансы компаний
        const allSupergroups = [...activeSupergroupsData, ...archivedSupergroupsData];
        const companyIds = allSupergroups
          .filter(group => group.company_id)
          .map(group => group.company_id!);
        
        if (companyIds.length > 0) {
          try {
            const balances: Record<number, number> = {};
            await Promise.all(
              companyIds.map(async (companyId) => {
                try {
                  // Since there's no getCompany method, we'll create a SQL query to get company balance
                  const { data: company } = await supabase
                    .from('companies')
                    .select('balance')
                    .eq('id', companyId)
                    .single();
                  if (company) {
                    balances[companyId] = company.balance || 0;
                  }
                } catch (err) {
                  balances[companyId] = 0;
                }
              })
            );
            setCompanyBalances(balances);
          } catch (err) {
            logger.error('Failed to reload company balances', err);
          }
        }
      } catch (err) {
        logger.error('Failed to reload supergroups after company creation', err);
      }
    };
    
    loadSupergroups();
  };

  const handleEditSuccess = async () => {
    logger.info('Company/group edited successfully, reloading data...', { component: 'GroupsPanel' });
    await handleCreateCompanySuccess(); // Reuse the same loading logic
    // Не закрываем модал редактирования - пользователь может продолжить редактирование
  };

  const handleEditGroup = async (supergroupId: number, companyId?: number) => {
    try {
      // Всегда загружаем данные супергруппы
      const supergroupData = await TelegramChatService.getSupergroupInfo(supergroupId);
      
      if (!supergroupData) {
        logger.error('Failed to load supergroup data', { supergroupId });
        return;
      }

      setPreloadedSupergroupData({
        id: supergroupData.id,
        title: supergroupData.title || '',
        description: supergroupData.description || '',
        username: supergroupData.username || '',
        invite_link: supergroupData.invite_link || '',
        member_count: supergroupData.member_count || 0,
        is_forum: supergroupData.is_forum || false,
        company_id: supergroupData.company_id || undefined,
        company_logo: supergroupData.company_logo || '',
        group_type: supergroupData.group_type || 'others'
      });

      // Если есть companyId, загружаем данные компании
      if (companyId) {
        const companyData = await CompanyService.getCompanyById(companyId);
        
        if (companyData) {
          setPreloadedCompanyData({
            id: companyData.id,
            vat: companyData.vat || '',
            kpp: companyData.kpp || '',
            ogrn: companyData.ogrn || '',
            company_name: companyData.name || '',
            email: companyData.email || '',
            phone: companyData.phone || '',
            street: companyData.street || '',
            city: companyData.city || '',
            postal_code: companyData.postal_code || '',
            country: companyData.country || '',
            director: companyData.director || '',
            company_type: companyData.company_type || 'company'
          });
        }
      } else {
        // Устанавливаем пустые данные компании для создания новой
        setPreloadedCompanyData({
          vat: '',
          kpp: '',
          ogrn: '',
          company_name: '',
          email: '',
          phone: '',
          street: '',
          city: '',
          postal_code: '',
          country: '',
          director: '',
          company_type: 'company'
        });
      }
      
      setEditingGroupId(supergroupId);
      setEditingCompanyId(companyId || 0);
    } catch (error) {
      logger.error('Failed to preload data', error);
      // Fallback к обычному открытию без предзагрузки
      setEditingGroupId(supergroupId);
      setEditingCompanyId(companyId || 0);
      setPreloadedCompanyData(null);
      setPreloadedSupergroupData(null);
    }
  };

  // Определяем текущий список групп и применяем фильтрацию
  const currentSupergroups = showArchived ? archivedSupergroups : activeSupergroups;
  const totalSupergroups = activeSupergroups.length + archivedSupergroups.length;
  
  // Определяем типы групп с иконками
  const groupTypes = [
    { type: 'client', icon: Users, label: 'Клиенты' },
    { type: 'payments', icon: DollarSign, label: 'Платежи' },
    { type: 'logistics', icon: Truck, label: 'Логисты' },
    { type: 'buyers', icon: ShoppingCart, label: 'Закупы' },
    { type: 'others', icon: Briefcase, label: 'Прочие' },
    { type: 'wellwon', icon: Building, label: 'WellWon' }
  ];
  
  const filteredSupergroups = useMemo(() => {
    let result = currentSupergroups;
    
    // Фильтр по поиску
    if (searchQuery.trim()) {
      result = result.filter(group => 
        group.title.toLowerCase().includes(searchQuery.toLowerCase())
      );
    }
    
    // Фильтр по типу группы
    if (selectedTypeFilter) {
      result = result.filter(group => group.group_type === selectedTypeFilter);
    }
    
    return result;
  }, [currentSupergroups, searchQuery, selectedTypeFilter]);

  // Функция архивирования/разархивирования
  const handleToggleArchive = async (supergroupId: number, currentIsActive: boolean) => {
    try {
      const newIsActive = !currentIsActive;
      
      await TelegramChatService.updateSupergroup(supergroupId, {
        is_active: newIsActive
      });

      // Перемещаем группу между списками
      if (currentIsActive) {
        // Архивируем: перемещаем из активных в архивные
        const groupToArchive = activeSupergroups.find(g => g.id === supergroupId);
        if (groupToArchive) {
          setActiveSupergroups(prev => prev.filter(g => g.id !== supergroupId));
          setArchivedSupergroups(prev => [...prev, { ...groupToArchive, is_active: false }]);
        }
      } else {
        // Разархивируем: перемещаем из архивных в активные
        const groupToRestore = archivedSupergroups.find(g => g.id === supergroupId);
        if (groupToRestore) {
          setArchivedSupergroups(prev => prev.filter(g => g.id !== supergroupId));
          setActiveSupergroups(prev => [...prev, { ...groupToRestore, is_active: true }]);
        }
      }

      logger.info('Supergroup archive status toggled', { 
        supergroupId, 
        newIsActive,
        component: 'GroupsPanel' 
      });
    } catch (error) {
      logger.error('Failed to toggle supergroup archive status', error, { 
        supergroupId,
        component: 'GroupsPanel' 
      });
    }
  };

  if (loading) {
    return (
      <div
        className={`h-full border-r ${theme.border} flex flex-col ${theme.bg}`}
        style={{ width: `${width}px` }}
      >
        {collapsed ? (
          <>
            {/* Заголовок с кнопкой разворачивания */}
            <div className={`h-16 border-b ${theme.border} flex items-center justify-center px-3`}>
              <Button
                size="icon"
                variant="ghost"
                onClick={onToggleGroups}
                className={`h-8 w-8 p-0 transition-colors ${theme.button.ghost}`}
              >
                <ChevronRight size={16} />
              </Button>
            </div>

        {/* Кнопка архива */}
        <div className={`h-16 border-b ${theme.border} flex items-center justify-center px-3`}>
          <Button
            size="icon"
            variant="ghost"
            className={`h-8 w-8 p-0 transition-colors ${theme.button.ghost}`}
          >
            <Archive size={14} />
          </Button>
        </div>

            {/* Загрузка групп */}
            <div className="flex items-center justify-center py-4">
              <span className={`text-sm ${theme.text.secondary}`}>Загрузка...</span>
            </div>
          </>
        ) : (
          <>
            {/* Заголовок */}
            <div className={`h-16 border-b ${theme.border} flex items-center justify-between pl-6 pr-4`}>
              <div>
                <h2 className={`font-semibold text-lg ${theme.text.primary}`}>Группы</h2>
                <p className={`text-xs ${theme.text.secondary}`}>
                  0 групп
                </p>
              </div>
              <div className="flex items-center gap-1">
                <Button
                  size="icon"
                  variant="ghost"
                  onClick={() => setIsCreateCompanyModalOpen(true)}
                  className={`h-8 w-8 p-0 transition-colors ${theme.button.ghost}`}
                  title="Создать компанию"
                >
                  <Plus size={16} />
                </Button>
                <Button
                  size="icon"
                  variant="ghost"
                  onClick={onToggleGroups}
                  className={`h-8 w-8 p-0 transition-colors ${theme.button.ghost}`}
                >
                  <ChevronLeft size={16} />
                </Button>
              </div>
            </div>

            <div className={`h-16 border-b ${theme.border} flex flex-col justify-center px-6`}>
              <span className={`text-sm ${theme.text.secondary}`}>Загрузка...</span>
            </div>

            <div className="flex-1">
              <ScrollArea className="h-full">
                <div className="flex items-center justify-center py-8">
                  <span className={`text-sm ${theme.text.secondary}`}>Загрузка групп...</span>
                </div>
              </ScrollArea>
            </div>
          </>
        )}
      </div>
    );
  }

  if (error) {
    return (
      <div
        className={`h-full border-r ${theme.border} flex flex-col items-center justify-center p-4 ${theme.bg}`}
        style={{ width: `${width}px` }}
      >
        {!collapsed && <p className="text-red-400 text-sm text-center">{error}</p>}
      </div>
    );
  }

  // Collapsed mini mode
  if (collapsed) {
    return (
      <div
        className={`h-full border-r ${theme.border} flex flex-col ${theme.bg}`}
        style={{ width: `${width}px` }}
      >
        {/* Заголовок с кнопкой разворачивания */}
        <div className={`h-16 border-b ${theme.border} flex items-center justify-center px-3 shrink-0`}>
          <Button
            size="icon"
            variant="ghost"
            onClick={onToggleGroups}
            className={`h-8 w-8 p-0 transition-colors ${theme.button.ghost}`}
          >
            <ChevronRight size={16} />
          </Button>
        </div>

        {/* Кнопка архива */}
        <div className={`h-16 border-t border-b ${theme.border} flex items-center justify-center px-3 shrink-0`}>
        <Button
          size="icon"
          variant="ghost"
          onClick={() => setShowArchived(!showArchived)}
          className={`h-8 w-8 p-0 transition-colors ${
            showArchived
              ? theme.button.active
              : theme.button.ghost
          }`}
          title={`Архив (${archivedSupergroups.length})`}
          aria-label={`${showArchived ? 'Скрыть' : 'Показать'} архив групп (${archivedSupergroups.length})`}
        >
          <Archive size={14} />
        </Button>
        </div>

        <div className="flex-1 flex flex-col items-center py-3 space-y-3">
          {filteredSupergroups.map((group) => (
            <div
              key={group.id}
                     onClick={() => {
                       onSelectGroup(group.id);
                       setScopeBySupergroup(group);
                     }}
              title={group.title}
              className={`
                ${selectedSupergroupId === group.id ? 'w-14 h-14' : 'w-12 h-12'}
                flex items-center justify-center rounded-md cursor-pointer overflow-hidden
                backdrop-blur-sm border transition-all duration-200
                ${selectedSupergroupId === group.id
                  ? 'bg-primary/20 border-primary/30 text-primary'
                  : isLightTheme
                    ? 'bg-gray-200 text-gray-600 border-gray-300 hover:text-gray-900 hover:bg-gray-300'
                    : 'bg-medium-gray/60 text-gray-400 border-white/10 hover:text-white hover:bg-medium-gray/80 hover:border-white/20'
                }
              `}
            >
              {group.company_logo ? (
                <OptimizedImage
                  src={group.company_logo}
                  alt={group.title || 'Company logo'}
                  className="w-full h-full object-cover"
                />
              ) : (
                <span className="font-medium text-sm">
                  {group.title.charAt(0).toUpperCase()}
                </span>
              )}
            </div>
          ))}
        </div>

        {/* Модальные окна - рендерятся и в collapsed режиме */}
        <AdminFormsModal
          isOpen={isCreateCompanyModalOpen}
          onClose={() => setIsCreateCompanyModalOpen(false)}
          formType="company-registration"
          onSuccess={handleCreateCompanySuccess}
        />

        {/* Кнопки типов групп внизу в 2 ряда */}
        <div className={`border-t ${theme.border} mt-auto p-2 min-h-24 flex items-center`}>
          <div className="grid grid-cols-3 gap-1 w-full">
            {groupTypes.map((groupType) => {
              const IconComponent = groupType.icon;
              return (
                <Button
                  key={groupType.type}
                  size="icon"
                  variant="ghost"
                  onClick={() => {
                    setSelectedTypeFilter(selectedTypeFilter === groupType.type ? null : groupType.type);
                  }}
                  className={`h-6 w-full p-0 text-xs transition-colors ${
                    selectedTypeFilter === groupType.type
                      ? theme.button.active
                      : theme.button.ghost
                  }`}
                  title={groupType.label}
                >
                  <IconComponent size={12} />
                </Button>
              );
            })}
          </div>
        </div>
        
        {editingGroupId && editingCompanyId && (
          <EditCompanyGroupModal
            isOpen={!!editingGroupId}
            onClose={() => {
              setEditingGroupId(null);
              setEditingCompanyId(null);
              setPreloadedCompanyData(null);
              setPreloadedSupergroupData(null);
            }}
            supergroupId={editingGroupId}
            companyId={editingCompanyId}
            onSuccess={handleEditSuccess}
            initialCompanyType={preloadedCompanyType}
            preloadedCompanyData={preloadedCompanyData}
            preloadedSupergroupData={preloadedSupergroupData}
          />
        )}
      </div>
    );
  }

  return (
    <div
      className={`h-full border-r ${theme.border} flex flex-col ${theme.bg}`}
      style={{ width: `${width}px` }}
    >
      {/* Заголовок - Все группы с кнопками */}
      <div className={`h-16 border-b ${theme.border} flex items-center justify-between pl-6 pr-4`}>
        <div>
          <h2 className={`font-semibold text-lg ${theme.text.primary}`}>Группы</h2>
          <p className={`text-xs ${theme.text.secondary}`}>
            {filteredSupergroups.length} групп{showArchived ? ' (архив)' : ''}
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Button
            size="icon"
            variant="ghost"
            onClick={onToggleGroups}
            className={`h-8 w-8 p-0 transition-colors ${theme.button.ghost}`}
          >
            <ChevronLeft size={16} />
          </Button>
          <Button
            size="icon"
            onClick={() => setIsCreateCompanyModalOpen(true)}
            className="bg-accent-red hover:bg-accent-red/90 hover:scale-105 text-white rounded-lg h-8 w-8"
          >
            <Plus size={14} />
          </Button>
        </div>
      </div>

      {/* Панель поиска и фильтров */}
      <div className={`h-16 px-4 border-b ${theme.border} flex flex-col justify-center space-y-1`}>
        {/* Строка поиска с кнопками справа */}
        <div className="flex items-center gap-3">
          <div className="relative flex-1">
            <Search className={`absolute left-3 top-1/2 transform -translate-y-1/2 h-4 w-4 ${theme.text.secondary}`} />
            <Input
              placeholder="Поиск групп..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className={`pl-10 ${theme.input} focus:border-primary/50`}
            />
          </div>

          {/* Кнопки фильтров справа */}
          <div className="flex items-center gap-2">
            <Button
              size="icon"
              variant="ghost"
              onClick={() => setShowArchived(!showArchived)}
              className={`h-8 w-8 transition-colors ${
                showArchived
                  ? theme.button.active
                  : theme.button.ghost
              }`}
              title={`Архив (${archivedSupergroups.length})`}
            >
              <Archive size={14} />
            </Button>
            <Button
              size="icon"
              variant="ghost"
              className={`h-8 w-8 ${theme.button.ghost}`}
              title="Фильтры"
            >
              <Filter size={14} />
            </Button>
          </div>
        </div>

      </div>

      {/* Список групп */}
      <ScrollArea className="flex-1">
        <div className="px-4 pt-3 pb-3 space-y-3">
          {filteredSupergroups.length === 0 ? (
            <div className="text-center py-12">
              <Users size={32} className={`mx-auto mb-3 ${theme.text.muted}`} />
              <p className={`text-sm ${theme.text.secondary}`}>
                {searchQuery ? 'Группы не найдены' : 'Нет групп'}
              </p>
            </div>
          ) : (
            filteredSupergroups.map((group) => {
              const isExpanded = expandedGroupId === group.id;
              const companyBalance = group.company_id ? companyBalances[group.company_id] : null;

              return (
                <div
                  key={group.id}
                  className={`
                    border rounded-lg overflow-hidden
                    ${selectedSupergroupId === group.id
                      ? isLightTheme
                        ? 'bg-gray-100 border-gray-300'
                        : 'bg-white/5 border-white/15'
                      : isLightTheme
                        ? 'bg-white border-gray-200 hover:bg-gray-50 hover:border-gray-300'
                        : 'bg-[#2e2e33] border-white/10 hover:bg-[#3a3a40] hover:border-white/20'
                    }
                    ${isExpanded ? 'pb-4' : ''}
                  `}
                >
                  <div
                    role="button"
                    tabIndex={0}
                     onClick={() => {
                       onSelectGroup(group.id);
                       setScopeBySupergroup(group);
                       setExpandedGroupId(isExpanded ? null : group.id);
                     }}
                    onKeyDown={(e) => {
                      if (e.key === 'Enter' || e.key === ' ') {
                        e.preventDefault();
                        onSelectGroup(group.id);
                        setExpandedGroupId(isExpanded ? null : group.id);
                      }
                    }}
                    className={`w-full px-3 py-2.5 cursor-pointer transition-colors rounded-lg ${
                      selectedSupergroupId === group.id
                        ? isLightTheme ? 'text-gray-900 bg-gray-100' : 'text-white bg-white/5'
                        : isLightTheme ? 'text-gray-700 hover:bg-gray-50 hover:text-gray-900' : 'text-gray-300 hover:bg-white/10 hover:text-white'
                    }`}
                  >
                    <div className="flex items-center gap-3 w-full">
                      {/* Иконка группы */}
                      <div className={`flex-shrink-0 w-10 h-10 rounded-md flex items-center justify-center overflow-hidden ${isLightTheme ? 'bg-gray-100' : 'bg-primary/20'}`}>
                        {group.company_logo ? (
                          <OptimizedImage
                            src={group.company_logo}
                            alt={group.title || 'Company logo'}
                            className="w-full h-full object-cover"
                          />
                        ) : (
                          <span className="text-primary font-medium text-sm">
                            {group.title.charAt(0).toUpperCase()}
                          </span>
                        )}
                      </div>

                      {/* Информация о группе */}
                      <div className="flex-1 min-w-0 text-left">
                         <div className="flex items-center justify-between mb-1">
                           <p className={`font-medium text-sm ${isExpanded ? 'whitespace-normal break-words' : 'truncate'}`}>
                             {group.title}
                           </p>
                            <div className="flex items-center gap-2 ml-2">
                              {chatCounts[group.id] && (
                                <Badge
                                  variant="secondary"
                                  className={isLightTheme ? 'bg-gray-100 text-gray-700 text-xs border-gray-300' : 'bg-white/10 text-white text-xs border-white/20'}
                                >
                                  {chatCounts[group.id]}
                                </Badge>
                              )}
                            </div>
                         </div>
                        <div className={`flex items-center gap-2 text-xs ${theme.text.secondary}`}>
                          <Users size={12} />
                          <span>{group.member_count}</span>
                          {!group.company_id && (
                            <div className="flex items-center gap-1 text-red-400" title="Компания не привязана">
                              <Building size={12} />
                              <span className="text-xs">Нет компании</span>
                            </div>
                          )}
                          {group.is_forum && (
                            <Badge variant="outline" className={`text-xs ${isLightTheme ? 'border-gray-300 text-gray-500' : 'border-white/20 text-gray-400'}`}>
                              Форум
                            </Badge>
                          )}
                        </div>
                      </div>
                    </div>
                  </div>
                  
                  {/* Расширенная информация */}
                  {isExpanded && (
                    <div className="px-3 pt-2 space-y-2">
                      {/* Баланс компании */}
                      {group.company_id && (
                        <div className={`flex items-center justify-between px-3 py-2 rounded-lg ${isLightTheme ? 'bg-gray-100' : 'bg-white/5'}`}>
                          <span className={`text-xs ${theme.text.secondary}`}>Баланс компании:</span>
                          <span className={`text-sm font-medium ${theme.text.primary}`}>
                            {companyBalance !== null
                              ? `${companyBalance.toLocaleString('ru-RU')} ₽`
                              : 'Загрузка...'
                            }
                          </span>
                        </div>
                      )}

                        {/* ID группы и кнопки */}
                        <div className="flex items-center gap-2">
                          <div className={`px-3 py-2 rounded-lg w-3/5 ${isLightTheme ? 'bg-gray-100' : 'bg-white/5'}`}>
                            <div className="flex items-center gap-2">
                              <span className={`text-xs ${theme.text.secondary}`}>ID:</span>
                              <span className={`text-xs ${isLightTheme ? 'text-gray-700' : 'text-gray-300'}`}>{group.id}</span>
                            </div>
                          </div>
                          <div className="flex items-center gap-2 w-2/5 justify-end">
                            <Button
                              size="sm"
                              variant="ghost"
                              onClick={(e) => {
                                e.stopPropagation();
                                setArchiveConfirmOpen(group.id);
                              }}
                              className={`h-6 w-6 p-0 ${theme.button.ghost}`}
                              title={group.is_active ? "Архивировать группу" : "Разархивировать группу"}
                            >
                              <Archive size={12} />
                            </Button>
                            <Button
                              size="sm"
                              variant="ghost"
                              onClick={(e) => {
                                e.stopPropagation();
                                handleEditGroup(group.id, group.company_id);
                              }}
                              className={`h-6 w-6 p-0 ${theme.button.ghost}`}
                              title="Редактировать"
                            >
                              <Edit3 size={12} />
                            </Button>
                          </div>
                        </div>

                        {/* Дополнительная информация */}
                        {group.username && (
                          <div className={`px-3 py-2 rounded-lg ${isLightTheme ? 'bg-gray-100' : 'bg-white/5'}`}>
                            <div className="flex items-center justify-between">
                              <span className={`text-xs ${theme.text.secondary}`}>Username:</span>
                              <span className={`text-xs ${isLightTheme ? 'text-gray-700' : 'text-gray-300'}`}>@{group.username}</span>
                            </div>
                          </div>
                        )}
                     </div>
                   )}
                </div>
              );
            })
          )}
        </div>
      </ScrollArea>

      {/* Диалог подтверждения архивации */}
      {archiveConfirmOpen && (
        <AppConfirmDialog
          open={!!archiveConfirmOpen}
          onOpenChange={(open) => !open && setArchiveConfirmOpen(null)}
          onConfirm={() => {
            const group = filteredSupergroups.find(g => g.id === archiveConfirmOpen);
            if (group) {
              handleToggleArchive(group.id, group.is_active);
            }
            setArchiveConfirmOpen(null);
          }}
          title={(() => {
            const group = filteredSupergroups.find(g => g.id === archiveConfirmOpen);
            return group?.is_active ? "Отправить в архив?" : "Разархивировать группу?";
          })()}
          description={(() => {
            const group = filteredSupergroups.find(g => g.id === archiveConfirmOpen);
            return group?.is_active
              ? "Группа будет перемещена в архив и скрыта из основного списка."
              : "Группа будет восстановлена из архива и появится в основном списке.";
          })()}
          confirmText={(() => {
            const group = filteredSupergroups.find(g => g.id === archiveConfirmOpen);
            return group?.is_active ? "Архивировать" : "Разархивировать";
          })()}
          variant="default"
          icon={Archive}
        />
      )}

      {/* Кнопки типов групп внизу */}
      <div className={`min-h-24 border-t ${theme.border} mt-auto px-4 py-3 shrink-0`}>
        <div className="grid grid-cols-3 gap-2">
          {groupTypes.map((groupType) => {
            const IconComponent = groupType.icon;
            return (
              <Button
                key={groupType.type}
                size="sm"
                variant="ghost"
                onClick={() => {
                  setSelectedTypeFilter(selectedTypeFilter === groupType.type ? null : groupType.type);
                }}
                className={`h-8 px-2 text-xs transition-colors flex items-center gap-1 ${
                  selectedTypeFilter === groupType.type
                    ? theme.button.active
                    : theme.button.ghost
                }`}
                title={groupType.label}
              >
                <IconComponent size={14} />
                <span className="truncate">{groupType.label}</span>
              </Button>
            );
          })}
        </div>
      </div>

      {/* Модальные окна */}
      <AdminFormsModal
        isOpen={isCreateCompanyModalOpen}
        onClose={() => setIsCreateCompanyModalOpen(false)}
        formType="company-registration"
        onSuccess={handleCreateCompanySuccess}
      />

        {editingGroupId && (
        <EditCompanyGroupModal
          isOpen={!!editingGroupId}
          onClose={() => {
            setEditingGroupId(null);
            setEditingCompanyId(null);
            setPreloadedCompanyData(null);
            setPreloadedSupergroupData(null);
          }}
          supergroupId={editingGroupId}
          companyId={editingCompanyId}
          onSuccess={handleEditSuccess}
          initialCompanyType={preloadedCompanyType}
          preloadedCompanyData={preloadedCompanyData}
          preloadedSupergroupData={preloadedSupergroupData}
        />
      )}
    </div>
  );
};
