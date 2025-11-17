import React, { useState } from 'react';
import { Label } from '@/components/ui/label';
import { RadioGroup, RadioGroupItem } from '@/components/ui/radio-group';
import { Dialog, DialogContent, DialogTrigger } from '@/components/ui/dialog';
import { FileUploadZone } from './FileUploadZone';
import { 
  AlignLeft, 
  AlignRight, 
  AlignVerticalJustifyCenter,
  AlignHorizontalJustifyCenter,
  Square, 
  RectangleVertical, 
  RectangleHorizontal 
} from 'lucide-react';
import { uploadImageToStorage, deleteImageFromStorage } from './ImageUploadService';
import { useToast } from '@/hooks/use-toast';

interface ImagePositionSelectorProps {
  position: 'left' | 'right' | 'top' | 'bottom';
  onPositionChange: (position: 'left' | 'right' | 'top' | 'bottom') => void;
  format: 'square' | 'vertical' | 'full-width';
  onFormatChange: (format: 'square' | 'vertical' | 'full-width') => void;
  imageUrl?: string;
  onImageChange: (url?: string) => void;
}

const POSITION_OPTIONS = [
  { value: 'left', icon: AlignLeft, label: 'Слева от текста' },
  { value: 'right', icon: AlignRight, label: 'Справа от текста' },
  { value: 'top', icon: AlignVerticalJustifyCenter, label: 'Над текстом' },
  { value: 'bottom', icon: AlignHorizontalJustifyCenter, label: 'Под текстом' },
] as const;

const FORMAT_OPTIONS = [
  { value: 'square', icon: Square, label: 'Квадрат' },
  { value: 'vertical', icon: RectangleVertical, label: 'Вертикальный' },
  { value: 'full-width', icon: RectangleHorizontal, label: 'Во всю ширину' },
] as const;

export const ImagePositionSelector: React.FC<ImagePositionSelectorProps> = ({
  position,
  onPositionChange,
  format,
  onFormatChange,
  imageUrl,
  onImageChange
}) => {
  const { toast } = useToast();
  const [isDialogOpen, setIsDialogOpen] = useState(false);

  const handleFileSelect = async (file: File) => {
    try {
      toast({
        title: "Загрузка изображения",
        description: "Пожалуйста, подождите...",
      });

      const publicUrl = await uploadImageToStorage(file);
      onImageChange(publicUrl);

      toast({
        title: "Изображение загружено",
        description: "Изображение успешно сохранено",
      });
    } catch (error) {
      
      toast({
        title: "Ошибка загрузки",
        description: "Не удалось загрузить изображение",
        variant: "error",
      });
    }
  };

  const handleRemoveImage = async () => {
    if (imageUrl) {
      try {
        await deleteImageFromStorage(imageUrl);
      } catch (error) {
        
      }
    }
    onImageChange(undefined);
  };

  return (
    <div className="space-y-4">
      {/* Upload Zone - Always Visible with Square Aspect Ratio */}
      <div className="space-y-3">
        <Label className="text-sm text-gray-400 mb-2 block">Загрузить изображение</Label>
        
        {imageUrl ? (
          <div className="relative">
            <Dialog open={isDialogOpen} onOpenChange={setIsDialogOpen}>
              <DialogTrigger asChild>
                <div className="relative w-24 h-24 rounded-lg overflow-hidden bg-dark-gray/50 border border-white/10 cursor-pointer hover:border-white/20 transition-colors">
                  <img
                    src={imageUrl}
                    alt="Preview"
                    className="w-full h-full object-cover"
                  />
                </div>
              </DialogTrigger>
              <DialogContent className="max-w-2xl">
                <div className="flex items-center justify-center p-4">
                  <img
                    src={imageUrl}
                    alt="Full size preview"
                    className="max-w-full max-h-[70vh] object-contain"
                  />
                </div>
              </DialogContent>
            </Dialog>
            
            <button
              onClick={handleRemoveImage}
              className="absolute -top-2 -right-2 w-6 h-6 bg-red-500 hover:bg-red-600 rounded-full flex items-center justify-center transition-colors text-white text-xs"
            >
              ×
            </button>
          </div>
        ) : (
          <div className="w-24 h-24">
            <FileUploadZone
              onFileSelect={handleFileSelect}
              onRemove={handleRemoveImage}
              currentImageUrl={imageUrl}
              className="h-full"
            />
          </div>
        )}
      </div>

      {/* Position and Format Options - Only show if image is uploaded */}
      {imageUrl && (
        <div className="grid grid-cols-2 gap-6 pt-2 border-t border-white/10">
          {/* Position Column */}
          <div className="space-y-3">
            <Label className="text-sm text-gray-400 mb-3 block">Положение картинки</Label>
            <RadioGroup
              value={position}
              onValueChange={(value) => onPositionChange(value as typeof position)}
              className="space-y-2"
            >
              {POSITION_OPTIONS.map(({ value, icon: Icon, label }) => (
                <div key={value} className="flex items-center space-x-2">
                  <RadioGroupItem value={value} id={`pos-${value}`} />
                  <Label 
                    htmlFor={`pos-${value}`} 
                    className="flex items-center gap-2 text-xs text-gray-300 cursor-pointer flex-1"
                  >
                    <Icon size={14} />
                    {label}
                  </Label>
                </div>
              ))}
            </RadioGroup>
          </div>

          {/* Format Column */}
          <div className="space-y-3">
            <Label className="text-sm text-gray-400 mb-3 block">Формат картинки</Label>
            <RadioGroup
              value={format}
              onValueChange={(value) => onFormatChange(value as typeof format)}
              className="space-y-2"
            >
              {FORMAT_OPTIONS.map(({ value, icon: Icon, label }) => (
                <div key={value} className="flex items-center space-x-2">
                  <RadioGroupItem value={value} id={`fmt-${value}`} />
                  <Label 
                    htmlFor={`fmt-${value}`} 
                    className="flex items-center gap-2 text-xs text-gray-300 cursor-pointer flex-1"
                  >
                    <Icon size={14} />
                    {label}
                  </Label>
                </div>
              ))}
            </RadioGroup>
          </div>
        </div>
      )}
    </div>
  );
};