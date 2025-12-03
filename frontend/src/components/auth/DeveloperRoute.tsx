// =============================================================================
// Developer Route Guard
// =============================================================================
// Protected route component that only allows access to users with developer status
// Redirects non-developers to /platform and unauthenticated users to /auth

import React from 'react';
import { Navigate, useLocation } from 'react-router-dom';
import { useAuth } from '@/contexts/AuthContext';
import { useToast } from '@/hooks/use-toast';

interface DeveloperRouteProps {
  children: React.ReactNode;
}

const DeveloperRoute: React.FC<DeveloperRouteProps> = ({ children }) => {
  const { user, profile, loading } = useAuth();
  const location = useLocation();
  const { toast } = useToast();
  const [hasShownToast, setHasShownToast] = React.useState(false);

  // Show loading state while checking authentication or waiting for profile
  if (loading || (user && !profile)) {
    return (
      <div className="flex items-center justify-center h-screen bg-dark-gray">
        <div className="text-white">Загрузка...</div>
      </div>
    );
  }

  // Redirect to auth if not logged in
  if (!user) {
    const redirectUrl = encodeURIComponent(location.pathname + location.search);
    return <Navigate to={`/auth?mode=login&redirect=${redirectUrl}`} replace />;
  }

  // Redirect to platform if not a developer (profile is guaranteed to exist here)
  if (!profile.is_developer) {
    // Show toast only once
    if (!hasShownToast) {
      toast({
        title: 'Доступ запрещён',
        description: 'Platform Pro доступна только для разработчиков',
        variant: 'destructive',
      });
      setHasShownToast(true);
    }

    return <Navigate to="/platform" replace />;
  }

  // User is authenticated and is a developer - render children
  return <>{children}</>;
};

export default DeveloperRoute;
