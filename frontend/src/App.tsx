// =============================================================================
// File: src/App.tsx
// Description: Main App component with providers and routing
// =============================================================================

import { QueryClientProvider } from '@tanstack/react-query';
import { ReactQueryDevtools } from '@tanstack/react-query-devtools';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';

import { AuthProvider } from './contexts/AuthContext';
import { queryClient } from './lib/queryClient';

// Pages
import HomePage from './pages/HomePage';
import AuthPage from './components/auth/AuthPage';
import PlatformPage from './pages/PlatformPage';
import NotFound from './pages/NotFound';

// Auth protection
import ProtectedRoute from './components/auth/ProtectedRoute';

import './App.css';

function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <AuthProvider>
          <Routes>
            {/* Public routes */}
            <Route path="/" element={<HomePage />} />
            <Route path="/auth" element={<AuthPage />} />

            {/* Protected routes */}
            <Route
              path="/platform/*"
              element={
                <ProtectedRoute>
                  <PlatformPage />
                </ProtectedRoute>
              }
            />

            {/* 404 */}
            <Route path="*" element={<NotFound />} />
          </Routes>
        </AuthProvider>
      </BrowserRouter>

      {/* React Query Devtools (only in dev) */}
      <ReactQueryDevtools initialIsOpen={false} />
    </QueryClientProvider>
  );
}

export default App;
