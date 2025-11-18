import React from 'react';
import { Loader2, CheckCircle, X, Copy, ExternalLink, Building2 } from 'lucide-react';
import { GlassButton } from '@/components/design-system';
import { useToast } from '@/hooks/use-toast';

interface LoadingOverlayProps {
  isVisible: boolean;
  message: string;
  progress: number;
  steps: string[];
  currentStep: number;
  stepStatuses: ('pending' | 'loading' | 'success' | 'error')[];
  errorMessage?: string;
  resultData?: {
    companyName?: string;
    telegramGroup?: {
      title: string;
      link: string;
      qrCodeUrl?: string;
    };
  };
  onClose?: () => void;
  embedded?: boolean;
}

export const LoadingOverlay: React.FC<LoadingOverlayProps> = ({
  isVisible,
  message,
  progress,
  steps,
  currentStep,
  stepStatuses,
  errorMessage,
  resultData,
  onClose,
  embedded = false
}) => {
  const { toast } = useToast();
  
  if (!isVisible) return null;

  const handleCopyLink = () => {
    if (resultData?.telegramGroup?.link) {
      navigator.clipboard.writeText(resultData.telegramGroup.link);
      toast({
        title: "Ссылка скопирована",
        variant: "success"
      });
    }
  };

  const getStepStatusCircle = (status: 'pending' | 'loading' | 'success' | 'error') => {
    switch (status) {
      case 'pending':
        return <div className="w-4 h-4 rounded-full bg-transparent border-2 border-muted-foreground" />;
      case 'loading':
        return <div className="w-4 h-4 rounded-full bg-primary animate-pulse" />;
      case 'success':
        return <div className="w-4 h-4 rounded-full bg-green-400" />;
      case 'error':
        return <div className="w-4 h-4 rounded-full bg-red-400" />;
      default:
        return <div className="w-4 h-4 rounded-full bg-transparent border-2 border-muted-foreground" />;
    }
  };

  return (
    <div className={embedded ? "" : "fixed inset-0 bg-black/80 backdrop-blur-sm z-50 flex items-center justify-center"}>
      <div className={embedded ? "w-full bg-glass-surface/30 border border-glass-border rounded-lg p-6" : "bg-card/95 backdrop-blur-xl border border-white/20 rounded-lg w-full mx-4 shadow-2xl max-w-lg p-8"}>
        <div className="flex flex-col items-center space-y-6">
          {/* Иконка - всегда статичная */}
          <div className="relative">
            <Building2 className="h-12 w-12 text-primary" />
          </div>
          
          {/* Заголовок - всегда статичный */}
          <div className="text-center">
            <h3 className="text-lg font-semibold text-foreground">
              Создание компании и Telegram группы
            </h3>
          </div>
          
          {/* Progress Bar - всегда видимый */}
          <div className="w-full bg-glass-surface/50 rounded-full h-3">
            <div 
              className="bg-primary h-3 rounded-full transition-all duration-500"
              style={{ width: `${Math.max(progress, 10)}%` }}
            ></div>
          </div>
          
          {/* Steps - всегда отображаются */}
          <div className="space-y-3 w-full">
            {steps.map((step, index) => {
              const status = stepStatuses[index] || 'pending';
              return (
                <div 
                  key={index}
                  className="flex items-center gap-3 p-3 rounded-lg bg-glass-surface/20 transition-all duration-300"
                >
                  {getStepStatusCircle(status)}
                  <span className={`text-sm font-medium ${
                    status === 'success' ? 'text-green-400' :
                    status === 'error' ? 'text-red-400' :
                    status === 'loading' ? 'text-primary' :
                    'text-muted-foreground'
                  }`}>
                    {step}
                  </span>
                </div>
              );
            })}
          </div>

          {/* Error Section - показываем если есть ошибка */}
          {errorMessage && (
            <div className="w-full bg-red-500/10 border border-red-500/20 rounded-lg p-4">
              <div className="flex items-center gap-2 mb-2">
                <X className="h-4 w-4 text-red-400" />
                <h4 className="font-medium text-red-400">
                  Ошибка
                </h4>
              </div>
              <p className="text-sm text-red-300">
                {errorMessage}
              </p>
            </div>
          )}

          {/* Results Section - показываем если есть результат */}
          {resultData && (
            <div className="w-full space-y-4">
              {resultData.companyName && (
                <div className="bg-green-500/10 border border-green-500/20 rounded-lg p-4">
                  <div className="flex items-center gap-2 mb-2">
                    <CheckCircle className="h-4 w-4 text-green-400" />
                    <h4 className="font-medium text-green-400">
                      Компания создана
                    </h4>
                  </div>
                  <p className="text-sm text-green-300">
                    {resultData.companyName}
                  </p>
                </div>
              )}
              
              {resultData.telegramGroup && (
                <div className="bg-glass-surface/30 rounded-lg p-4 space-y-3">
                  <h4 className="font-medium text-foreground">
                    Telegram группа
                  </h4>
                  
                  <div className="space-y-3">
                    <p className="text-sm text-muted-foreground">
                      <strong>Название:</strong> {resultData.telegramGroup.title}
                    </p>
                    
                    <div className="flex items-center gap-2">
                      <input
                        type="text"
                        value={resultData.telegramGroup.link}
                        readOnly
                        className="flex-1 bg-background/50 border border-border rounded px-3 py-2 text-sm"
                      />
                      <GlassButton
                        variant="outline"
                        size="sm"
                        onClick={handleCopyLink}
                      >
                        <Copy className="h-4 w-4" />
                      </GlassButton>
                    </div>
                    
                    {resultData.telegramGroup.qrCodeUrl && (
                      <div className="text-center">
                        <img
                          src={resultData.telegramGroup.qrCodeUrl}
                          alt="QR Code"
                          className="mx-auto w-32 h-32 border border-border rounded"
                        />
                      </div>
                    )}
                    
                    <GlassButton
                      variant="outline"
                      size="sm"
                      className="w-full"
                      onClick={() => window.open(resultData.telegramGroup?.link, '_blank')}
                    >
                      <ExternalLink className="h-4 w-4 mr-2" />
                      Открыть группу
                    </GlassButton>
                  </div>
                </div>
              )}
            </div>
          )}
          
          {/* Close button - показываем если есть ошибка или результат */}
          {(errorMessage || resultData) && onClose && (
            <GlassButton
              variant="secondary"
              onClick={onClose}
              className="w-full"
            >
              {errorMessage ? 'Понятно' : 'Закрыть'}
            </GlassButton>
          )}
        </div>
      </div>
    </div>
  );
};