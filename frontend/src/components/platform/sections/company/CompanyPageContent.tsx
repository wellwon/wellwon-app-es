import React, { useState } from 'react';
import { Building2, TrendingUp, DollarSign, Package, MessageSquare, Star, Info } from 'lucide-react';
import { GlassCard } from '@/components/design-system';

import CreateCompanyDialog from '../../sidebar/CreateCompanyDialog';
import { AdminFormsModal } from '@/components/chat/components/AdminFormsModal';
import EmployeeManagement from './EmployeeManagement';
import { useAuth } from '@/contexts/AuthContext';
import { usePlatform } from '@/contexts/PlatformContext';
import type { Company } from '@/types/realtime-chat';

const CompanyPageContent = () => {
  const { user } = useAuth();
  const { selectedCompany } = usePlatform();
  const [showCreateDialog, setShowCreateDialog] = useState(false);
  const [showCreateForm, setShowCreateForm] = useState(false);

  const handleCreateCompany = () => {
    setShowCreateDialog(true);
  };

  const handleConfirmCreate = () => {
    setShowCreateDialog(false);
    setShowCreateForm(true);
  };

  const handleCompanyCreated = () => {
    setShowCreateForm(false);
    // AdminFormsModal handles refreshing companies internally
  };

  // Use real company data from selectedCompany
  const companyData = selectedCompany ? {
    name: selectedCompany.name,
    balance: selectedCompany.balance || 0,
    currency: "USD",
    rating: selectedCompany.rating || 0,
    metrics: {
      dialogs: Math.floor(Math.random() * 50) + 20, // Mock data - replace with real API
      orders: selectedCompany.orders_count || 0,
      turnover: selectedCompany.turnover || 0,
      successfulDeliveries: selectedCompany.successful_deliveries || 0,
      totalOrders: selectedCompany.orders_count || 0
    }
  } : null;

  if (!companyData) {
    return (
      <div className="h-full flex flex-col">
        {/* Header Container */}
        <div className="h-16 bg-dark-gray border-b border-white/10 flex items-center px-6">
        {/* Company selector removed - functionality moved to company card */}
        </div>
        
        {/* Main Content Container */}
        <div className="flex-1 bg-dark-gray flex items-center justify-center">
          <div className="text-center">
            <Building2 className="mx-auto h-12 w-12 text-gray-400 mb-4" />
            <h3 className="text-lg font-medium text-white">Выберите компанию</h3>
            <p className="text-gray-400">Выберите компанию для просмотра аналитики</p>
          </div>
        </div>

        <CreateCompanyDialog
          open={showCreateDialog}
          onOpenChange={setShowCreateDialog}
          onConfirm={handleConfirmCreate}
        />
      </div>
    );
  }

  const deliveryIndex = Math.round(companyData.metrics.successfulDeliveries / companyData.metrics.totalOrders * 100);
  
  const getRatingText = (score: number) => {
    if (score >= 80) return 'Отлично';
    if (score >= 60) return 'Хорошо';
    return 'Средне';
  };

  return (
    <div className="h-full flex flex-col">
      {/* Header Container */}
      <div className="h-16 bg-dark-gray border-b border-white/10 flex items-center px-6">
        {/* Company selector removed - functionality moved to company card */}
      </div>

      {/* Main Content Container */}
      <div className="flex-1 bg-dark-gray p-6 space-y-6 overflow-auto">
        {/* Header */}
        <div className="flex items-center gap-4">
          <div className="w-16 h-16 bg-gradient-to-br from-medium-gray to-light-gray rounded-xl flex items-center justify-center border border-white/10">
            <Building2 size={32} className="text-white" />
          </div>
          <div>
            <h1 className="text-2xl font-bold text-white">{companyData.name}</h1>
            <p className="text-gray-400">Профиль компании и аналитика</p>
          </div>
        </div>

        {/* Main Stats */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          <GlassCard className="p-6">
            <div className="flex items-center justify-between mb-2">
              <span className="text-gray-400">Баланс</span>
              <DollarSign className="text-green-400" size={20} />
            </div>
            <p className="text-2xl font-bold text-white">
              {companyData.balance.toLocaleString()} {companyData.currency}
            </p>
          </GlassCard>

          <GlassCard className="p-6">
            <div className="flex items-center justify-between mb-2">
              <span className="text-gray-400">Оборот за месяц</span>
              <TrendingUp className="text-blue-400" size={20} />
            </div>
            <p className="text-2xl font-bold text-white">
              {companyData.metrics.turnover.toLocaleString()} $
            </p>
          </GlassCard>

          <GlassCard className="p-6">
            <div className="flex items-center justify-between mb-2">
              <div className="flex items-center gap-2">
                <span className="text-gray-400">Рейтинг компании</span>
                <div className="group relative">
                  <Info size={14} className="text-gray-500 cursor-help" />
                  <div className="absolute bottom-full left-1/2 transform -translate-x-1/2 mb-2 w-64 p-2 bg-dark-gray border border-white/20 rounded-lg text-xs text-gray-300 opacity-0 group-hover:opacity-100 transition-opacity z-50">
                    Индекс показывает эффективность доставок. Рассчитывается как отношение успешно доставленных заказов к общему количеству заказов.
                  </div>
                </div>
              </div>
              <Star className="text-yellow-400" size={20} />
            </div>
            <div className="flex items-center gap-2">
              <p className="text-2xl font-bold text-white">{deliveryIndex}%</p>
              <span className="text-sm text-gray-400">({getRatingText(deliveryIndex)})</span>
            </div>
          </GlassCard>
        </div>

        {/* Detailed Metrics */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          <GlassCard className="p-6">
            <h3 className="text-lg font-semibold text-white mb-4">Операционные метрики</h3>
            <div className="space-y-4">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <MessageSquare size={16} className="text-blue-400" />
                  <span className="text-gray-300">Диалогов</span>
                </div>
                <span className="text-white font-medium">{companyData.metrics.dialogs}</span>
              </div>
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <Package size={16} className="text-green-400" />
                  <span className="text-gray-300">Заказов</span>
                </div>
                <span className="text-white font-medium">{companyData.metrics.orders}</span>
              </div>
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <TrendingUp size={16} className="text-purple-400" />
                  <span className="text-gray-300">Успешных доставок</span>
                </div>
                <span className="text-white font-medium">{companyData.metrics.successfulDeliveries}</span>
              </div>
            </div>
          </GlassCard>

          <GlassCard className="p-6">
            <h3 className="text-lg font-semibold text-white mb-4">Последние события</h3>
            <div className="space-y-3">
              <div className="flex items-center gap-3 p-3 bg-white/5 rounded-lg">
                <div className="w-2 h-2 bg-green-400 rounded-full"></div>
                <div>
                  <p className="text-white text-sm">Поступил новый заказ</p>
                  <p className="text-gray-400 text-xs">2 минуты назад</p>
                </div>
              </div>
              <div className="flex items-center gap-3 p-3 bg-white/5 rounded-lg">
                <div className="w-2 h-2 bg-blue-400 rounded-full"></div>
                <div>
                  <p className="text-white text-sm">Обновлен баланс</p>
                  <p className="text-gray-400 text-xs">15 минут назад</p>
                </div>
              </div>
              <div className="flex items-center gap-3 p-3 bg-white/5 rounded-lg">
                <div className="w-2 h-2 bg-yellow-400 rounded-full"></div>
                <div>
                  <p className="text-white text-sm">Завершена доставка №1247</p>
                  <p className="text-gray-400 text-xs">1 час назад</p>
                </div>
              </div>
            </div>
          </GlassCard>
        </div>

        {/* Employee Management */}
        <EmployeeManagement />
      </div>

      <CreateCompanyDialog
        open={showCreateDialog}
        onOpenChange={setShowCreateDialog}
        onConfirm={handleConfirmCreate}
      />
      
      <AdminFormsModal
        isOpen={showCreateForm}
        onClose={() => setShowCreateForm(false)}
        formType="company-registration"
        onSuccess={handleCompanyCreated}
      />
    </div>
  );
};

export default CompanyPageContent;