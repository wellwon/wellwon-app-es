
import React, { Suspense } from 'react';
import { ProvidersWrapper } from '@/contexts/chat';
import { PlatformProvider } from '@/contexts/PlatformContext';
import { LoadingOverlayProvider } from '@/contexts/LoadingOverlayContext';
import PlatformLayout from '@/components/platform/shared/PlatformLayout';
import PlatformErrorBoundary from '@/components/platform/shared/PlatformErrorBoundary';
import PageLoader from '@/components/ui/PageLoader';

const PlatformPage = () => {
  return (
    <LoadingOverlayProvider>
      <PlatformProvider>
        <PlatformErrorBoundary>
          <ProvidersWrapper>
            <Suspense fallback={<PageLoader />}>
              <PlatformLayout />
            </Suspense>
          </ProvidersWrapper>
        </PlatformErrorBoundary>
      </PlatformProvider>
    </LoadingOverlayProvider>
  );
};

export default PlatformPage;
