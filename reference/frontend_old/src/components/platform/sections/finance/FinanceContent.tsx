import React from 'react';
import { GlassCard } from '@/components/design-system/GlassCard';

const FinanceContent = () => {
  return (
    <div className="p-6 h-full overflow-y-auto">
      <div className="max-w-7xl mx-auto">
        <div className="mb-8">
          <h1 className="text-3xl font-bold text-white mb-2">Финансы и кошелёк</h1>
          <p className="text-gray-400">Управление финансами и платежами</p>
        </div>

        <GlassCard variant="default" className="text-center py-16">
          <h3 className="text-xl font-semibold text-white mb-4">Раздел в разработке</h3>
          <p className="text-gray-400">Здесь будет финансовая система</p>
        </GlassCard>
      </div>
    </div>
  );
};

export default FinanceContent;