// =============================================================================
// Safe Content Renderer для Platform Pro
// =============================================================================

import React, { Suspense } from 'react';
import { usePlatformPro } from '@/contexts/PlatformProContext';
import { getProSectionComponent } from '@/config/PlatformProSectionConfig';
import { LazyErrorBoundary } from '@/components/shared/LazyErrorBoundary';

const SafeContentRenderer: React.FC = () => {
  const { activeSection, isDark } = usePlatformPro();

  const SectionComponent = getProSectionComponent(activeSection);

  if (!SectionComponent) {
    return (
      <div className="flex items-center justify-center h-full">
        <div className={isDark ? 'text-white' : 'text-gray-900'}>
          Секция не найдена: {activeSection}
        </div>
      </div>
    );
  }

  return (
    <LazyErrorBoundary>
      <Suspense
        fallback={
          <div className="flex items-center justify-center h-full">
            <div className={isDark ? 'text-white' : 'text-gray-900'}>
              Загрузка секции...
            </div>
          </div>
        }
      >
        <SectionComponent />
      </Suspense>
    </LazyErrorBoundary>
  );
};

export default SafeContentRenderer;
