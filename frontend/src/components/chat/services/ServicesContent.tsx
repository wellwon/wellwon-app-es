import React from 'react';
import { Wrench } from 'lucide-react';
import { usePlatform } from '@/contexts/PlatformContext';

const ServicesContent = () => {
  const { isLightTheme } = usePlatform();

  const theme = isLightTheme ? {
    text: {
      primary: 'text-gray-900',
      secondary: 'text-gray-500'
    }
  } : {
    text: {
      primary: 'text-white',
      secondary: 'text-gray-400'
    }
  };

  return (
    <div className="flex flex-col items-center justify-center h-full text-center py-16">
      <Wrench size={48} className={`mb-4 ${theme.text.secondary}`} />
      <h3 className={`font-medium mb-2 ${theme.text.primary}`}>Каталог услуг</h3>
      <p className={`text-sm max-w-xs ${theme.text.secondary}`}>
        Раздел в разработке. Здесь будет каталог доступных услуг.
      </p>
    </div>
  );
};

export default ServicesContent;