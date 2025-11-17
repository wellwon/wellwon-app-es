
import { useLocation } from "react-router-dom";
import { useEffect } from "react";

import { Home, ArrowLeft } from 'lucide-react';
import UTMLink from "@/components/shared/UTMLink";
import { GlassCard } from '@/components/design-system/GlassCard';
import { GlassButton } from '@/components/design-system/GlassButton';
import { logger } from '@/utils/logger';

const NotFound = () => {
  const location = useLocation();

  useEffect(() => {
    logger.error('404 Error: User attempted to access non-existent route', null, {
      component: 'NotFound',
      path: location.pathname
    });
  }, [location.pathname]);

  return (
    <div className="min-h-screen flex items-center justify-center bg-gradient-dark animate-fade-in">
      <GlassCard variant="elevated" className="max-w-md mx-4 text-center">
        <div className="flex flex-col items-center space-y-6">
          <div className="text-8xl font-bold text-accent-red opacity-80">
            404
          </div>
          
          <div className="space-y-2">
            <h1 className="text-3xl font-bold text-text-white">Страница не найдена</h1>
            <p className="text-text-gray-400">Запрашиваемая страница не существует или была перемещена</p>
          </div>

          <UTMLink to="/" className="inline-block">
            <GlassButton variant="primary" size="lg" className="mt-4">
              <Home className="w-4 h-4 mr-2" />
              На главную
            </GlassButton>
          </UTMLink>
        </div>
      </GlassCard>
    </div>
  );
};

export default NotFound;
