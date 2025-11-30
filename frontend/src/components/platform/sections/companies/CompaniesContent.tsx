// =============================================================================
// File: CompaniesContent.tsx
// Description: Companies content using React Query + WSE
// =============================================================================

import React from 'react';
import { GlassCard } from '@/components/design-system/GlassCard';
import { useAuth } from '@/contexts/AuthContext';
import { useMyCompanies } from '@/hooks/company';

const CompaniesContent = () => {
  const { user, profile } = useAuth();
  const { companies, isLoading } = useMyCompanies();

  if (!user || !profile) {
    return null;
  }

  return (
    <div className="p-6 h-full overflow-y-auto">
      <div className="max-w-7xl mx-auto">
        <div className="mb-8">
          <h1 className="text-3xl font-bold text-white mb-2">Компании</h1>
          <p className="text-gray-400">Управление компаниями и партнерами</p>
        </div>

        {isLoading ? (
          <GlassCard variant="default" className="text-center py-16">
            <div className="animate-pulse">
              <h3 className="text-xl font-semibold text-white mb-4">Загрузка...</h3>
              <p className="text-gray-400">Получение данных о компаниях</p>
            </div>
          </GlassCard>
        ) : companies.length > 0 ? (
          <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-3">
            {companies.map((company) => (
              <GlassCard key={company.company_id} variant="elevated" className="p-6">
                <div className="flex justify-between items-start mb-4">
                  <h3 className="text-xl font-semibold text-white">{company.company_name}</h3>
                  <span className="text-xs px-2 py-1 bg-primary/20 text-primary rounded">
                    {company.relationship_type}
                  </span>
                </div>
                <div className="space-y-2 text-sm">
                  <div className="flex justify-between">
                    <span className="text-gray-400">ID:</span>
                    <span className="text-white">WID{company.company_id}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-gray-400">Тип:</span>
                    <span className="text-white">{company.company_type || 'N/A'}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-gray-400">Статус:</span>
                    <span className="text-white">{company.is_active ? 'Активна' : 'Архив'}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-gray-400">Добавлен:</span>
                    <span className="text-white">{new Date(company.joined_at).toLocaleDateString()}</span>
                  </div>
                </div>
              </GlassCard>
            ))}
          </div>
        ) : (
          <GlassCard variant="default" className="text-center py-16">
            <h3 className="text-xl font-semibold text-white mb-4">
              Нет закрепленных компаний
            </h3>
            <p className="text-gray-400">
              Закрепленные компании будут отображаться здесь
            </p>
          </GlassCard>
        )}
      </div>
    </div>
  );
};

export default CompaniesContent;
