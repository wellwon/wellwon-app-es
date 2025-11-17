import React from 'react';
import { Navigate, useLocation } from 'react-router-dom';
import { useAuth } from '@/contexts/AuthContext';

interface ProtectedRouteProps {
  children: React.ReactNode;
}

const ProtectedRoute: React.FC<ProtectedRouteProps> = ({ children }) => {
  const { user, profile, loading } = useAuth();
  const location = useLocation();

  if (loading) {
    return (
      <div className="min-h-screen bg-gradient-dark flex items-center justify-center">
        <div className="text-white">Загрузка...</div>
      </div>
    );
  }

  if (!user) {
    // Сохраняем текущий путь для редиректа после входа
    return <Navigate to={`/auth?mode=login&redirect=${encodeURIComponent(location.pathname)}`} replace />;
  }

  // Users are now active by default, but keep check for manually deactivated users
  if (profile && !profile.active) {
    return (
      <div className="min-h-screen bg-gradient-dark flex items-center justify-center">
        <div className="max-w-md mx-auto text-center p-8">
          <div className="text-white text-xl mb-4">Аккаунт заблокирован</div>
          <div className="text-gray-400 mb-6">
            Ваш аккаунт был заблокирован администратором. Пожалуйста, обратитесь к поддержке.
          </div>
          <div className="text-sm text-gray-500">
            Тип аккаунта: {profile.is_developer ? 'Разработчик WW' : 'Менеджер WW'}
          </div>
        </div>
      </div>
    );
  }

  return <>{children}</>;
};

export default ProtectedRoute;