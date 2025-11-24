// =============================================================================
// Platform Pro Layout
// =============================================================================

import React, { Suspense } from 'react';
import { usePlatformPro } from '@/contexts/PlatformProContext';
import PlatformProSidebar from '../sidebar/PlatformProSidebar';
import SafeContentRenderer from './SafeContentRenderer';

const PlatformProLayout: React.FC = () => {
  const { isDark } = usePlatformPro();

  return (
    <div className={`h-screen flex overflow-hidden ${isDark ? 'dark bg-[#1a1a1e]' : 'bg-[#f4f4f4]'}`}>
      {/* Sidebar */}
      <PlatformProSidebar />

      {/* Main Content */}
      <div className="flex-1 flex flex-col min-w-0">
        <Suspense
          fallback={
            <div className="flex items-center justify-center h-full">
              <div className={isDark ? 'text-white' : 'text-gray-900'}>
                Загрузка...
              </div>
            </div>
          }
        >
          <SafeContentRenderer />
        </Suspense>
      </div>
    </div>
  );
};

export default PlatformProLayout;
