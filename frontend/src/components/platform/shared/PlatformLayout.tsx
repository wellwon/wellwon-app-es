import React from 'react';
import { usePlatform } from '@/contexts/PlatformContext';
import PlatformSidebar from '../sidebar/PlatformSidebar';
import SafeContentRenderer from './SafeContentRenderer';


const PlatformLayout = () => {
  const { activeSection, userTheme, isLightTheme } = usePlatform();

  // Light theme support (like Declarant page)
  // Sidebar stays dark (#232328), only content area changes
  const contentBgClass = isLightTheme ? 'bg-[#f4f4f4]' : 'bg-dark-gray';

  return (
    <div className={`h-screen flex overflow-hidden ${userTheme}`}>
      {/* Sidebar - always dark (#232328) */}
      <PlatformSidebar />

      {/* Основная область контента - supports light/dark theme */}
      <div className={`flex-1 flex flex-col min-w-0 relative ${contentBgClass}`}>
        <SafeContentRenderer sectionId={activeSection} />
      </div>
    </div>
  );
};

export default PlatformLayout;