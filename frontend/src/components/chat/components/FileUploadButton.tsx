import React, { useRef } from 'react';
import { Button } from '@/components/ui/button';
import { Paperclip } from 'lucide-react';
import { useRealtimeChatContext } from '@/contexts/RealtimeChatContext';
import { useToast } from '@/hooks/use-toast';
import { usePlatform } from '@/contexts/PlatformContext';

interface FileUploadButtonProps {
  disabled?: boolean;
}

export function FileUploadButton({ disabled }: FileUploadButtonProps) {
  const fileInputRef = useRef<HTMLInputElement>(null);
  const { sendFile } = useRealtimeChatContext();
  const { toast } = useToast();
  const { isLightTheme } = usePlatform();

  const handleFileSelect = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const files = event.target.files;
    if (!files || files.length === 0) return;

    const file = files[0];
    
    // Проверка размера файла (максимум 10MB)
    const maxSize = 10 * 1024 * 1024; // 10MB
    if (file.size > maxSize) {
      toast({
        title: "Файл слишком большой",
        description: "Максимальный размер файла 10MB",
        variant: "error"
      });
      return;
    }

    try {
      await sendFile(file);
      toast({
        title: "Файл отправлен",
        description: `Файл "${file.name}" успешно отправлен`,
      });
    } catch (error) {
      
      toast({
        title: "Ошибка отправки",
        description: "Не удалось отправить файл",
        variant: "error"
      });
    }

    // Очищаем input для возможности повторного выбора того же файла
    if (fileInputRef.current) {
      fileInputRef.current.value = '';
    }
  };

  const openFileDialog = () => {
    fileInputRef.current?.click();
  };

  return (
    <>
      <input
        ref={fileInputRef}
        type="file"
        className="hidden"
        onChange={handleFileSelect}
        accept="*/*"
      />
      <Button
        variant="ghost"
        size="icon"
        className={`rounded-full h-11 w-11 transition-all ${
          isLightTheme
            ? 'text-gray-500 hover:text-accent-red bg-[#e8e8e8] hover:bg-accent-red/10 border border-gray-300 hover:border-accent-red/30'
            : 'text-gray-400 hover:text-accent-red hover:bg-accent-red/10 border border-transparent hover:border-accent-red/30'
        }`}
        onClick={openFileDialog}
        disabled={disabled}
      >
        <Paperclip size={22} />
      </Button>
    </>
  );
}