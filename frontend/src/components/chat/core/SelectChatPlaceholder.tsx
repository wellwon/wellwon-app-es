import React from 'react';
import { MessageCircle } from 'lucide-react';
import { usePlatform } from '@/contexts/PlatformContext';

const SelectChatPlaceholder = () => {
  const { isLightTheme } = usePlatform();

  return (
    <div className={`h-full flex items-center justify-center p-8 ${isLightTheme ? 'bg-[#f4f4f4]' : 'bg-dark-gray'}`}>
      <div className="text-center max-w-md">
        <div className={`w-16 h-16 rounded-full flex items-center justify-center mx-auto mb-6 ${isLightTheme ? 'bg-gray-200' : 'bg-accent-red/20'}`}>
          <MessageCircle size={32} className={isLightTheme ? 'text-gray-600' : 'text-accent-red'} />
        </div>
        <h2 className={`text-2xl font-bold mb-4 ${isLightTheme ? 'text-gray-900' : 'text-white'}`}>
          Выберите чат
        </h2>
        <p className={`leading-relaxed ${isLightTheme ? 'text-[#6b7280]' : 'text-gray-400'}`}>
          Выберите чат из списка слева для просмотра переписки
        </p>
      </div>
    </div>
  );
};

export default SelectChatPlaceholder;