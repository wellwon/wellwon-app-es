import { useState, useCallback, useMemo, useRef } from 'react';
import { TelegramChatService } from '@/services/TelegramChatService';
import { supabase } from '@/integrations/supabase/client';
import { logger } from '@/utils/logger';

interface MentionCandidate {
  id: string;
  name: string;
  username: string;
  roleLabel?: string;
  avatarUrl?: string;
  group: 'manager' | 'telegram';
}

interface UseMentionsProps {
  activeChat?: any;
}

interface UseMentionsReturn {
  items: MentionCandidate[];
  isLoading: boolean;
  error: string | null;
  fetchIfNeeded: () => Promise<void>;
  filter: (query: string) => MentionCandidate[];
}

export function useMentions({ activeChat }: UseMentionsProps): UseMentionsReturn {
  const [items, setItems] = useState<MentionCandidate[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  
  const cacheRef = useRef<{
    chatId: string | null;
    timestamp: number;
    items: MentionCandidate[];
  }>({
    chatId: null,
    timestamp: 0,
    items: []
  });

  const isValidCache = useCallback((chatId: string | null): boolean => {
    const cache = cacheRef.current;
    const maxAge = 5 * 60 * 1000; // 5 минут
    return (
      cache.chatId === chatId &&
      Date.now() - cache.timestamp < maxAge
    );
  }, []);

  const loadMentionCandidates = useCallback(async (): Promise<MentionCandidate[]> => {
    if (!activeChat?.telegram_supergroup_id) {
      return [];
    }

    const candidates: MentionCandidate[] = [];

    try {
      // 1. Получаем telegram пользователей супергруппы
      const members = await TelegramChatService.getSupergroupMembers(activeChat.telegram_supergroup_id);
      const nonBotMembers = members.filter(m => !m.is_bot && m.username);

      if (nonBotMembers.length > 0) {
        const tgUserIds = nonBotMembers.map(m => m.telegram_user_id);
        const tgUsers = await TelegramChatService.getTgUsersByIds(tgUserIds);

        nonBotMembers.forEach(member => {
          if (member.username) {
            const userData = tgUsers.find(user => user.id === member.telegram_user_id);
            const name = [member.first_name, member.last_name].filter(Boolean).join(' ') || 'Пользователь';
            
            candidates.push({
              id: `tg-${member.telegram_user_id}`,
              name,
              username: member.username,
              roleLabel: userData?.role_label || undefined,
              group: 'telegram'
            });
          }
        });
      }

      // 2. Получаем менеджеров компании с telegram username
      const { data: profiles, error: profilesError } = await supabase
        .from('profiles')
        .select('user_id, first_name, last_name, avatar_url, role_label, telegram_user_id')
        .eq('active', true)
        .not('telegram_user_id', 'is', null);

      if (profilesError) {
        logger.error('Failed to load profiles for mentions', profilesError, { component: 'useMentions' });
      } else if (profiles && profiles.length > 0) {
        const managerTgIds = profiles.map(p => p.telegram_user_id).filter(Boolean);
        
        if (managerTgIds.length > 0) {
          const managerTgUsers = await TelegramChatService.getTgUsersByIds(managerTgIds);

          profiles.forEach(profile => {
            const tgUser = managerTgUsers.find(tg => tg.id === profile.telegram_user_id);
            if (tgUser?.username) {
              const name = [profile.first_name, profile.last_name].filter(Boolean).join(' ') || 'Менеджер';
              
              candidates.push({
                id: `mgr-${profile.user_id}`,
                name,
                username: tgUser.username,
                roleLabel: profile.role_label || 'Менеджер',
                avatarUrl: profile.avatar_url || undefined,
                group: 'manager'
              });
            }
          });
        }
      }

      // Сортируем: сначала менеджеры, потом telegram пользователи
      candidates.sort((a, b) => {
        if (a.group !== b.group) {
          return a.group === 'manager' ? -1 : 1;
        }
        return a.name.localeCompare(b.name);
      });

      return candidates;
    } catch (error) {
      logger.error('Failed to load mention candidates', error, { 
        component: 'useMentions', 
        chatId: activeChat?.id 
      });
      throw error;
    }
  }, [activeChat?.telegram_supergroup_id, activeChat?.id]);

  const fetchIfNeeded = useCallback(async (): Promise<void> => {
    const chatId = activeChat?.id || null;
    
    if (isValidCache(chatId)) {
      setItems(cacheRef.current.items);
      return;
    }

    setIsLoading(true);
    setError(null);

    try {
      const candidates = await loadMentionCandidates();
      
      // Обновляем кэш
      cacheRef.current = {
        chatId,
        timestamp: Date.now(),
        items: candidates
      };
      
      setItems(candidates);
    } catch (err) {
      const errorMsg = err instanceof Error ? err.message : 'Не удалось загрузить список пользователей';
      setError(errorMsg);
      setItems([]);
    } finally {
      setIsLoading(false);
    }
  }, [activeChat?.id, isValidCache, loadMentionCandidates]);

  const filter = useCallback((query: string): MentionCandidate[] => {
    if (!query.trim()) {
      return items;
    }

    const lowerQuery = query.toLowerCase();
    return items.filter(item => 
      item.username.toLowerCase().includes(lowerQuery) ||
      item.name.toLowerCase().includes(lowerQuery) ||
      (item.roleLabel && item.roleLabel.toLowerCase().includes(lowerQuery))
    );
  }, [items]);

  const filteredItems = useMemo(() => filter(''), [filter]);

  return {
    items: filteredItems,
    isLoading,
    error,
    fetchIfNeeded,
    filter
  };
}