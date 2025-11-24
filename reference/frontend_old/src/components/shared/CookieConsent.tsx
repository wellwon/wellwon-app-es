import React, { useState, useEffect } from 'react';
import { Button } from '@/components/ui/button';
import { CookieSettingsSheet } from './CookieSettingsSheet';
import { logger } from '@/utils/logger';

interface CookieConsentProps {
  onAccept?: (hasAcceptedAll: boolean) => void;
}

interface CookiePreferences {
  essential: boolean;
  analytics: boolean;
  advertising: boolean;
  preferences: boolean;
}

const COOKIE_CONSENT_KEY = 'WellWon-cookie-consent';

// Dev функция для сброса cookie consent (только в development)
const resetCookieConsent = () => {
  if (import.meta.env.DEV) {
    localStorage.removeItem(COOKIE_CONSENT_KEY);
    // Убираем автоматическую перезагрузку - пусть пользователь сам решает
    if (import.meta.env.DEV) {
      logger.info('Cookie consent reset. Please refresh the page manually.', { component: 'CookieConsent' });
    }
  }
};

export const CookieConsent: React.FC<CookieConsentProps> = ({ onAccept }) => {
  const [isVisible, setIsVisible] = useState(false);
  const [showSettings, setShowSettings] = useState(false);

  useEffect(() => {
    const consent = localStorage.getItem(COOKIE_CONSENT_KEY);
    if (!consent) {
      // Показываем через небольшую задержку для лучшего UX
      setTimeout(() => setIsVisible(true), 2000);
    }
  }, []);

  const handleAcceptAll = () => {
    const preferences: CookiePreferences = {
      essential: true,
      analytics: true,
      advertising: true,
      preferences: true,
    };
    
    localStorage.setItem(COOKIE_CONSENT_KEY, JSON.stringify({
      acceptedAll: true,
      preferences,
      timestamp: new Date().toISOString()
    }));
    onAccept?.(true);
    setIsVisible(false);
  };

  const handleRejectNonEssential = () => {
    const preferences: CookiePreferences = {
      essential: true,
      analytics: false,
      advertising: false,
      preferences: false,
    };
    
    localStorage.setItem(COOKIE_CONSENT_KEY, JSON.stringify({
      acceptedAll: false,
      preferences,
      timestamp: new Date().toISOString()
    }));
    onAccept?.(false);
    setIsVisible(false);
  };

  const handleSavePreferences = (preferences: CookiePreferences) => {
    const hasAcceptedAll = preferences.analytics && preferences.advertising && preferences.preferences;
    
    localStorage.setItem(COOKIE_CONSENT_KEY, JSON.stringify({
      acceptedAll: hasAcceptedAll,
      preferences,
      timestamp: new Date().toISOString()
    }));
    onAccept?.(hasAcceptedAll);
    setIsVisible(false);
  };

  if (!isVisible) return null;

  return (
    <>
      <div className="fixed bottom-6 right-6 z-50 max-w-sm animate-fade-in">
        <div className="bg-medium-gray/95 backdrop-blur-lg border border-white/10 rounded-2xl p-6 shadow-2xl">
          <h3 className="text-white text-lg font-semibold mb-3">
            Управление cookie
          </h3>
          
          <p className="text-gray-400 text-sm mb-4 leading-relaxed">
            Мы используем файлы cookie для улучшения работы сайта.{' '}
            <button 
              onClick={() => setShowSettings(true)}
              className="text-accent-red underline hover:text-accent-red/80 transition-colors"
            >
              Настройки cookie
            </button>.
          </p>

          <div className="space-y-2 mt-6">
            <Button
              onClick={handleAcceptAll}
              className="w-full bg-white text-dark-gray hover:bg-gray-100 rounded-lg py-2 px-4 text-sm font-medium transition-all duration-300"
            >
              Принять все
            </Button>
            
            <Button
              variant="secondary"
              onClick={handleRejectNonEssential}
              className="w-full rounded-lg py-2 px-4 text-sm font-medium"
            >
              Только необходимые
            </Button>
          </div>
          
          {/* Dev кнопка для сброса (только в development) */}
          {import.meta.env.DEV && (
            <button
              onClick={resetCookieConsent}
              className="mt-2 text-xs text-gray-500 hover:text-gray-400"
            >
              [Dev] Reset Cookie Consent
            </button>
          )}
        </div>
      </div>

      <CookieSettingsSheet
        open={showSettings}
        onOpenChange={setShowSettings}
        onSave={handleSavePreferences}
      />
    </>
  );
};