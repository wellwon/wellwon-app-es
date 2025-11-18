import React, { useState, useRef } from 'react';
import { Button } from '@/components/ui/button';
import { Progress } from '@/components/ui/progress';
import { X, Upload, FileText, Image as ImageIcon } from 'lucide-react';
import { useRealtimeChatContext } from '@/contexts/RealtimeChatContext';

interface FilePreview {
  file: File;
  preview?: string;
  type: 'image' | 'document';
}

interface EnhancedFileUploadProps {
  replyToId?: string;
}

export function EnhancedFileUpload({ replyToId }: EnhancedFileUploadProps) {
  const [files, setFiles] = useState<FilePreview[]>([]);
  const [isUploading, setIsUploading] = useState(false);
  const [uploadProgress, setUploadProgress] = useState(0);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const { sendFile } = useRealtimeChatContext();

  const handleFileSelect = (selectedFiles: FileList | null) => {
    if (!selectedFiles) return;

    const newFiles: FilePreview[] = [];
    
    Array.from(selectedFiles).forEach((file) => {
      const isImage = file.type.startsWith('image/');
      const filePreview: FilePreview = {
        file,
        type: isImage ? 'image' : 'document'
      };

      if (isImage) {
        const reader = new FileReader();
        reader.onload = (e) => {
          filePreview.preview = e.target?.result as string;
          setFiles(prev => [...prev.filter(f => f !== filePreview), filePreview]);
        };
        reader.readAsDataURL(file);
      }

      newFiles.push(filePreview);
    });

    setFiles(prev => [...prev, ...newFiles]);
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    handleFileSelect(e.dataTransfer.files);
  };

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
  };

  const removeFile = (index: number) => {
    setFiles(prev => prev.filter((_, i) => i !== index));
  };

  const uploadFiles = async () => {
    if (files.length === 0) return;

    setIsUploading(true);
    setUploadProgress(0);

    try {
      for (let i = 0; i < files.length; i++) {
        const { file } = files[i];
        await sendFile(file, replyToId);
        setUploadProgress(((i + 1) / files.length) * 100);
      }
      
      setFiles([]);
    } catch (error) {
      
      alert('Не удалось загрузить файлы');
    } finally {
      setIsUploading(false);
      setUploadProgress(0);
    }
  };

  if (files.length === 0) {
    return (
      <>
        <input
          ref={fileInputRef}
          type="file"
          multiple
          className="hidden"
          onChange={(e) => handleFileSelect(e.target.files)}
          accept="image/*,application/pdf,.doc,.docx,.txt"
        />
        <Button
          size="sm"
          variant="ghost"
          onClick={() => fileInputRef.current?.click()}
          className="h-8 w-8 p-0 text-muted-foreground hover:text-foreground"
        >
          <Upload size={16} />
        </Button>
      </>
    );
  }

  return (
    <div className="space-y-3">
      {/* File Previews */}
      <div 
        className="border-2 border-dashed border-muted-foreground/25 rounded-lg p-4 space-y-2"
        onDrop={handleDrop}
        onDragOver={handleDragOver}
      >
        {files.map((filePreview, index) => (
          <div key={index} className="flex items-center gap-3 p-2 bg-muted/50 rounded">
            {filePreview.type === 'image' && filePreview.preview ? (
              <img 
                src={filePreview.preview} 
                alt={filePreview.file.name}
                className="w-12 h-12 object-cover rounded"
              />
            ) : (
              <div className="w-12 h-12 bg-muted rounded flex items-center justify-center">
                {filePreview.type === 'image' ? (
                  <ImageIcon size={20} />
                ) : (
                  <FileText size={20} />
                )}
              </div>
            )}
            
            <div className="flex-1 min-w-0">
              <div className="font-medium text-sm truncate">
                {filePreview.file.name}
              </div>
              <div className="text-xs text-muted-foreground">
                {Math.round(filePreview.file.size / 1024)} KB
              </div>
            </div>
            
            <Button
              size="sm"
              variant="ghost"
              onClick={() => removeFile(index)}
              className="h-6 w-6 p-0"
            >
              <X size={12} />
            </Button>
          </div>
        ))}
        
        <div className="text-center text-sm text-muted-foreground">
          Перетащите файлы сюда или нажмите для выбора
        </div>
      </div>

      {/* Upload Progress */}
      {isUploading && (
        <div className="space-y-2">
          <Progress value={uploadProgress} className="w-full" />
          <div className="text-sm text-center text-muted-foreground">
            Загружается... {Math.round(uploadProgress)}%
          </div>
        </div>
      )}

      {/* Upload Controls */}
      <div className="flex gap-2">
        <Button
          onClick={uploadFiles}
          disabled={isUploading}
          size="sm"
          className="flex-1"
        >
          {isUploading ? 'Загружается...' : `Отправить ${files.length} файл(ов)`}
        </Button>
        
        <Button
          onClick={() => fileInputRef.current?.click()}
          variant="outline"
          size="sm"
          disabled={isUploading}
        >
          Добавить
        </Button>
        
        <Button
          onClick={() => setFiles([])}
          variant="outline"
          size="sm"
          disabled={isUploading}
        >
          Отмена
        </Button>
      </div>

      <input
        ref={fileInputRef}
        type="file"
        multiple
        className="hidden"
        onChange={(e) => handleFileSelect(e.target.files)}
        accept="image/*,application/pdf,.doc,.docx,.txt"
      />
    </div>
  );
}