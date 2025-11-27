// =============================================================================
// File: CompanyBadge.tsx
// Description: Company Badge component using new Chat/Company API
// =============================================================================

import React, { useState, useEffect } from 'react';
import { Badge } from '@/components/ui/badge';
import * as companyApi from '@/api/company';
import { useWSE } from '@/wse';
import { logger } from '@/utils/logger';

interface CompanyBadgeProps {
  chatId: string;
  companyId?: string | null;
}

const getCompanyStatusColor = (status: string | undefined) => {
  switch (status) {
    case 'new':
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

interface CompanyInfo {
  id: string;
  name: string;
  status?: string;
}

const CompanyBadge: React.FC<CompanyBadgeProps> = ({ chatId, companyId }) => {
  const [company, setCompany] = useState<CompanyInfo | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const { isConnected, subscribe, unsubscribe } = useWSE();

  useEffect(() => {
    const fetchCompany = async () => {
      if (!companyId) {
        setCompany(null);
        setIsLoading(false);
        return;
      }

      setIsLoading(true);
      try {
        const companyData = await companyApi.getCompanyById(companyId);
        if (companyData) {
          setCompany({
            id: companyData.id,
            name: companyData.name,
            status: companyData.status
          });
        } else {
          setCompany(null);
        }
      } catch (error) {
        logger.error('Error loading company for badge', error, { component: 'CompanyBadge', companyId });
        setCompany(null);
      } finally {
        setIsLoading(false);
      }
    };

    fetchCompany();
  }, [companyId]);

  // Subscribe to WSE company updates
  useEffect(() => {
    if (!isConnected || !companyId) return;

    const handleCompanyUpdate = (event: { p: { company_id?: string } }) => {
      if (event.p.company_id === companyId) {
        // Refetch company data when updated
        companyApi.getCompanyById(companyId).then(companyData => {
          if (companyData) {
            setCompany({
              id: companyData.id,
              name: companyData.name,
              status: companyData.status
            });
          }
        });
      }
    };

    subscribe('company_updated', handleCompanyUpdate);

    return () => {
      unsubscribe('company_updated', handleCompanyUpdate);
    };
  }, [isConnected, companyId, subscribe, unsubscribe]);

  if (isLoading) {
    return (
      <div className="h-4 w-20 bg-white/10 rounded animate-pulse"></div>
    );
  }

  const companyName = company?.name || 'Нет компании';
  const statusColor = company ? getCompanyStatusColor(company.status) : '';

  // If no company, show in red text without badge
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
