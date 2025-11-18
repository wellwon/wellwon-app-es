import React, { useRef } from 'react';
import { Button } from '@/components/ui/button';
import { Image } from 'lucide-react';
import { useRealtimeChatContext } from '@/contexts/RealtimeChatContext';
import { useToast } from '@/hooks/use-toast';

interface ImageUploadButtonProps {
  disabled?: boolean;
}

export function ImageUploadButton({ disabled }: ImageUploadButtonProps) {
  const fileInputRef = useRef<HTMLInputElement>(null);
  const { sendFile } = useRealtimeChatContext();
  const { toast } = useToast();

  const handleImageSelect = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const files = event.target.files;
    if (!files || files.length === 0) return;

    const file = files[0];
    
    // Проверка типа файла
    if (!file.type.startsWith('image/')) {
      toast({
        title: "Неверный тип файла",
        description: "Можно загружать только изображения",
        variant: "error"
      });
      return;
    }

    // Проверка размера файла (максимум 5MB для изображений)
    const maxSize = 5 * 1024 * 1024; // 5MB
    if (file.size > maxSize) {
      toast({
        title: "Изображение слишком большое",
        description: "Максимальный размер изображения 5MB",
        variant: "error"
      });
      return;
    }

    try {
      await sendFile(file);
      toast({
        title: "Изображение отправлено",
        description: `Изображение "${file.name}" успешно отправлено`,
      });
    } catch (error) {
      
      toast({
        title: "Ошибка отправки",
        description: "Не удалось отправить изображение",
        variant: "error"
      });
    }

    // Очищаем input
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
        onChange={handleImageSelect}
        accept="image/*"
      />
      <Button 
        variant="ghost" 
        size="icon" 
        className="text-text-gray-400 hover:text-white hover:bg-white/10 rounded-full h-8 w-8"
        onClick={openFileDialog}
        disabled={disabled}
      >
        <Image size={16} />
      </Button>
    </>
  );
}