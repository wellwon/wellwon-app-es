// =============================================================================
// File: CompanyBadge.tsx
// Description: Company Badge component using React Query
// =============================================================================

import React from 'react';
import { Badge } from '@/components/ui/badge';
import { useCompany } from '@/hooks/company';

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

const CompanyBadge: React.FC<CompanyBadgeProps> = ({ chatId, companyId }) => {
  const { company, isLoading } = useCompany(companyId ?? null);

  const companyName = company?.name || 'Нет компании';
  const statusColor = company ? getCompanyStatusColor((company as any).status) : '';

  // Fixed height container to prevent layout shift
  return (
    <div className="h-[18px] flex items-center">
      {isLoading ? (
        <div className="h-[14px] w-16 bg-white/10 rounded animate-pulse" />
      ) : !company ? (
        <span className="text-destructive text-[10px] truncate max-w-full leading-none" title={companyName}>
          {companyName}
        </span>
      ) : (
        <Badge
          variant="outline"
          className={`text-[10px] h-[14px] px-1.5 py-0 border leading-none flex items-center ${statusColor} truncate max-w-full`}
          title={companyName}
        >
          {companyName}
        </Badge>
      )}
    </div>
  );
};

export default CompanyBadge;
