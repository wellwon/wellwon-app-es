import React from 'react';
import { GlassCard } from '@/components/design-system/GlassCard';

const ChatSettingsContent = () => {
  return (
    <div className="p-6 h-full overflow-y-auto">
      <div className="max-w-7xl mx-auto">
        <div className="mb-8">
          <h1 className="text-3xl font-bold text-white mb-2">Настройки чатов</h1>
          <p className="text-gray-400">Конфигурация и настройки чатов</p>
        </div>

        <GlassCard variant="default" className="text-center py-16">
          <h3 className="text-xl font-semibold text-white mb-4">Раздел в разработке</h3>
          <p className="text-gray-400">Здесь будут настройки чатов и ботов</p>
        </GlassCard>
      </div>
    </div>
  );
};

export default ChatSettingsContent;