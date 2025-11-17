import React from 'react';
import { GlassCard } from '@/components/design-system/GlassCard';

const LastMileContent = () => {
  return (
    <div className="p-6 h-full overflow-y-auto">
      <div className="max-w-7xl mx-auto">
        <div className="mb-8">
          <h1 className="text-3xl font-bold text-white mb-2">Последняя миля</h1>
          <p className="text-gray-400">Управление доставкой до клиента</p>
        </div>

        <GlassCard variant="default" className="text-center py-16">
          <h3 className="text-xl font-semibold text-white mb-4">Раздел в разработке</h3>
          <p className="text-gray-400">Здесь будет система последней мили</p>
        </GlassCard>
      </div>
    </div>
  );
};

export default LastMileContent;