import React from 'react';
import UserManagement from '@/components/admin/UserManagement';

const SettingsContent = () => {
  return (
    <div className="p-6 h-full overflow-y-auto">
      <div className="max-w-7xl mx-auto">
        <div className="mb-8">
          <h1 className="text-3xl font-bold text-white mb-2">Настройки платформы</h1>
          <p className="text-gray-400">Настройки и администрирование системы</p>
        </div>

        <div className="max-w-4xl">
          <div>
            <h2 className="text-xl font-semibold text-white mb-4">Управление пользователями</h2>
            <UserManagement />
          </div>
        </div>
      </div>
    </div>
  );
};

export default SettingsContent;