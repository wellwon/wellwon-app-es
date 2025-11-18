import React, { createContext, useContext, useState, useEffect, ReactNode } from 'react';

interface ChatDisplayOptions {
  showTelegramNames: boolean;
  showTelegramIcon: boolean;
  preferUsernameOverName: boolean;
}

interface ChatDisplayOptionsContextType {
  options: ChatDisplayOptions;
  updateOption: (key: keyof ChatDisplayOptions, value: boolean) => void;
  resetToDefaults: () => void;
}

const defaultOptions: ChatDisplayOptions = {
  showTelegramNames: true,
  showTelegramIcon: true,
  preferUsernameOverName: false,
};

const STORAGE_KEY = 'chat-display-options';

const ChatDisplayOptionsContext = createContext<ChatDisplayOptionsContextType | null>(null);

export const ChatDisplayOptionsProvider: React.FC<{ children: ReactNode }> = ({ children }) => {
  const [options, setOptions] = useState<ChatDisplayOptions>(defaultOptions);

  // Загружаем настройки из localStorage при инициализации
  useEffect(() => {
    try {
      const stored = localStorage.getItem(STORAGE_KEY);
      if (stored) {
        const parsedOptions = JSON.parse(stored);
        setOptions({ ...defaultOptions, ...parsedOptions });
      }
    } catch (error) {
      console.warn('Failed to load chat display options from localStorage:', error);
    }
  }, []);

  // Сохраняем настройки в localStorage при изменении
  useEffect(() => {
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(options));
    } catch (error) {
      console.warn('Failed to save chat display options to localStorage:', error);
    }
  }, [options]);

  const updateOption = (key: keyof ChatDisplayOptions, value: boolean) => {
    setOptions(prev => ({ ...prev, [key]: value }));
  };

  const resetToDefaults = () => {
    setOptions(defaultOptions);
  };

  return (
    <ChatDisplayOptionsContext.Provider value={{ options, updateOption, resetToDefaults }}>
      {children}
    </ChatDisplayOptionsContext.Provider>
  );
};

export const useChatDisplayOptions = () => {
  const context = useContext(ChatDisplayOptionsContext);
  if (!context) {
    throw new Error('useChatDisplayOptions must be used within a ChatDisplayOptionsProvider');
  }
  return context;
};