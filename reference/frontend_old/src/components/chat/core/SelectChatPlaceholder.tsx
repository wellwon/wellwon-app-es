import React from 'react';
import { MessageCircle } from 'lucide-react';

const SelectChatPlaceholder = () => {
  return (
    <div className="h-full flex items-center justify-center p-8 bg-dark-gray">
      <div className="text-center max-w-md">
        <div className="w-16 h-16 bg-accent-red/20 rounded-full flex items-center justify-center mx-auto mb-6">
          <MessageCircle size={32} className="text-accent-red" />
        </div>
        <h2 className="text-2xl font-bold text-white mb-4">
          Выберите чат
        </h2>
        <p className="text-gray-400 leading-relaxed">
          Выберите чат из списка слева для просмотра переписки
        </p>
      </div>
    </div>
  );
};

export default SelectChatPlaceholder;