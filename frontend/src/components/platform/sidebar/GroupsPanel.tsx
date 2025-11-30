
import React, { useState, useMemo } from 'react';
import * as telegramApi from '@/api/telegram';
import * as companyApi from '@/api/company';
import { useRealtimeChatContext } from '@/contexts/RealtimeChatContext';
import { useAuth } from '@/contexts/AuthContext';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { GlassButton } from '@/components/design-system';
import { OptimizedImage } from '@/components/chat/components/OptimizedImage';
import { Users, ChevronLeft, ChevronRight, Search, Archive, Filter, Edit3, Building, Plus, Briefcase, DollarSign, Truck, Package, ShoppingCart, Layers, Settings, Trash2 } from 'lucide-react';
import { logger } from '@/utils/logger';
import { AdminFormsModal } from '@/components/chat/components/AdminFormsModal';
import { EditCompanyGroupModal } from '@/components/chat/components/EditCompanyGroupModal';
import AppConfirmDialog from '@/components/shared/AppConfirmDialog';
import DeleteGroupDialog from './DeleteGroupDialog';
import type { TelegramSupergroup } from '@/types/chat';
import type { CompanyFormData, SupergroupFormData } from '@/types/company-form';
import { useSupergroups, useInvalidateSupergroups } from '@/hooks/useSupergroups';

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
  const { profile } = useAuth();

  // Check if user is admin - only admins can delete, regular users can only archive
  // role = 'admin' | 'user' - for permissions
  // user_type = employee type - for UI layouts
  const isAdmin = profile?.role === 'admin';

  // React Query hook - replaces useState + useEffect + manual WSE listeners
  // TkDodo Pattern: WSE events invalidate cache, React Query refetches automatically
  const {
    activeSupergroups,
    archivedSupergroups,
    chatCounts,
    companyBalances,
    isLoading: loading,
    isError,
    refetch: loadSupergroups,
  } = useSupergroups();

  const invalidateSupergroups = useInvalidateSupergroups();

  // Local UI state (not data state)
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
  const [deleteConfirmGroup, setDeleteConfirmGroup] = useState<TelegramSupergroup | null>(null);
  const [selectedTypeFilter, setSelectedTypeFilter] = useState<string | null>(null);

  const handleCreateCompanySuccess = () => {
    // React Query will auto-refetch via WSE event invalidation
    // This is just for immediate feedback if needed
    invalidateSupergroups();
  };

  const handleEditSuccess = async () => {
    logger.info('Company/group edited successfully, reloading data...', { component: 'GroupsPanel' });
    await handleCreateCompanySuccess(); // Reuse the same loading logic
    // Не закрываем модал редактирования - пользователь может продолжить редактирование
  };

  const handleEditGroup = async (supergroupId: number, companyId?: number) => {
    try {
      // Всегда загружаем данные супергруппы
      const supergroupData = await telegramApi.getGroupInfo(supergroupId);
      
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
        const companyData = await companyApi.getCompanyById(String(companyId));
        
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
  // Pattern: Mutate then invalidate - React Query will refetch
  const handleToggleArchive = async (supergroupId: number, currentIsActive: boolean) => {
    try {
      const newIsActive = !currentIsActive;

      await telegramApi.updateSupergroup(supergroupId, {
        is_active: newIsActive
      });

      // Invalidate React Query cache - it will refetch automatically
      // No manual state manipulation needed - React Query handles it
      invalidateSupergroups();

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

  // Функция удаления супергруппы (только группа, без компании)
  const handleDeleteSupergroupOnly = async (supergroupId: number) => {
    const success = await telegramApi.deleteSupergroup(supergroupId);

    if (success) {
      // Clear selection if deleted group was selected
      if (selectedSupergroupId === supergroupId) {
        onSelectGroup(null);
      }

      // Invalidate React Query cache
      invalidateSupergroups();

      logger.info('Supergroup deleted (group only)', {
        supergroupId,
        component: 'GroupsPanel'
      });
    } else {
      throw new Error('Failed to delete supergroup');
    }
  };

  // Функция удаления всего (компания + чаты + telegram группа)
  const handleDeleteAll = async (group: TelegramSupergroup) => {
    if (!group.company_id) {
      // No company - just delete the group
      await handleDeleteSupergroupOnly(group.id);
      return;
    }

    // Delete company with cascade (this triggers GroupDeletionSaga)
    await companyApi.deleteCompany(String(group.company_id), {
      cascade: true,
      preserveCompany: false,
    });

    // Clear selection if deleted group was selected
    if (selectedSupergroupId === group.id) {
      onSelectGroup(null);
    }

    // Invalidate React Query cache
    invalidateSupergroups();

    logger.info('Company and supergroup deleted', {
      supergroupId: group.id,
      companyId: group.company_id,
      component: 'GroupsPanel'
    });
  };

  // Функция удаления с сохранением компании (для будущей привязки)
  const handleDeletePreserveCompany = async (group: TelegramSupergroup) => {
    if (!group.company_id) {
      // No company - just delete the group
      await handleDeleteSupergroupOnly(group.id);
      return;
    }

    // Delete with preserve_company=true (keeps company record)
    await companyApi.deleteCompany(String(group.company_id), {
      cascade: true,
      preserveCompany: true,
    });

    // Clear selection if deleted group was selected
    if (selectedSupergroupId === group.id) {
      onSelectGroup(null);
    }

    // Invalidate React Query cache
    invalidateSupergroups();

    logger.info('Supergroup deleted, company preserved', {
      supergroupId: group.id,
      companyId: group.company_id,
      component: 'GroupsPanel'
    });
  };

  if (loading) {
    return (
      <div
        className="h-full border-r border-white/10 flex flex-col"
        style={{ width: `${width}px`, backgroundColor: '#232328' }}
      >
        {collapsed ? (
          <>
            {/* Заголовок с кнопкой разворачивания */}
            <div className="h-16 border-b border-white/10 flex items-center justify-center px-3">
              <Button
                size="icon"
                variant="ghost"
                onClick={onToggleGroups}
                className="h-8 w-8 p-0 hover:bg-white/10 text-gray-300 hover:text-white transition-colors"
              >
                <ChevronRight size={16} />
              </Button>
            </div>

            {/* Кнопка архива */}
            <div className="h-16 border-t border-b border-white/10 flex items-center justify-center px-3">
              <Button
                size="icon"
                variant="ghost"
                className="h-8 w-8 p-0 hover:bg-white/10 text-gray-300 hover:text-white transition-colors"
              >
                <Archive size={14} />
              </Button>
            </div>

            {/* Загрузка групп - skeleton */}
            <div className="flex-1 flex flex-col items-center py-3 space-y-3">
              {[1, 2, 3].map((i) => (
                <div
                  key={i}
                  className="w-12 h-12 rounded-md bg-white/10 animate-pulse"
                />
              ))}
            </div>
          </>
        ) : (
          <>
            {/* Заголовок - показываем все controls */}
            <div className="h-16 border-b border-white/10 flex items-center justify-between pl-6 pr-4">
              <div className="text-white">
                <h2 className="font-semibold text-lg">Группы</h2>
                <p className="text-xs text-gray-400">
                  Загрузка...
                </p>
              </div>
              <div className="flex items-center gap-2">
                <Button
                  size="icon"
                  variant="ghost"
                  onClick={onToggleGroups}
                  className="h-8 w-8 p-0 hover:bg-white/10 text-gray-300 hover:text-white transition-colors"
                >
                  <ChevronLeft size={16} />
                </Button>
                <Button
                  size="icon"
                  onClick={() => setIsCreateCompanyModalOpen(true)}
                  className="bg-accent-red hover:bg-accent-red/90 text-white rounded-lg h-8 w-8"
                >
                  <Plus size={14} />
                </Button>
              </div>
            </div>

            {/* Панель поиска и фильтров - показываем во время загрузки */}
            <div className="h-16 px-4 border-b border-white/10 flex flex-col justify-center space-y-1">
              <div className="flex items-center gap-3">
                <div className="relative flex-1">
                  <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 h-4 w-4 text-gray-400" />
                  <Input
                    placeholder="Поиск групп..."
                    disabled
                    className="pl-10 bg-white/5 border-white/10 text-white placeholder:!text-[#9da3af] focus:border-white/20 opacity-50"
                  />
                </div>

                <div className="flex items-center gap-2">
                  <Button
                    size="icon"
                    variant="ghost"
                    disabled
                    className="h-8 w-8 text-gray-400 opacity-50"
                    title="Архив"
                  >
                    <Archive size={14} />
                  </Button>
                  <Button
                    size="icon"
                    variant="ghost"
                    disabled
                    className="h-8 w-8 text-gray-400 opacity-50"
                    title="Фильтры"
                  >
                    <Filter size={14} />
                  </Button>
                </div>
              </div>
            </div>

            {/* Skeleton список групп */}
            <div className="flex-1">
              <ScrollArea className="h-full">
                <div className="px-4 pt-3 pb-3 space-y-3">
                  {[1, 2, 3, 4].map((i) => (
                    <div
                      key={i}
                      className="border rounded-lg overflow-hidden bg-[#2e2e33] border-white/10 p-3"
                    >
                      <div className="flex items-center gap-3">
                        <div className="w-10 h-10 rounded-md bg-white/10 animate-pulse" />
                        <div className="flex-1 space-y-2">
                          <div className="h-4 bg-white/10 rounded animate-pulse w-3/4" />
                          <div className="h-3 bg-white/10 rounded animate-pulse w-1/2" />
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              </ScrollArea>
            </div>

            {/* Кнопки типов групп внизу */}
            <div className="min-h-24 border-t border-white/10 mt-auto px-4 py-3 shrink-0">
              <div className="grid grid-cols-3 gap-2">
                {groupTypes.map((groupType) => {
                  const IconComponent = groupType.icon;
                  return (
                    <Button
                      key={groupType.type}
                      size="sm"
                      variant="ghost"
                      disabled
                      className="h-8 px-2 text-xs text-gray-300 opacity-50 flex items-center gap-1"
                    >
                      <IconComponent size={14} />
                      <span className="truncate">{groupType.label}</span>
                    </Button>
                  );
                })}
              </div>
            </div>
          </>
        )}

        {/* Модальные окна доступны во время загрузки */}
        <AdminFormsModal
          isOpen={isCreateCompanyModalOpen}
          onClose={() => setIsCreateCompanyModalOpen(false)}
          formType="company-registration"
          onSuccess={handleCreateCompanySuccess}
        />
      </div>
    );
  }

  if (isError) {
    return (
      <div
        className="h-full border-r border-white/10 flex flex-col items-center justify-center p-4"
        style={{ width: `${width}px`, backgroundColor: '#232328' }}
      >
        {!collapsed && <p className="text-red-400 text-sm text-center">Failed to load groups</p>}
      </div>
    );
  }

  // Collapsed mini mode
  if (collapsed) {
    return (
      <div 
        className="h-full border-r border-white/10 flex flex-col"
        style={{ width: `${width}px`, backgroundColor: '#232328' }}
      >
        {/* Заголовок с кнопкой разворачивания */}
        <div className="h-16 border-b border-white/10 flex items-center justify-center px-3 shrink-0">
          <Button
            size="icon"
            variant="ghost"
            onClick={onToggleGroups}
            className="h-8 w-8 p-0 hover:bg-white/10 text-gray-300 hover:text-white transition-colors"
          >
            <ChevronRight size={16} />
          </Button>
        </div>
        
        {/* Кнопка архива */}
        <div className="h-16 border-t border-b border-white/10 flex items-center justify-center px-3 shrink-0">
        <Button
          size="icon"
          variant="ghost"
          onClick={() => setShowArchived(!showArchived)}
          className={`h-8 w-8 p-0 transition-colors ${
            showArchived 
              ? 'text-accent-red border border-accent-red/60 bg-accent-red/10 hover:bg-accent-red/20' 
              : 'text-gray-300 hover:text-white hover:bg-white/10'
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
        <div className="border-t border-white/10 mt-auto p-2 min-h-24 flex items-center">
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
                      ? 'text-accent-red border border-accent-red/60 bg-accent-red/10 hover:bg-accent-red/20' 
                      : 'text-gray-300 hover:text-white hover:bg-white/10'
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
      className="h-full border-r border-white/10 flex flex-col"
      style={{ width: `${width}px`, backgroundColor: '#232328' }}
    >
      {/* Заголовок - Все группы с кнопками */}
      <div className="h-16 border-b border-white/10 flex items-center justify-between pl-6 pr-4">
        <div className="text-white">
          <h2 className="font-semibold text-lg">Группы</h2>
          <p className="text-xs text-gray-400">
            {filteredSupergroups.length} групп{showArchived ? ' (архив)' : ''}
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Button
            size="icon"
            variant="ghost"
            onClick={onToggleGroups}
            className="h-8 w-8 p-0 hover:bg-white/10 text-gray-300 hover:text-white transition-colors"
          >
            <ChevronLeft size={16} />
          </Button>
          <Button
            size="icon"
            onClick={() => setIsCreateCompanyModalOpen(true)}
            className="bg-accent-red hover:bg-accent-red/90 text-white rounded-lg h-8 w-8"
          >
            <Plus size={14} />
          </Button>
        </div>
      </div>

      {/* Панель поиска и фильтров */}
      <div className="h-16 px-4 border-b border-white/10 flex flex-col justify-center space-y-1">
        {/* Строка поиска с кнопками справа */}
        <div className="flex items-center gap-3">
          <div className="relative flex-1">
            <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 h-4 w-4 text-gray-400" />
            <Input
              placeholder="Поиск групп..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="pl-10 bg-white/5 border-white/10 text-white placeholder:!text-[#9da3af] focus:border-white/20"
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
                  ? 'text-accent-red border border-accent-red/60 bg-accent-red/10 hover:bg-accent-red/20' 
                  : 'text-gray-400 hover:text-white hover:bg-white/10'
              }`}
              title={`Архив (${archivedSupergroups.length})`}
            >
              <Archive size={14} />
            </Button>
            <Button
              size="icon"
              variant="ghost"
              className="h-8 w-8 text-gray-400 hover:text-white hover:bg-white/10"
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
              <Users size={32} className="mx-auto text-gray-500 mb-3" />
              <p className="text-gray-400 text-sm">
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
                      ? 'bg-white/5 border-white/15'
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
                        ? 'text-white bg-white/5'
                        : 'text-gray-300 hover:bg-white/10 hover:text-white'
                    }`}
                  >
                    <div className="flex items-center gap-3 w-full">
                      {/* Иконка группы */}
                      <div className="flex-shrink-0 w-10 h-10 bg-primary/20 rounded-md flex items-center justify-center overflow-hidden">
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
                                  className="bg-white/10 text-white text-xs border-white/20"
                                >
                                  {chatCounts[group.id]}
                                </Badge>
                              )}
                            </div>
                         </div>
                        <div className="flex items-center gap-2 text-xs text-gray-400">
                          <Users size={12} />
                          <span>{group.member_count}</span>
                          {!group.company_id && (
                            <div className="flex items-center gap-1 text-red-400" title="Компания не привязана">
                              <Building size={12} />
                              <span className="text-xs">Нет компании</span>
                            </div>
                          )}
                          {group.is_forum && (
                            <Badge variant="outline" className="text-xs border-white/20 text-gray-400">
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
                        <div className="flex items-center justify-between px-3 py-2 bg-white/5 rounded-lg">
                          <span className="text-xs text-gray-400">Баланс компании:</span>
                          <span className="text-sm font-medium text-white">
                            {companyBalance != null
                              ? `${companyBalance.toLocaleString('ru-RU')} ₽`
                              : 'Загрузка...'
                            }
                          </span>
                        </div>
                      )}
                      
                        {/* ID группы и кнопки */}
                        <div className="flex items-center gap-2">
                          <div className="px-3 py-2 bg-white/5 rounded-lg w-3/5">
                            <div className="flex items-center gap-2">
                              <span className="text-xs text-gray-400">ID:</span>
                              <span className="text-xs text-gray-300">{group.id}</span>
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
                              className="h-6 w-6 p-0 text-gray-400 hover:text-white hover:bg-white/10"
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
                              className="h-6 w-6 p-0 text-gray-400 hover:text-white hover:bg-white/10"
                              title="Редактировать"
                            >
                              <Edit3 size={12} />
                            </Button>
                            {/* Delete button - only for admin users */}
                            {isAdmin && (
                              <Button
                                size="sm"
                                variant="ghost"
                                onClick={(e) => {
                                  e.stopPropagation();
                                  setDeleteConfirmGroup(group);
                                }}
                                className="h-6 w-6 p-0 text-gray-400 hover:text-red-400 hover:bg-red-500/10"
                                title="Удалить группу"
                              >
                                <Trash2 size={12} />
                              </Button>
                            )}
                          </div>
                        </div>
                        
                        {/* Дополнительная информация */}
                        {group.username && (
                          <div className="px-3 py-2 bg-white/5 rounded-lg">
                            <div className="flex items-center justify-between">
                              <span className="text-xs text-gray-400">Username:</span>
                              <span className="text-xs text-gray-300">@{group.username}</span>
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

      {/* Диалог подтверждения удаления - с опциями */}
      {deleteConfirmGroup && (
        <DeleteGroupDialog
          open={!!deleteConfirmGroup}
          onOpenChange={(open) => !open && setDeleteConfirmGroup(null)}
          groupTitle={deleteConfirmGroup.title}
          companyId={deleteConfirmGroup.company_id}
          companyName={deleteConfirmGroup.title}
          onDeleteAll={async () => {
            await handleDeleteAll(deleteConfirmGroup);
            setDeleteConfirmGroup(null);
          }}
          onPreserveCompany={async () => {
            await handleDeletePreserveCompany(deleteConfirmGroup);
            setDeleteConfirmGroup(null);
          }}
          onDeleteGroupOnly={async () => {
            await handleDeleteSupergroupOnly(deleteConfirmGroup.id);
            setDeleteConfirmGroup(null);
          }}
        />
      )}

      {/* Кнопки типов групп внизу */}
      <div className="min-h-24 border-t border-white/10 mt-auto px-4 py-3 shrink-0">
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
                    ? 'text-accent-red border border-accent-red/60 bg-accent-red/10 hover:bg-accent-red/20' 
                    : 'text-gray-300 hover:text-white hover:bg-white/10'
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
