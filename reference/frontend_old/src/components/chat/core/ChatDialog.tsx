import React, { useState, useEffect } from 'react';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { GlassButton } from '@/components/design-system/GlassButton';
import { GlassInput } from '@/components/design-system/GlassInput';
import { useToast } from '@/hooks/use-toast';
import { logger } from '@/utils/logger';
import type { Chat } from '@/types/realtime-chat';

interface ChatDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  chat: Chat | null;
  mode: 'rename' | 'edit';
  onUpdate: (chatId: string, name: string, description?: string) => Promise<void>;
}

const ChatDialog: React.FC<ChatDialogProps> = ({
  open,
  onOpenChange,
  chat,
  mode,
  onUpdate
}) => {
  const { toast } = useToast();
  const [loading, setLoading] = useState(false);
  const [name, setName] = useState('');
  const [description, setDescription] = useState('');

  useEffect(() => {
    if (open && chat) {
      setName(chat.name || '');
      setDescription((chat.metadata as any)?.description || '');
    }
  }, [open, chat]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!chat || !name.trim()) return;

    setLoading(true);
    try {
      if (mode === 'rename') {
        await onUpdate(chat.id, name.trim());
      } else {
        await onUpdate(chat.id, name.trim(), description.trim());
      }
      
      toast({
        title: "Успешно",
        description: mode === 'rename' ? "Название чата изменено" : "Чат обновлен",
        variant: "success",
      });
      onOpenChange(false);
    } catch (error) {
      logger.error('Error updating chat', error, { component: 'ChatDialog' });
      toast({
        title: "Ошибка",
        description: mode === 'rename' ? "Не удалось переименовать чат" : "Не удалось обновить чат",
        variant: "error",
      });
    } finally {
      setLoading(false);
    }
  };

  const dialogTitle = mode === 'rename' ? 'Переименовать чат' : 'Редактировать чат';

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="bg-card/95 backdrop-blur-xl border-white/20 shadow-2xl max-w-md">
        <DialogHeader>
          <DialogTitle className="text-foreground text-lg font-semibold">{dialogTitle}</DialogTitle>
        </DialogHeader>
        
        <form onSubmit={handleSubmit} className="space-y-6">
          <GlassInput
            label={mode === 'rename' ? 'Название чата' : 'Название чата *'}
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder={mode === 'rename' ? 'Введите новое название' : 'Введите название чата'}
            required
            autoFocus
          />
          
          {mode === 'edit' && (
            <GlassInput
              label="Описание чата"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="Краткое описание чата"
            />
          )}
          
          <div className="flex justify-end gap-3 pt-6">
            <GlassButton
              type="button"
              variant="secondary"
              onClick={() => onOpenChange(false)}
              disabled={loading}
            >
              Отмена
            </GlassButton>
            <GlassButton
              type="submit"
              variant="primary"
              disabled={loading || !name.trim()}
              loading={loading}
            >
              Сохранить
            </GlassButton>
          </div>
        </form>
      </DialogContent>
    </Dialog>
  );
};

export default ChatDialog;