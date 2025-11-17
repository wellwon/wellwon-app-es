import React, { useState } from 'react';
import { X, Plus, Minus } from 'lucide-react';
import { Button } from '@/components/ui/button';
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
  SheetDescription,
  SheetFooter,
} from '@/components/ui/sheet';
import { Switch } from '@/components/ui/switch';

interface CookieSettingsSheetProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onSave: (preferences: CookiePreferences) => void;
}

interface CookiePreferences {
  essential: boolean;
  analytics: boolean;
  advertising: boolean;
  preferences: boolean;
}

export const CookieSettingsSheet: React.FC<CookieSettingsSheetProps> = ({
  open,
  onOpenChange,
  onSave,
}) => {
  const [expandedSections, setExpandedSections] = useState<Record<string, boolean>>({});
  const [cookiePrefs, setCookiePrefs] = useState<CookiePreferences>({
    essential: true,
    analytics: true,
    advertising: true,
    preferences: true,
  });

  const toggleSection = (section: string) => {
    setExpandedSections(prev => ({
      ...prev,
      [section]: !prev[section]
    }));
  };

  const handleSwitchChange = (key: keyof CookiePreferences, value: boolean) => {
    setCookiePrefs(prev => ({
      ...prev,
      [key]: value
    }));
  };

  const handleConfirm = () => {
    onSave(cookiePrefs);
    onOpenChange(false);
  };

  const handleAcceptAll = () => {
    const allAccepted = {
      essential: true,
      analytics: true,
      advertising: true,
      preferences: true,
    };
    setCookiePrefs(allAccepted);
    onSave(allAccepted);
    onOpenChange(false);
  };

  const cookieSections = [
    {
      key: 'essential',
      title: 'Необходимые cookie',
      description: 'Эти файлы cookie необходимы для работы сайта и не могут быть отключены.',
      required: true,
    },
    {
      key: 'analytics',
      title: 'Аналитические cookie',
      description: 'Помогают нам понять, как вы используете сайт, чтобы улучшить его работу.',
      required: false,
    },
    {
      key: 'advertising',
      title: 'Рекламные cookie',
      description: 'Используются для показа более релевантной рекламы.',
      required: false,
    },
    {
      key: 'preferences',
      title: 'Пользовательские настройки',
      description: 'Сохраняют ваши предпочтения для более удобного использования сайта.',
      required: false,
    },
  ];

  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent 
        side="right" 
        className="w-full sm:max-w-md bg-dark-gray/95 backdrop-blur-lg border-l border-white/10 text-white overflow-y-auto"
      >
        <SheetHeader className="space-y-4 pb-6">
          <SheetTitle className="text-white text-xl font-semibold">
            Настройки cookie
          </SheetTitle>
          <SheetDescription className="text-gray-400 text-sm leading-relaxed">
            Управляйте настройками файлов cookie. Вы можете включить или отключить различные категории.
          </SheetDescription>
          <div className="text-gray-400 text-sm leading-relaxed">
            Подробнее о cookie читайте в{' '}
            <a 
              href="/cookie-policy" 
              className="text-accent-red underline hover:text-accent-red/80 transition-colors"
              target="_blank"
              rel="noopener noreferrer"
            >
              Политике cookie
            </a>.
          </div>
        </SheetHeader>

        <div className="space-y-4 py-6">
          {cookieSections.map((section) => (
            <div
              key={section.key}
              className="border border-white/10 rounded-lg bg-medium-gray/50"
            >
              <button
                onClick={() => toggleSection(section.key)}
                className="w-full p-4 flex items-center justify-between text-left hover:bg-white/5 transition-colors rounded-lg"
              >
                <div className="flex-1">
                  <h3 className="text-white font-medium mb-1">{section.title}</h3>
                  {section.required && (
                    <span className="text-green-400 text-sm">Всегда активно</span>
                  )}
                </div>
                <div className="flex items-center space-x-3">
                  <Switch
                    checked={cookiePrefs[section.key as keyof CookiePreferences]}
                    onCheckedChange={section.required ? undefined : (checked) => 
                      handleSwitchChange(section.key as keyof CookiePreferences, checked)
                    }
                    disabled={section.required}
                    className="data-[state=checked]:bg-green-500 data-[state=checked]:shadow-lg data-[state=checked]:shadow-green-500/25"
                  />
                  {expandedSections[section.key] ? (
                    <Minus className="h-4 w-4 text-gray-400" />
                  ) : (
                    <Plus className="h-4 w-4 text-gray-400" />
                  )}
                </div>
              </button>
              
              {expandedSections[section.key] && !section.required && (
                <div className="px-4 pb-4">
                  <p className="text-gray-400 text-sm">{section.description}</p>
                </div>
              )}
            </div>
          ))}
        </div>

        <SheetFooter className="pt-6 border-t border-white/10">
          <div className="flex gap-2 w-full">
            <Button
              onClick={handleConfirm}
              size="sm"
              className="flex-1 bg-white text-dark-gray hover:bg-gray-100 rounded-lg py-1.5 px-3 text-xs font-medium transition-all duration-300"
            >
              Сохранить настройки
            </Button>
            <Button
              onClick={handleAcceptAll}
              variant="secondary"
              size="sm"
              className="flex-1 rounded-lg py-1.5 px-3 text-xs font-medium"
            >
              Принять все
            </Button>
          </div>
        </SheetFooter>
      </SheetContent>
    </Sheet>
  );
};