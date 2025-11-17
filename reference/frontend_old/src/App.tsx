
import { lazy, Suspense, useEffect } from 'react';
import { Toaster } from "@/components/ui/toaster";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { BrowserRouter, Routes, Route, useNavigate } from "react-router-dom";
import { UTMProvider } from "@/contexts/UTMContext";

import { AuthProvider } from "@/contexts/AuthContext";
import { ProfileModalProvider } from "@/contexts/ProfileModalContext";
import { EnhancedProfileEditModal } from "@/components/shared/EnhancedProfileEditModal";
import { useProfileModal } from "@/contexts/ProfileModalContext";
import ErrorBoundary from "@/components/shared/ErrorBoundary";
import ProtectedRoute from "@/components/auth/ProtectedRoute";
import { registerNavigateFunction, unregisterNavigateFunction } from "@/utils/navigationHelper";

import { CookieConsent } from "@/components/shared/CookieConsent";
import { useAppRecovery } from "@/hooks/useAppRecovery";
import { logger, logInfo } from "@/utils/logger";
import PageLoader from "@/components/ui/PageLoader";
import { performanceTracker } from "@/utils/performanceTracker";

// Ленивая загрузка страниц с улучшенной обработкой ошибок
import { createLazyComponent } from "@/components/shared/LazyErrorBoundary";

const HomePage = createLazyComponent(() => import("./pages/HomePage"));
const Version3 = createLazyComponent(() => import("./pages/Version3"));
const NotFound = createLazyComponent(() => import("./pages/NotFound"));
const AuthPage = createLazyComponent(() => import("./components/auth/AuthPage"));
const TermsPage = createLazyComponent(() => import("./pages/TermsPage"));
const PrivacyPage = createLazyComponent(() => import("./pages/PrivacyPage"));
const CookiePolicyPage = createLazyComponent(() => import("./pages/CookiePolicyPage"));

const PlatformPage = createLazyComponent(() => import("./pages/PlatformPage"));
const DesignPage = createLazyComponent(() => import("./pages/DesignPage"));

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 5 * 60 * 1000, // 5 минут
      refetchOnWindowFocus: false,
    },
  },
});

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
  // Инициализируем систему восстановления приложения
  useAppRecovery();
  const navigate = useNavigate();

  useEffect(() => {
    logInfo('Application initialized', { component: 'App' });
    
    // Регистрируем функцию навигации для error boundaries
    registerNavigateFunction(navigate);
    
    // Инициализируем отслеживание производительности
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
          <Route path="/" element={<HomePage />} />
          <Route path="/financing" element={<Version3 />} />
          <Route path="/auth" element={<AuthPage />} />
          
          <Route path="/platform/:section?/:chatId?" element={<ProtectedRoute><PlatformPage /></ProtectedRoute>} />
          
          <Route path="/design" element={<DesignPage />} />
          <Route path="/terms" element={<TermsPage />} />
          <Route path="/privacy" element={<PrivacyPage />} />
          <Route path="/cookie-policy" element={<CookiePolicyPage />} />
          {/* ADD ALL CUSTOM ROUTES ABOVE THE CATCH-ALL "*" ROUTE */}
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

const App = () => {
  return (
    <ErrorBoundary>
      <QueryClientProvider client={queryClient}>
        <AuthProvider>
          <ProfileModalProvider>
            <BrowserRouter>
              <AppContentWithProfile />
            </BrowserRouter>
          </ProfileModalProvider>
        </AuthProvider>
      </QueryClientProvider>
    </ErrorBoundary>
  );
};

export default App;
