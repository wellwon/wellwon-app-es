
import React, { Suspense } from 'react';
import { ProvidersWrapper } from '@/contexts/chat';
import { PlatformProvider } from '@/contexts/PlatformContext';
import { LoadingOverlayProvider } from '@/contexts/LoadingOverlayContext';
import PlatformLayout from '@/components/platform/shared/PlatformLayout';
import PlatformErrorBoundary from '@/components/platform/shared/PlatformErrorBoundary';
import PageLoader from '@/components/ui/PageLoader';

const PlatformPage = () => {
  return (
    <PlatformErrorBoundary>
      <LoadingOverlayProvider>
        <PlatformProvider>
          <ProvidersWrapper>
            <Suspense fallback={<PageLoader />}>
              <PlatformLayout />
            </Suspense>
          </ProvidersWrapper>
        </PlatformProvider>
      </LoadingOverlayProvider>
    </PlatformErrorBoundary>
  );
};

export default PlatformPage;
