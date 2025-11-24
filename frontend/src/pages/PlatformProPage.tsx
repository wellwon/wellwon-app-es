// =============================================================================
// Platform Pro Page
// =============================================================================
// Entry point for Platform Pro (developer-only platform)
// Аналог PlatformPage для основной платформы

import React, { Suspense } from 'react';
import { PlatformProProvider } from '@/contexts/PlatformProContext';
import { LoadingOverlayProvider } from '@/contexts/LoadingOverlayContext';
import PlatformProLayout from '@/components/platform-pro/shared/PlatformProLayout';
import PlatformProErrorBoundary from '@/components/platform-pro/shared/PlatformProErrorBoundary';

// Loading fallback component
const PageLoader = () => (
  <div className="flex items-center justify-center h-screen bg-dark-gray">
    <div className="text-white text-lg">Загрузка Platform Pro...</div>
  </div>
);

const PlatformProPage: React.FC = () => {
  return (
    <PlatformProErrorBoundary>
      <LoadingOverlayProvider>
        <PlatformProProvider>
          <Suspense fallback={<PageLoader />}>
            <PlatformProLayout />
          </Suspense>
        </PlatformProProvider>
      </LoadingOverlayProvider>
    </PlatformProErrorBoundary>
  );
};

export default PlatformProPage;
