import React, { useState, useEffect } from 'react';
import { Badge } from '@/components/ui/badge';
import { supabase } from '@/integrations/supabase/client';
import { logger } from '@/utils/logger';
import type { Company } from '@/types/realtime-chat';

interface CompanyBadgeProps {
  chatId: string;
}

const getCompanyStatusColor = (status: string | undefined) => {
  switch (status) {
    case 'new':
      // white
      return 'bg-white/20 text-white border-white/30';
    case 'bronze':
      return 'bg-amber-700/20 text-amber-300 border-amber-600/30';
    case 'silver':
      return 'bg-slate-300/20 text-slate-200 border-slate-300/30';
    case 'gold':
      return 'bg-yellow-500/20 text-yellow-300 border-yellow-500/30';
    default:
      return 'bg-white/10 text-white/80 border-white/20';
  }
};

const CompanyBadge: React.FC<CompanyBadgeProps> = ({ chatId }) => {
  const [company, setCompany] = useState<Company | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    const fetchCompany = async () => {
      setIsLoading(true);
      try {
        // Get company directly from chat's company_id using the new function
        const { data, error } = await supabase.rpc('get_client_company_from_chat', {
          chat_uuid: chatId
        });

        if (error) {
          logger.error('Error loading company for chat', error, { component: 'CompanyBadge' });
          setCompany(null);
        } else if (data && data.length > 0) {
          setCompany(data[0] as Company);
        } else {
          setCompany(null);
        }
      } catch (error) {
        logger.error('Error loading company for badge', error, { component: 'CompanyBadge' });
        setCompany(null);
      } finally {
        setIsLoading(false);
      }
    };

    if (chatId) {
      fetchCompany();
    }
  }, [chatId]);

  // Realtime: refetch when chat.company_id changes
  useEffect(() => {
    if (!chatId) return;
    const channel = supabase
      .channel(`company-badge-chat-${chatId}`)
      .on(
        'postgres_changes',
        { event: 'UPDATE', schema: 'public', table: 'chats', filter: `id=eq.${chatId}` },
        () => {
          supabase
            .rpc('get_client_company_from_chat', { chat_uuid: chatId })
            .then(({ data, error }) => {
              if (!error && data && data.length > 0) setCompany(data[0] as Company);
            });
        }
      )
      .subscribe();

    return () => {
      supabase.removeChannel(channel);
    };
  }, [chatId]);

  // Realtime: refetch when company itself changes (status/name)
  useEffect(() => {
    const companyId = company?.id;
    if (!chatId || !companyId) return;

    const channel = supabase
      .channel(`company-badge-company-${companyId}`)
      .on(
        'postgres_changes',
        { event: 'UPDATE', schema: 'public', table: 'companies', filter: `id=eq.${companyId}` },
        () => {
          supabase
            .rpc('get_client_company_from_chat', { chat_uuid: chatId })
            .then(({ data, error }) => {
              if (!error && data && data.length > 0) setCompany(data[0] as Company);
            });
        }
      )
      .subscribe();

    return () => {
      supabase.removeChannel(channel);
    };
  }, [chatId, company?.id]);
  if (isLoading) {
    return (
      <div className="h-4 w-20 bg-white/10 rounded animate-pulse"></div>
    );
  }

  const companyName = company?.name || 'Нет компании';
  const statusColor = company ? getCompanyStatusColor(company.status) : '';

  // Если нет компании, показываем красным текстом без бейджа
  if (!company) {
    return (
      <span className="text-destructive text-[10px] truncate max-w-full" title={companyName}>
        {companyName}
      </span>
    );
  }

  return (
    <Badge 
      variant="outline" 
      className={`text-[10px] h-auto px-1.5 py-0.5 border ${statusColor} truncate max-w-full`}
      title={companyName}
    >
      {companyName}
    </Badge>
  );
};

export default CompanyBadge;