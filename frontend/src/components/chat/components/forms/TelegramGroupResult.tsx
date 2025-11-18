import React, { useEffect } from 'react';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { GlassCard } from '@/components/design-system/GlassCard';
import { GlassButton } from '@/components/design-system/GlassButton';
import { CheckCircle, XCircle, Building, MessageCircle, Link, Copy } from 'lucide-react';
import { TelegramIcon } from '@/components/ui/TelegramIcon';
import { toast } from '@/hooks/use-toast';
import useSound from 'use-sound';

interface TelegramGroupResultData {
  success: boolean;
  group_id?: number;
  group_title?: string;
  invite_link?: string;
  bots_results?: Array<{
    username: string;
    title: string;
    status: string;
  }>;
  permissions_set?: boolean;
  topic_renamed?: boolean;
  photo_set?: boolean;
  metadata?: any;
  error?: string;
}

interface CompanyData {
  id: number;
  name: string;
  company_type: string;
}

interface TelegramGroupResultProps {
  isOpen: boolean;
  onClose: () => void;
  result: TelegramGroupResultData | null;
  companyData: CompanyData | null;
}

export const TelegramGroupResult: React.FC<TelegramGroupResultProps> = ({
  isOpen,
  onClose,
  result,
  companyData
}) => {
  const [playSuccess] = useSound('/sounds/notification.mp3', { volume: 0.5 });

  // Play sound when modal opens with result
  useEffect(() => {
    if (isOpen) {
      if (result?.success) {
        setTimeout(() => playSuccess(), 300);
      } else {
        // Play error sound for failed operations
        setTimeout(() => playSuccess(), 300);
      }
    }
  }, [isOpen, result, playSuccess]);

  const copyInviteLink = async () => {
    if (result?.invite_link) {
      try {
        await navigator.clipboard.writeText(result.invite_link);
        toast({
          title: 'Ссылка скопирована',
          variant: "success"
        });
      } catch (error) {
        toast({
          title: 'Ошибка копирования ссылки',
          variant: "error"
        });
      }
    }
  };

  const openTelegramGroup = () => {
    if (result?.invite_link) {
      window.open(result.invite_link, '_blank');
    }
  };

  if (!result) return null;

  return (
    <Dialog open={isOpen} onOpenChange={(open) => !open && onClose()}>
      <DialogContent 
        className="max-w-3xl bg-card/98 backdrop-blur-xl border-white/30 shadow-2xl animate-scale-in" 
        onEscapeKeyDown={(e) => e.preventDefault()} 
        onPointerDownOutside={(e) => e.preventDefault()}
      >
        <DialogHeader className="pb-0">
          <div className="flex flex-col items-center text-center space-y-4">
            {result.success ? (
              <CheckCircle className="h-16 w-16 text-green-500" />
            ) : (
              <XCircle className="h-16 w-16 text-destructive" />
            )}
            <DialogTitle className="text-2xl font-bold text-foreground">
              {result.success ? "Компания и группа успешно созданы!" : "Произошла ошибка"}
            </DialogTitle>
          </div>
        </DialogHeader>

        <div className="space-y-6">
          {result.success ? (
            <>
              {/* Company Information */}
              {companyData && (
                <div className="space-y-3">
                  <div className="flex items-center gap-3">
                    <Building className="h-5 w-5 text-primary" />
                    <h3 className="text-lg font-semibold text-foreground">
                      Информация о компании
                    </h3>
                  </div>
                  <div className="grid grid-cols-1 md:grid-cols-3 gap-4 p-4 bg-card/50 rounded-lg border border-border/50">
                    <div>
                      <span className="text-sm text-muted-foreground">Название:</span>
                      <p className="font-medium text-foreground">{companyData.name}</p>
                    </div>
                    <div>
                      <span className="text-sm text-muted-foreground">Тип:</span>
                      <p className="font-medium text-foreground">{companyData.company_type === 'project' ? 'Проект' : 'Компания'}</p>
                    </div>
                    <div>
                      <span className="text-sm text-muted-foreground">ID:</span>
                      <p className="font-medium text-foreground">{companyData.id}</p>
                    </div>
                  </div>
                </div>
              )}

              {/* Telegram Group Information */}
              {result.group_id && (
                <div className="space-y-3">
                  <div className="flex items-center gap-3">
                    <MessageCircle className="h-5 w-5 text-primary" />
                    <h3 className="text-lg font-semibold text-foreground">
                      Telegram группа
                    </h3>
                  </div>
                  <div className="space-y-4 p-4 bg-card/50 rounded-lg border border-border/50">
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                      <div>
                        <span className="text-sm text-muted-foreground">Название группы:</span>
                        <p className="font-medium text-foreground">{result.group_title}</p>
                      </div>
                      <div>
                        <span className="text-sm text-muted-foreground">Telegram ID:</span>
                        <p className="font-medium text-foreground">{result.group_id}</p>
                      </div>
                    </div>
                    
                    {/* Bots Results */}
                    {result.bots_results && result.bots_results.length > 0 && (
                      <div className="space-y-2">
                        <span className="text-sm text-muted-foreground">Добавленные боты:</span>
                        <div className="space-y-1">
                          {result.bots_results.map((bot, index) => (
                            <div key={index} className="flex items-center gap-2 text-sm">
                              <div className={`w-2 h-2 rounded-full ${bot.status === 'success' ? 'bg-green-500' : 'bg-red-500'}`}></div>
                              <span className="text-foreground">{bot.title} (@{bot.username})</span>
                            </div>
                          ))}
                        </div>
                      </div>
                    )}

                    {/* Settings Status */}
                    <div className="space-y-1">
                      <span className="text-sm text-muted-foreground">Настройки:</span>
                      <div className="flex flex-wrap gap-4 text-sm">
                        {result.permissions_set && (
                          <div className="flex items-center gap-2 text-green-600">
                            <CheckCircle className="h-3 w-3" />
                            <span>Права настроены</span>
                          </div>
                        )}
                        {result.topic_renamed && (
                          <div className="flex items-center gap-2 text-green-600">
                            <CheckCircle className="h-3 w-3" />
                            <span>Топик переименован</span>
                          </div>
                        )}
                        {result.photo_set && (
                          <div className="flex items-center gap-2 text-green-600">
                            <CheckCircle className="h-3 w-3" />
                            <span>Фото установлено</span>
                          </div>
                        )}
                      </div>
                    </div>
                  </div>
                </div>
              )}

              {/* Invite Link Section */}
              {result.invite_link && (
                <div className="space-y-3">
                  <div className="flex items-center gap-3">
                    <Link className="h-5 w-5 text-primary" />
                    <h3 className="text-lg font-semibold text-foreground">
                      Ссылка приглашения
                    </h3>
                  </div>
                  <div className="p-4 bg-card/50 rounded-lg border border-border/50">
                    <div className="flex items-center gap-2 mb-2">
                      <span className="text-sm text-muted-foreground">Пригласительная ссылка:</span>
                      <GlassButton
                        variant="outline"
                        onClick={copyInviteLink}
                        className="flex items-center gap-2 px-3 py-1 text-xs"
                      >
                        <Copy className="h-3 w-3" />
                        Копировать
                      </GlassButton>
                    </div>
                    <p className="text-sm text-foreground break-all bg-muted/30 p-2 rounded border font-mono">
                      {result.invite_link}
                    </p>
                  </div>
                </div>
              )}
            </>
          ) : (
            <div className="text-center space-y-4">
              <p className="text-muted-foreground text-lg">
                {result.error || "Произошла неизвестная ошибка"}
              </p>
            </div>
          )}

          {/* Action Buttons */}
          <div className="flex justify-between items-center gap-3 pt-6 border-t border-border/50">
            {result.success && result.invite_link && (
              <GlassButton
                variant="primary"
                onClick={openTelegramGroup}
                className="flex items-center gap-2 px-6 py-3"
              >
                <TelegramIcon className="h-4 w-4" />
                Открыть группу
              </GlassButton>
            )}
            <div className="flex-1"></div>
            <GlassButton
              variant="secondary"
              onClick={onClose}
              className="px-6 py-3"
            >
              Закрыть
            </GlassButton>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
};