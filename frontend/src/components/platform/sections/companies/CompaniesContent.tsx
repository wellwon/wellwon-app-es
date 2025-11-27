import React, { useState, useEffect } from 'react';
import { GlassCard } from '@/components/design-system/GlassCard';
import { useAuth } from '@/contexts/AuthContext';
import { CompanyService } from '@/services/CompanyService';
import { logger } from '@/utils/logger';
import type { Company } from '@/types/realtime-chat';

const CompaniesContent = () => {
  const { user, profile } = useAuth();
  const [userCompanies, setUserCompanies] = useState<(Company & { relationship_type: string })[]>([]);
  const [isLoading, setIsLoading] = useState(false);

  useEffect(() => {
    const loadUserCompanies = async () => {
      if (!user || !profile) return;
      
      setIsLoading(true);
      try {
        const companies = await CompanyService.getUserCompanies(user.id);
        setUserCompanies(companies);
      } catch (error) {
        logger.error('Error loading user companies', error, { component: 'CompaniesContent' });
      } finally {
        setIsLoading(false);
      }
    };

    loadUserCompanies();
  }, [user, profile]);

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
        ) : userCompanies.length > 0 ? (
          <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-3">
            {userCompanies.map((company) => (
              <GlassCard key={company.id} variant="elevated" className="p-6">
                <div className="flex justify-between items-start mb-4">
                  <h3 className="text-xl font-semibold text-white">{company.name}</h3>
                  <span className="text-xs px-2 py-1 bg-primary/20 text-primary rounded">
                    {company.relationship_type}
                  </span>
                </div>
                <div className="space-y-2 text-sm">
                  <div className="flex justify-between">
                    <span className="text-gray-400">ID:</span>
                    <span className="text-white">WID{company.id}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-gray-400">Тип:</span>
                    <span className="text-white">{company.company_type}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-gray-400">Статус:</span>
                    <span className="text-white">{company.status}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-gray-400">Баланс:</span>
                    <span className="text-white">${Number(company.balance).toLocaleString()}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-gray-400">Заказов:</span>
                    <span className="text-white">{company.orders_count}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-gray-400">Рейтинг:</span>
                    <span className="text-white">{Number(company.rating).toFixed(1)}</span>
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