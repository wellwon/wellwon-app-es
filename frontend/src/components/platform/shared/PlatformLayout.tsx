import React from 'react';
import { usePlatform } from '@/contexts/PlatformContext';
import PlatformSidebar from '../sidebar/PlatformSidebar';
import SafeContentRenderer from './SafeContentRenderer';
import DeveloperPanel from '../developer/DeveloperPanel';


const PlatformLayout = () => {
  const { activeSection, userTheme } = usePlatform();

  // Обычный фон без градиентов

  return (
    <div className={`h-screen bg-dark-gray flex overflow-hidden ${userTheme}`}>
      <PlatformSidebar />
      
      {/* Основная область контента */}
      <div className="flex-1 flex flex-col min-w-0 relative bg-dark-gray">
        <SafeContentRenderer sectionId={activeSection} />
      </div>
      
      {/* Floating Developer Panel */}
      <DeveloperPanel />
    </div>
  );
};

export default PlatformLayout;