// =============================================================================
// File: src/App.tsx
// Description: Main App component with providers and routing
// =============================================================================

import { Suspense, useEffect } from 'react';
import { Toaster } from "@/components/ui/toaster";
import { QueryClientProvider } from '@tanstack/react-query';
import { ReactQueryDevtools } from '@tanstack/react-query-devtools';
import { BrowserRouter, Routes, Route, useNavigate } from 'react-router-dom';
import { UTMProvider } from '@/contexts/UTMContext';

import { AuthProvider } from './contexts/AuthContext';
import { WSEProvider } from '@/providers/WSEProvider';
import { ProfileModalProvider } from '@/contexts/ProfileModalContext';
import { EnhancedProfileEditModal } from '@/components/shared/EnhancedProfileEditModal';
import { useProfileModal } from '@/contexts/ProfileModalContext';
import ErrorBoundary from '@/components/shared/ErrorBoundary';
import ProtectedRoute from './components/auth/ProtectedRoute';
import DeveloperRoute from './components/auth/DeveloperRoute';
import { registerNavigateFunction, unregisterNavigateFunction } from '@/utils/navigationHelper';

import { CookieConsent } from '@/components/shared/CookieConsent';
import { useAppRecovery } from '@/hooks/useAppRecovery';
import { logger, logInfo } from '@/utils/logger';
import PageLoader from '@/components/ui/PageLoader';
import { performanceTracker } from '@/utils/performanceTracker';

import { queryClient } from './lib/queryClient';

import './App.css';

// Lazy loading pages with improved error handling
import { createLazyComponent } from '@/components/shared/LazyErrorBoundary';

const HomePage = createLazyComponent(() => import('./pages/HomePage'));
const Version3 = createLazyComponent(() => import('./pages/Version3'));
const NotFound = createLazyComponent(() => import('./pages/NotFound'));
const AuthPage = createLazyComponent(() => import('./components/auth/AuthPage'));
const TermsPage = createLazyComponent(() => import('./pages/TermsPage'));
const PrivacyPage = createLazyComponent(() => import('./pages/PrivacyPage'));
const CookiePolicyPage = createLazyComponent(() => import('./pages/CookiePolicyPage'));

const PlatformPage = createLazyComponent(() => import('./pages/PlatformPage'));
const PlatformProPage = createLazyComponent(() => import('./pages/PlatformProPage'));
const DeclarantPage = createLazyComponent(() => import('./pages/declarant/DeclarantPage'));

const AppContentWithProfile = () => {
  const { isProfileModalOpen, closeProfileModal } = useProfileModal();

  return (
    <>
      <AppContent />
      <EnhancedProfileEditModal
        isOpen={isProfileModalOpen}
        onClose={closeProfileModal}
      />
    </>
  );
};

const AppContent = () => {
  // Initialize app recovery system
  useAppRecovery();
  const navigate = useNavigate();

  useEffect(() => {
    logInfo('Application initialized', { component: 'App' });

    // Register navigation function for error boundaries
    registerNavigateFunction(navigate);

    // Initialize performance tracking
    performanceTracker.recordCustomMetric('app_initialization', performance.now(), {
      component: 'App',
      hasNavigate: !!navigate
    });

    return () => {
      unregisterNavigateFunction();
    };
  }, [navigate]);

  return (
    <UTMProvider>
      <Suspense fallback={<PageLoader />}>
        <Routes>
          {/* Public routes */}
          <Route path="/" element={<HomePage />} />
          <Route path="/financing" element={<Version3 />} />
          <Route path="/auth" element={<AuthPage />} />

          {/* Protected routes */}
          <Route
            path="/platform/:section?/:chatId?"
            element={
              <ProtectedRoute>
                <PlatformPage />
              </ProtectedRoute>
            }
          />

          {/* Platform Pro - Developer-only platform */}
          <Route
            path="/platform-pro/:section?"
            element={
              <DeveloperRoute>
                <PlatformProPage />
              </DeveloperRoute>
            }
          />

          {/* Platform Pro - Declarant package page */}
          <Route
            path="/platform-pro/declarant/package/:packageId"
            element={
              <DeveloperRoute>
                <PlatformProPage />
              </DeveloperRoute>
            }
          />

          {/* Platform Pro - Declaration page */}
          <Route
            path="/platform-pro/declaration/:declarationId?"
            element={
              <DeveloperRoute>
                <PlatformProPage />
              </DeveloperRoute>
            }
          />

          {/* Declarant module - standalone isolated application */}
          <Route
            path="/declarant"
            element={
              <ProtectedRoute>
                <DeclarantPage />
              </ProtectedRoute>
            }
          />

          {/* Legal pages */}
          <Route path="/terms" element={<TermsPage />} />
          <Route path="/privacy" element={<PrivacyPage />} />
          <Route path="/cookie-policy" element={<CookiePolicyPage />} />

          {/* 404 */}
          <Route path="*" element={<NotFound />} />
        </Routes>
      </Suspense>

      <Toaster />
      <CookieConsent
        onAccept={(preferences) => {
          logger.userAction('cookie_consent_accepted', 'CookieConsent', {
            metadata: { preferences: preferences } as Record<string, unknown>
          });
        }}
      />
    </UTMProvider>
  );
};

function App() {
  return (
    <ErrorBoundary>
      <QueryClientProvider client={queryClient}>
        <AuthProvider>
          <WSEProvider>
            <ProfileModalProvider>
              <BrowserRouter>
                <AppContentWithProfile />
              </BrowserRouter>
            </ProfileModalProvider>
          </WSEProvider>
        </AuthProvider>

        {/* React Query Devtools (only in dev) */}
        <ReactQueryDevtools initialIsOpen={false} />
      </QueryClientProvider>
    </ErrorBoundary>
  );
}

export default App;
