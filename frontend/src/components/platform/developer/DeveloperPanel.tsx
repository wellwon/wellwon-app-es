import React, { useState } from 'react';
import { useAuth } from '@/contexts/AuthContext';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Card } from '@/components/ui/card';
import { Settings, Move, X, Minimize2, Maximize2, Info, CheckCircle, AlertTriangle, XCircle, Bell, Database, BarChart3 } from 'lucide-react';
import { useDraggable } from '@/hooks/useDraggable';
import { useToast } from '@/hooks/use-toast';
import { AppConfirmDialog } from '@/components/shared';
import { makeStoragePublic, backfillMedia, retryProxyFiles, getFileStats } from '@/utils/testStoragePublic';

type Section = 'toasts' | 'position' | 'dialogs' | 'media';
const DeveloperPanel: React.FC = () => {
  const {
    profile,
    user
  } = useAuth();
  const { toast } = useToast();
  const [isMinimized, setIsMinimized] = useState(true);
  const [isVisible, setIsVisible] = useState(true);
  const [activeSection, setActiveSection] = useState<Section>('toasts');
  const [mediaLoading, setMediaLoading] = useState<string | null>(null);
  
  // Dialog states
  const [showBaseDialog, setShowBaseDialog] = useState(false);
  const [showDestructiveDialog, setShowDestructiveDialog] = useState(false);
  const [showCreateCompanyDialog, setShowCreateCompanyDialog] = useState(false);
  const [showNewChatDialog, setShowNewChatDialog] = useState(false);
  const {
    elementRef,
    position,
    isDragging,
    resetPosition,
    handlers
  } = useDraggable({
    storageKey: 'developer-panel-position'
  });

  // Set default position if not set
  const finalPosition = position.x === 0 && position.y === 0 ? {
    x: 20,
    y: 100
  } : position;

  // Show for developers and specific test user IDs in development mode
  const allowedDeveloperUserIds = [
  '58a589dd-6f1b-493b-9966-a595dd438015' // oleg.admin@test.com
  ];
  const isDeveloper = profile?.is_developer;
  const isAllowedTestUser = user?.id && allowedDeveloperUserIds.includes(user.id);
  if (!profile || !isDeveloper && !isAllowedTestUser || process.env.NODE_ENV !== 'development' || !isVisible) {
    return null;
  }
  if (isMinimized) {
    return <div ref={elementRef} className="fixed z-[9999] select-none" style={{
      left: finalPosition.x,
      top: finalPosition.y,
      transform: isDragging ? 'scale(1.02)' : 'scale(1)',
      transition: isDragging ? 'none' : 'transform 0.2s ease'
    }}>
        <Card className="bg-gray-900/95 backdrop-blur-md border-white/20 w-fit">
          <div className="flex items-center gap-2 p-2 cursor-move" {...handlers}>
            <Settings className="h-4 w-4 text-accent-red" />
            <span className="text-white text-xs font-medium">Tools</span>
            <Button variant="ghost" size="icon" className="h-6 w-6 text-gray-400 hover:text-white ml-1" onClick={() => setIsMinimized(false)}>
              <Maximize2 className="h-3 w-3" />
            </Button>
          </div>
        </Card>
      </div>;
  }
  return <div ref={elementRef} className="fixed z-[9999] select-none" style={{
    left: finalPosition.x,
    top: finalPosition.y,
    transform: isDragging ? 'scale(1.02)' : 'scale(1)',
    transition: isDragging ? 'none' : 'transform 0.2s ease'
  }}>
      <Card className="bg-gray-900/95 backdrop-blur-md border-white/20 w-[500px]">
        {/* Header */}
        <div className="flex items-center justify-between p-3 border-b border-white/10 cursor-move" {...handlers}>
          <div className="flex items-center gap-2">
            <Settings className="h-4 w-4 text-accent-red" />
            <span className="text-white font-medium">Панель разработчика</span>
            <Badge variant="outline" className="text-xs text-accent-red border-accent-red/50">
              DEV
            </Badge>
          </div>
          
          <div className="flex items-center gap-1">
            <Button variant="ghost" size="icon" className="h-6 w-6 text-gray-400 hover:text-white" onClick={() => setIsMinimized(true)}>
              <Minimize2 className="h-3 w-3" />
            </Button>
            <Button variant="ghost" size="icon" className="h-6 w-6 text-gray-400 hover:text-white" onClick={() => setIsVisible(false)}>
              <X className="h-3 w-3" />
            </Button>
          </div>
        </div>

        {/* Content - always visible when not minimized */}
        <div className="p-4 space-y-4">
          {/* Mini icon navigation */}
          <div className="flex items-center gap-2">
            <Button
              size="icon"
              variant="outline"
              className={`h-8 w-8 ${activeSection === 'toasts' ? 'bg-blue-500/10' : ''} border-blue-500/50 text-blue-500 hover:bg-blue-500/10`}
              onClick={() => setActiveSection('toasts')}
              title="Уведомления"
            >
              <Bell className="h-4 w-4" />
            </Button>
            <Button
              size="icon"
              variant="outline"
              className={`h-8 w-8 ${activeSection === 'position' ? 'bg-white/10' : ''} border-white/30 text-gray-200 hover:bg-white/10`}
              onClick={() => setActiveSection('position')}
              title="Позиция панели"
            >
              <Move className="h-4 w-4" />
            </Button>
            <Button
              size="icon"
              variant="outline"
              className={`h-8 w-8 ${activeSection === 'dialogs' ? 'bg-purple-500/10' : ''} border-purple-500/50 text-purple-500 hover:bg-purple-500/10`}
              onClick={() => setActiveSection('dialogs')}
              title="Диалоговые окна"
            >
              <Settings className="h-4 w-4" />
            </Button>
            <Button
              size="icon"
              variant="outline"
              className={`h-8 w-8 ${activeSection === 'media' ? 'bg-orange-500/10' : ''} border-orange-500/50 text-orange-500 hover:bg-orange-500/10`}
              onClick={() => setActiveSection('media')}
              title="Медиа файлы"
            >
              <Database className="h-4 w-4" />
            </Button>
          </div>

          {/* Sections */}
          {activeSection === 'toasts' && (
            <div className="space-y-2">
              <div className="text-sm font-medium text-white">Тестирование тостов</div>
              <div className="flex gap-2">
                <Button 
                  size="icon" 
                  variant="outline" 
                  className="h-8 w-8 border-blue-500/50 text-blue-500 hover:bg-blue-500/10"
                  onClick={() => toast({ title: "Информация", description: "Полезная информация", variant: "info" })}
                >
                  <Info className="h-4 w-4" />
                </Button>
                <Button 
                  size="icon" 
                  variant="outline" 
                  className="h-8 w-8 border-green-500/50 text-green-500 hover:bg-green-500/10"
                  onClick={() => toast({ title: "Успех!", description: "Операция выполнена", variant: "success" })}
                >
                  <CheckCircle className="h-4 w-4" />
                </Button>
                <Button 
                  size="icon" 
                  variant="outline" 
                  className="h-8 w-8 border-yellow-500/50 text-yellow-500 hover:bg-yellow-500/10"
                  onClick={() => toast({ title: "Предупреждение", description: "Будьте осторожны", variant: "warning" })}
                >
                  <AlertTriangle className="h-4 w-4" />
                </Button>
                <Button 
                  size="icon" 
                  variant="outline" 
                  className="h-8 w-8 border-red-500/50 text-red-500 hover:bg-red-500/10"
                  onClick={() => toast({ title: "Ошибка", description: "Что-то пошло не так", variant: "error" })}
                >
                  <XCircle className="h-4 w-4" />
                </Button>
              </div>
            </div>
          )}

          {activeSection === 'position' && (
            <div className="pt-2">
              <div className="flex items-center justify-between text-xs text-gray-400">
                <span>Позиция панели</span>
                <Button
                  variant="ghost"
                  size="sm"
                  className="h-6 text-xs text-gray-400 hover:text-white px-2"
                  onClick={() => {
                    localStorage.removeItem('developer-panel-position');
                    resetPosition();
                  }}
                >
                  Сбросить позицию
                </Button>
              </div>
            </div>
          )}

          {activeSection === 'dialogs' && (
            <div className="space-y-2">
              <div className="text-sm font-medium text-white">Диалоговые окна</div>
              <div className="grid grid-cols-2 gap-2">
                <Button 
                  size="sm" 
                  variant="outline" 
                  className="h-8 border-purple-500/50 text-purple-500 hover:bg-purple-500/10 text-xs"
                  onClick={() => setShowBaseDialog(true)}
                >
                  Базовый
                </Button>
                <Button 
                  size="sm" 
                  variant="outline" 
                  className="h-8 border-red-500/50 text-red-500 hover:bg-red-500/10 text-xs"
                  onClick={() => setShowDestructiveDialog(true)}
                >
                  Удаление
                </Button>
                <Button 
                  size="sm" 
                  variant="outline" 
                  className="h-8 border-blue-500/50 text-blue-500 hover:bg-blue-500/10 text-xs"
                  onClick={() => setShowCreateCompanyDialog(true)}
                >
                  Компания
                </Button>
                <Button 
                  size="sm" 
                  variant="outline" 
                  className="h-8 border-green-500/50 text-green-500 hover:bg-green-500/10 text-xs"
                  onClick={() => setShowNewChatDialog(true)}
                >
                  Чат
                </Button>
              </div>
            </div>
          )}

          {activeSection === 'media' && (
            <div className="space-y-3">
              <div className="text-sm font-medium text-white">Управление медиа-файлами</div>
              <div className="space-y-2">
                <Button 
                  size="sm" 
                  variant="outline" 
                  className="w-full h-8 border-orange-500/50 text-orange-500 hover:bg-orange-500/10 text-xs justify-start"
                  onClick={async () => {
                    setMediaLoading('storage');
                    try {
                      const result = await makeStoragePublic();
                      toast({
                        title: result.success ? "Хранилище настроено" : "Ошибка настройки",
                        description: result.success ? "Bucket chat-files теперь публичный" : "Не удалось настроить хранилище",
                        variant: result.success ? "success" : "error"
                      });
                    } finally {
                      setMediaLoading(null);
                    }
                  }}
                  disabled={mediaLoading === 'storage'}
                >
                  {mediaLoading === 'storage' ? "..." : "Настроить хранилище"}
                </Button>
                <Button 
                  size="sm" 
                  variant="outline" 
                  className="w-full h-8 border-blue-500/50 text-blue-500 hover:bg-blue-500/10 text-xs justify-start"
                  onClick={async () => {
                    setMediaLoading('backfill');
                    try {
                      const result = await backfillMedia();
                      toast({
                        title: result.success ? "Backfill завершен" : "Ошибка backfill",
                        description: result.success ? "Медиа-файлы обработаны" : "Не удалось обработать файлы",
                        variant: result.success ? "success" : "error"
                      });
                    } finally {
                      setMediaLoading(null);
                    }
                  }}
                  disabled={mediaLoading === 'backfill'}
                >
                  {mediaLoading === 'backfill' ? "..." : "Backfill медиа"}
                </Button>
                <Button 
                  size="sm" 
                  variant="outline" 
                  className="w-full h-8 border-yellow-500/50 text-yellow-500 hover:bg-yellow-500/10 text-xs justify-start"
                  onClick={async () => {
                    setMediaLoading('retry');
                    try {
                      const result = await retryProxyFiles();
                      toast({
                        title: result.success ? "Retry завершен" : "Ошибка retry",
                        description: result.success ? "Proxy файлы повторно обработаны" : "Не удалось обработать proxy файлы",
                        variant: result.success ? "success" : "error"
                      });
                    } finally {
                      setMediaLoading(null);
                    }
                  }}
                  disabled={mediaLoading === 'retry'}
                >
                  {mediaLoading === 'retry' ? "..." : "Retry proxy файлы"}
                </Button>
                <Button 
                  size="sm" 
                  variant="outline" 
                  className="w-full h-8 border-green-500/50 text-green-500 hover:bg-green-500/10 text-xs justify-start"
                  onClick={async () => {
                    setMediaLoading('stats');
                    try {
                      const result = await getFileStats();
                      if (result.success && result.stats) {
                        toast({
                          title: "Статистика файлов",
                          description: `Всего: ${result.stats.total}, Сохранено: ${result.stats.stored}, Proxy: ${result.stats.proxy}`,
                          variant: "info"
                        });
                      } else {
                        toast({
                          title: "Ошибка получения статистики",
                          description: "Не удалось получить данные",
                          variant: "error"
                        });
                      }
                    } finally {
                      setMediaLoading(null);
                    }
                  }}
                  disabled={mediaLoading === 'stats'}
                >
                  <BarChart3 className="h-3 w-3 mr-1" />
                  {mediaLoading === 'stats' ? "..." : "Показать статистику"}
                </Button>
              </div>
            </div>
          )}
        </div>
        
        {/* Dialog Examples */}
        <AppConfirmDialog
          open={showBaseDialog}
          onOpenChange={setShowBaseDialog}
          onConfirm={() => toast({ title: "Подтверждено", description: "Базовое диалоговое окно", variant: "info" })}
          title="Базовое диалоговое окно"
          description="Это стандартное диалоговое окно для подтверждения действий."
          icon={Info}
        />
        
        <AppConfirmDialog
          open={showDestructiveDialog}
          onOpenChange={setShowDestructiveDialog}
          onConfirm={() => toast({ title: "Удалено", description: "Элемент был удален", variant: "error" })}
          title="Удаление элемента"
          description="Вы уверены, что хотите удалить этот элемент? Это действие нельзя отменить."
          confirmText="Удалить"
          variant="destructive"
          icon={XCircle}
        />
        
        <AppConfirmDialog
          open={showCreateCompanyDialog}
          onOpenChange={setShowCreateCompanyDialog}
          onConfirm={() => toast({ title: "Создано", description: "Компания успешно создана", variant: "success" })}
          title="Создание новой компании"
          description="Вы точно хотите создать ещё одну компанию?"
          confirmText="Создать"
          icon={Settings}
        />
        
        <AppConfirmDialog
          open={showNewChatDialog}
          onOpenChange={setShowNewChatDialog}
          onConfirm={() => toast({ title: "Создан", description: "Новый чат создан", variant: "success" })}
          title="Создание нового диалога"
          description="Вы уверены, что хотите создать новую тему?"
          confirmText="Создать"
          icon={Bell}
        />
      </Card>
    </div>;
};
export default DeveloperPanel;