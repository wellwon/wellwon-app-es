import React, { Suspense } from 'react';
import { getSectionComponent, SectionId } from './SectionConfig';
import { Loader } from '@/components/ui/loader';
import { usePlatform } from '@/contexts/PlatformContext';
import LazyErrorBoundary from '@/components/shared/LazyErrorBoundary';

interface SafeContentRendererProps {
  sectionId: SectionId;
}

const SafeContentRenderer: React.FC<SafeContentRendererProps> = ({ sectionId }) => {
  const { isDeveloper } = usePlatform();
  const SectionComponent = getSectionComponent(sectionId, isDeveloper);
  
  if (!SectionComponent) {
    return (
      <div className="p-6 h-full flex items-center justify-center">
        <div className="text-center">
          <h2 className="text-xl font-semibold text-white mb-2">Секция не найдена</h2>
          <p className="text-gray-400">Секция "{sectionId}" не существует</p>
        </div>
      </div>
    );
  }

  return (
    <LazyErrorBoundary>
      <Suspense 
        fallback={
          <div className="h-full flex items-center justify-center">
            <Loader className="text-accent-red" />
          </div>
        }
      >
        <SectionComponent />
      </Suspense>
    </LazyErrorBoundary>
  );
};

export default SafeContentRenderer;