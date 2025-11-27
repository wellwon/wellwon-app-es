import React, { useState, useEffect, useRef } from 'react';
import { Avatar, AvatarFallback, AvatarImage } from '@/components/ui/avatar';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Dialog, DialogContent } from '@/components/ui/dialog';
import { 
  MoreHorizontal, 
  Reply, 
  Download, 
  Play, 
  Pause,
  File,
  Image as ImageIcon,
  FileText,
  FileImage,
  FileVideo,
  FileAudio,
  X,
  ExternalLink,
  Copy
} from 'lucide-react';
import { OptimizedImage } from './OptimizedImage';
import { ImageMessageBubble } from './ImageMessageBubble';
import { getIconComponent } from '@/utils/iconUtils';
import { Check, CheckCheck } from 'lucide-react';
import { formatTime } from '@/utils/dateFormatter';
import { USER_TYPE_LABELS, CHAT_CONSTANTS } from '@/constants/chat';

import { logger } from '@/utils/logger';
import { supabase } from '@/integrations/supabase/client';
import type { Message } from '@/types/realtime-chat';
import TelegramMessageBubble from './TelegramMessageBubble';
import { TelegramChatService } from '@/services/TelegramChatService';
import { TelegramIcon } from '@/components/ui/TelegramIcon';
import { useChatDisplayOptions } from '@/contexts/chat';
import { ReplyMessageBubble } from './ReplyMessageBubble';
import { avatarCache } from '@/utils/avatarCache';

interface MessageBubbleProps {
  message: Message;
  isOwn: boolean;
  isSending?: boolean;
  currentUser?: {
    id: string;
    first_name?: string;
    last_name?: string;
    avatar_url?: string;
  };
  onReply?: (message: Message) => void;
  className?: string;
}

export function MessageBubble({ 
  message, 
  isOwn, 
  isSending = false,
  currentUser,
  onReply, 
  className = '' 
}: MessageBubbleProps) {
  const { options } = useChatDisplayOptions();
  const [imagePreviewOpen, setImagePreviewOpen] = useState(false);
  const openVoiceRef = useRef(false);
  const [avatarLoaded, setAvatarLoaded] = useState(() => avatarCache.isLoaded(message.sender_profile?.avatar_url || ''));
  
  // Avatar optimization
  useEffect(() => {
    const avatarUrl = message.sender_profile?.avatar_url;
    if (avatarUrl && !avatarLoaded) {
      avatarCache.preload(avatarUrl).catch(() => {
        // Handle errors silently
      });
    }
  }, [message.sender_profile?.avatar_url, avatarLoaded]);

  const handleAvatarLoad = () => {
    const avatarUrl = message.sender_profile?.avatar_url;
    if (avatarUrl) {
      avatarCache.markLoaded(avatarUrl);
      setAvatarLoaded(true);
    }
  };
  

  // Определяем имя отправителя с учетом опций отображения
  const displayName = message.sender_profile 
    ? `${message.sender_profile.first_name || ''} ${message.sender_profile.last_name || ''}`.trim() || 'Пользователь'
    : (options.showTelegramNames && message.telegram_user_data) 
      ? TelegramChatService.getTelegramUserDisplayName(message.telegram_user_data)
      : 'Пользователь';
    
  // Определяем источник имени для показа иконки Telegram
  const isFromTelegram = options.showTelegramIcon && !message.sender_profile && message.telegram_user_data;
  
  // Определяем URL аватара - только профиль платформы
  const avatarUrl = message.sender_profile?.avatar_url || null;

  // Функция для извлечения инициалов из имени типа "Liza | WellWon"
  const extractInitials = (name: string): string => {
    // Очищаем от разделителей и разбиваем на слова
    const cleanName = name.replace(/[|\/\-_\.\,]/g, ' ').trim();
    const words = cleanName.split(/\s+/).filter(word => /[a-zA-Zа-яА-Я]/.test(word));
    
    if (words.length >= 2) {
      return (words[0].charAt(0) + words[1].charAt(0)).toUpperCase();
    } else if (words.length === 1) {
      return words[0].charAt(0).toUpperCase();
    }
    
    return 'П';
  };

  // Utility functions
  const needsInlineTimestamp = (message: Message): boolean => {
    return (message.message_type === 'image') 
           && !message.content?.trim();
  };

  const getExtension = (message: Message): string => {
    const fileName = message.file_name || '';
    const fileUrl = message.file_url || '';
    
    // Try to get extension from filename first
    const fromName = fileName.split('.').pop()?.toLowerCase();
    if (fromName && fromName.length <= 4) return fromName;
    
    // Fallback to URL
    const fromUrl = fileUrl.split('.').pop()?.toLowerCase();
    if (fromUrl && fromUrl.length <= 4) return fromUrl;
    
    return 'file';
  };

  const formatBytes = (bytes?: number): string => {
    if (!bytes) return '';
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${Math.round(bytes / 1024)} KB`;
    return `${Math.round(bytes / (1024 * 1024))} MB`;
  };

  const formatVoiceDuration = (seconds?: number): string => {
    if (!seconds) return '0:00';
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return `${mins}:${secs.toString().padStart(2, '0')}`;
  };

  // Simple voice message handling - opens in new tab

  const getFileTypeInfo = (extension: string) => {
    const ext = extension.toLowerCase();
    
    // Document types - using design system colors with circular wrapper
    if (['pdf'].includes(ext)) return { 
      icon: FileText, 
      iconClass: 'text-accent-red', 
      wrapperClass: 'bg-accent-red/20 border-accent-red/30'
    };
    if (['doc', 'docx'].includes(ext)) return { 
      icon: FileText, 
      iconClass: 'text-accent-blue', 
      wrapperClass: 'bg-accent-blue/20 border-accent-blue/30'
    };
    if (['xls', 'xlsx'].includes(ext)) return { 
      icon: FileText, 
      iconClass: 'text-accent-green', 
      wrapperClass: 'bg-accent-green/20 border-accent-green/30'
    };
    
    // Media and other types - neutral styling
    if (['jpg', 'jpeg', 'png', 'gif', 'webp'].includes(ext)) return { 
      icon: FileImage, 
      iconClass: 'text-white/70', 
      wrapperClass: 'bg-white/10 border-white/20'
    };
    if (['mp4', 'avi', 'mov', 'wmv'].includes(ext)) return { 
      icon: FileVideo, 
      iconClass: 'text-white/70', 
      wrapperClass: 'bg-white/10 border-white/20'
    };
    if (['mp3', 'wav', 'flac', 'ogg'].includes(ext)) return { 
      icon: FileAudio, 
      iconClass: 'text-white/70', 
      wrapperClass: 'bg-white/10 border-white/20'
    };
    
    // Default for other files
    return { 
      icon: FileText, 
      iconClass: 'text-white/70', 
      wrapperClass: 'bg-white/10 border-white/20'
    };
  };

  // Функция для генерации инициалов из имени и фамилии
  const getUserInitials = () => {
    const profile = message.sender_profile;
    if (profile && profile.first_name && profile.last_name) {
      const firstName = profile.first_name.charAt(0)?.toUpperCase() || '';
      const lastName = profile.last_name.charAt(0)?.toUpperCase() || '';
      return (firstName + lastName) || 'П';
    }
    
    // Если есть профиль, но нет имени/фамилии, пробуем из display name
    if (profile) {
      const fullName = `${profile.first_name || ''} ${profile.last_name || ''}`.trim();
      if (fullName) {
        return extractInitials(fullName);
      }
    }
    
    // Если нет профиля, но есть telegram данные, генерируем инициалы из них
    if (message.telegram_user_data) {
      const telegramName = TelegramChatService.getTelegramUserDisplayName(message.telegram_user_data);
      return extractInitials(telegramName);
    }
    
    return 'П';
  };

  // Функция для извлечения всех Google-ссылок из текста сообщения
  const extractGoogleLinks = (text: string): { type: 'doc' | 'xls'; url: string; title: string }[] => {
    if (!text) return [];
    
    const links: { type: 'doc' | 'xls'; url: string; title: string }[] = [];
    const urlSet = new Set<string>(); // Для дедупликации
    
    // Поиск Google Docs
    const docsMatches = text.matchAll(/(https?:\/\/docs\.google\.com\/document\/[^\s]+)/g);
    for (const match of docsMatches) {
      const url = match[1];
      if (!urlSet.has(url)) {
        urlSet.add(url);
        links.push({ type: 'doc', url, title: 'Документ Google' });
      }
    }
    
    // Поиск Google Sheets
    const sheetsMatches = text.matchAll(/(https?:\/\/(docs\.google\.com\/spreadsheets|sheets\.google\.com)\/[^\s]+)/g);
    for (const match of sheetsMatches) {
      const url = match[1];
      if (!urlSet.has(url)) {
        urlSet.add(url);
        links.push({ type: 'xls', url, title: 'Таблица Google' });
      }
    }
    
    return links;
  };

  // Функция для замены ссылок в тексте на слова
  const linkifyText = (text: string, excludeGoogleLinks = false): React.ReactNode => {
    const urlRegex = /(https?:\/\/[^\s]+)/g;
    const parts = text.split(urlRegex);
    
    return parts.map((part, index) => {
      if (urlRegex.test(part)) {
        // Проверяем, является ли это Google-ссылкой
        if (part.includes('docs.google.com/document')) {
          return (
            <a
              key={index}
              href={part}
              target="_blank"
              rel="noopener noreferrer"
              className="text-blue-400 hover:text-blue-300 underline"
            >
              Документ
            </a>
          );
        } else if (part.includes('docs.google.com/spreadsheets') || part.includes('sheets.google.com')) {
          return (
            <a
              key={index}
              href={part}
              target="_blank"
              rel="noopener noreferrer"
              className="text-blue-400 hover:text-blue-300 underline"
            >
              Таблица
            </a>
          );
        } else {
          // Обычная ссылка - показываем как есть
          return (
            <a
              key={index}
              href={part}
              target="_blank"
              rel="noopener noreferrer"
              className="text-blue-400 hover:text-blue-300 underline"
            >
              {part}
            </a>
          );
        }
      }
      return part;
    });
  };

  const detectGoogleLink = (text: string): { type: 'doc' | 'xls'; url: string; title: string } | null => {
    if (!text) return null;
    
    // Check for Google Docs
    if (text.includes('docs.google.com/document')) {
      const match = text.match(/(https?:\/\/docs\.google\.com\/document\/[^\s]+)/);
      if (match) {
        return { type: 'doc', url: match[1], title: 'Документ Google' };
      }
    }
    
    // Check for Google Sheets
    if (text.includes('docs.google.com/spreadsheets') || text.includes('sheets.google.com')) {
      const match = text.match(/(https?:\/\/(docs\.google\.com\/spreadsheets|sheets\.google\.com)\/[^\s]+)/);
      if (match) {
        return { type: 'xls', url: match[1], title: 'Таблица Google' };
      }
    }
    
    return null;
  };

  const getTextWithoutGoogleLinksPreserveParagraphs = (text: string): string => {
    // Возвращаем исходный текст для linkifyText с заменой ссылок на слова
    return text;
  };

  const handleCopyLink = async (url: string) => {
    try {
      await navigator.clipboard.writeText(url);
      // Could add toast notification here
    } catch (error) {
      logger.error('Failed to copy link', error);
    }
  };

  const renderGoogleLinkCard = (linkInfo: { type: 'doc' | 'xls'; url: string; title: string }) => {
    const fileTypeInfo = getFileTypeInfo(linkInfo.type === 'doc' ? 'docx' : 'xlsx');
    const IconComponent = fileTypeInfo.icon;
    
    return (
      <div className="mb-3 flex items-center gap-3 p-3 rounded-lg bg-white/5 border border-white/10">
        <div className={`w-10 h-10 rounded-full border flex items-center justify-center ${fileTypeInfo.wrapperClass}`}>
          <IconComponent size={20} className={fileTypeInfo.iconClass} />
        </div>
        <div className="flex-1 min-w-0">
          <div className="text-sm font-medium text-white truncate">
            {linkInfo.title}
          </div>
          <div className="text-xs text-white/70">
            Онлайн документ
          </div>
        </div>
        <div className="flex gap-2">
          <Button
            size="sm"
            variant="ghost"
            className="h-8 w-8 p-0 bg-white/10 hover:bg-white/20"
            onClick={() => handleCopyLink(linkInfo.url)}
            title="Копировать ссылку"
          >
            <Copy size={14} className="text-white/70" />
          </Button>
          <Button
            size="sm"
            variant="ghost"
            className="h-8 w-8 p-0 bg-white/10 hover:bg-white/20"
            onClick={() => window.open(linkInfo.url, '_blank')}
            title="Открыть"
          >
            <ExternalLink size={14} className="text-white/70" />
          </Button>
        </div>
      </div>
    );
  };

  // Функция для создания подписанного URL для файла
  const createSignedUrl = async (fileUrl: string): Promise<string> => {
    try {
      const url = new URL(fileUrl);
      
      // Проверяем, является ли это URL Supabase Storage
      if (!url.pathname.includes('/storage/v1/object/')) {
        return fileUrl; // Возвращаем оригинальный URL для внешних ссылок
      }
      
      const pathSegments = url.pathname.split('/');
      
      // Для Supabase Storage URL структура: /storage/v1/object/public/bucket-name/file-path
      // или /storage/v1/object/sign/bucket-name/file-path  
      const objectIndex = pathSegments.findIndex(segment => segment === 'object');
      
      if (objectIndex === -1 || objectIndex + 3 >= pathSegments.length) {
        logger.warn('Invalid Supabase Storage URL format', { fileUrl });
        return fileUrl;
      }
      
      // Пропускаем 'public' или 'sign' сегмент
      const bucketName = pathSegments[objectIndex + 2];
      const filePath = decodeURIComponent(pathSegments.slice(objectIndex + 3).join('/'));
      
      if (!bucketName || !filePath) {
        logger.warn('Missing bucket or file path', { bucketName, filePath });
        return fileUrl;
      }
      
      const { data, error } = await supabase.storage
        .from(bucketName)
        .createSignedUrl(filePath, 3600); // 1 час
      
      if (error) {
        logger.error('Failed to create signed URL', error, { bucketName, filePath });
        return fileUrl; // Fallback к оригинальному URL
      }
      
      return data.signedUrl;
    } catch (error) {
      logger.error('Error creating signed URL', error, { fileUrl });
      return fileUrl; // Fallback к оригинальному URL
    }
  };

  const handleVoicePlay = async () => {
    if (!message.file_url || openVoiceRef.current) return;
    
    try {
      openVoiceRef.current = true;
      const audioUrl = await createSignedUrl(message.file_url);
      window.open(audioUrl, '_blank');
      
      // Dispatch event to indicate external player was opened
      window.dispatchEvent(new CustomEvent('chat:externalPlayerOpened'));
    } catch (error) {
      logger.error('Failed to open voice message', error);
      window.open(message.file_url, '_blank');
    } finally {
      setTimeout(() => {
        openVoiceRef.current = false;
      }, 1000);
    }
  };

  const handleDownload = async () => {
    if (!message.file_url || !message.file_name) return;
    
    try {
      const downloadUrl = await createSignedUrl(message.file_url);
      
      // Пытаемся скачать файл как blob для корректного имени
      try {
        const response = await fetch(downloadUrl);
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        
        const blob = await response.blob();
        const url = window.URL.createObjectURL(blob);
        
        // Создаем ссылку для скачивания с правильным именем
        const link = document.createElement('a');
        link.href = url;
        link.download = message.file_name;
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
        
        // Освобождаем память
        window.URL.revokeObjectURL(url);
      } catch (fetchError) {
        // Если fetch не работает, открываем в новой вкладке
        logger.warn('Fetch failed, opening in new tab', fetchError);
        window.open(downloadUrl, '_blank');
      }
    } catch (error) {
      logger.error('Failed to download file', error);
      // Последняя попытка - открыть оригинальный URL
      window.open(message.file_url, '_blank');
    }
  };


  const handleButtonAction = (action: string, buttonData?: any) => {
    // Обработка различных действий кнопок
    switch (action) {
      case 'open_registration_form':
        logger.info('Opening registration form');
        break;
      case 'contact_manager':
        logger.info('Contacting manager');
        break;
      case 'view_services':
        logger.info('Viewing services catalog');
        break;
      default:
        logger.debug(`Unknown button action: ${action}`);
    }
  };

  const renderInteractiveContent = () => {
    let interactiveData;
    try {
      // Пробуем извлечь данные из разных возможных полей
      if (message.interactive_data) {
        interactiveData = typeof message.interactive_data === 'string' 
          ? JSON.parse(message.interactive_data) 
          : message.interactive_data;
      } else if (message.metadata?.interactive_data) {
        interactiveData = message.metadata.interactive_data;
      } else {
        logger.debug('Interactive message data not available');
        return <div className="text-sm">Интерактивное сообщение (данные недоступны)</div>;
      }
    } catch (error) {
      logger.error('Error parsing interactive message data', error);
      return <div className="text-sm">Ошибка загрузки интерактивного сообщения</div>;
    }

    const title = interactiveData?.title || message.content || 'Интерактивное сообщение';
    const description = interactiveData?.description;
    const buttons = interactiveData?.buttons || [];
    const imageUrl = interactiveData?.image_url;
    const imagePosition = interactiveData?.image_position || 'left';

    return (
      <div className="space-y-3">
        {/* Content with image positioning */}
        <div className={`flex gap-3 ${imagePosition === 'right' ? 'flex-row-reverse' : 'flex-row'}`}>
          {/* Image */}
          {imageUrl && (
            <div className="flex-shrink-0">
              <OptimizedImage
                src={imageUrl} 
                alt={title || 'Message image'} 
                className="w-24 h-24 object-cover rounded-lg"
                initialWidth={96}
                initialHeight={96}
                aspectRatio={1}
                onError={() => {
                  // Image will be hidden by OptimizedImage component
                }}
              />
            </div>
          )}
          
          {/* Text content */}
          <div className="flex-1 space-y-1">
            <div className="font-medium text-sm">{title}</div>
            {description && (
              <div className="text-sm text-white/80">{description}</div>
            )}
          </div>
        </div>
        
        {/* Buttons */}
        {buttons.length > 0 && (
          <div className="flex flex-wrap gap-3">
            {buttons.map((button: any, index: number) => {
              const buttonStyle = button.style || 'secondary';
              let buttonVariant: 'default' | 'secondary' | 'outline' = 'secondary';
              
              if (buttonStyle === 'primary') buttonVariant = 'default';
              else if (buttonStyle === 'outline') buttonVariant = 'outline';
              
              const IconComponent = button.icon ? getIconComponent(button.icon) : null;
              
              return (
                <Button
                  key={index}
                  variant={buttonVariant}
                  size="sm"
                  className="w-auto text-left justify-start"
                  onClick={() => handleButtonAction(button.action, button)}
                >
                  <div className="flex items-center gap-2">
                    {IconComponent && <IconComponent size={14} />}
                    <span>{button.text}</span>
                  </div>
                </Button>
              );
            })}
          </div>
        )}
      </div>
    );
  };

  const renderTimeAndStatus = (overlay = false) => {
    const timeEl = (
      <span className="text-xs">
        {formatTime(message.created_at)}
      </span>
    );

    const statusEl = isOwn ? (
      isSending ? (
        <div className="w-4 h-4 border-2 border-current border-t-transparent rounded-full animate-spin" />
      ) : (
        message.read_by?.length ? (
          <CheckCheck size={14} />
        ) : (
          <Check size={14} />
        )
      )
    ) : null;

    const editedEl = message.is_edited ? (
      <span className="text-xs italic">изм.</span>
    ) : null;

    if (overlay) {
      return (
        <div className="absolute bottom-2 right-2 bg-black/50 text-white px-1.5 py-0.5 rounded-md flex items-center gap-1 text-xs">
          {editedEl}
          {timeEl}
          {statusEl}
        </div>
      );
    }

    return (
      <div className={`flex items-center gap-1 text-xs ${isOwn ? 'text-white/80' : 'text-gray-400'}`}>
        {editedEl}
        {timeEl}
        {statusEl}
      </div>
    );
  };

  const renderContent = () => {
    const googleLinks = extractGoogleLinks(message.content || '');
    const processedText = getTextWithoutGoogleLinksPreserveParagraphs(message.content || '');
    
    switch (message.message_type) {
      case 'text':
        return (
          <div className="space-y-2">
            {googleLinks.map((linkInfo, index) => (
              <div key={index}>
                {renderGoogleLinkCard(linkInfo)}
              </div>
            ))}
            {processedText && (
              <div className="whitespace-pre-wrap break-words text-sm font-medium pr-16">
                {linkifyText(processedText)}
              </div>
            )}
          </div>
        );

      case 'image':
        return (
          <ImageMessageBubble
            message={message}
            onImageClick={() => setImagePreviewOpen(true)}
            onDownload={handleDownload}
            renderTimeAndStatus={renderTimeAndStatus}
            needsInlineTimestamp={needsInlineTimestamp}
          />
        );

      case 'file':
        const extension = getExtension(message);
        const fileTypeInfo = getFileTypeInfo(extension);
        const IconComponent = fileTypeInfo.icon;
        const fileGoogleLinks = extractGoogleLinks(message.content || '');
        
        return (
          <div className="space-y-2">
            <div className="flex items-center gap-3 pr-16">
              {/* File icon */}
              <div className="flex-shrink-0">
                <div className={`w-10 h-10 rounded-full border flex items-center justify-center ${fileTypeInfo.wrapperClass}`}>
                  <IconComponent size={20} className={fileTypeInfo.iconClass} />
                </div>
              </div>
              
              {/* File name and size/download */}
              <div className="flex-1 min-w-0">
                <div className="text-sm font-medium text-white truncate">
                  {message.file_name || 'Файл'}
                </div>
                <div className="text-xs text-white/70">
                  {formatBytes(message.file_size)} • <button 
                    onClick={handleDownload}
                    className="text-white/70 hover:text-white underline"
                  >
                    скачать
                  </button>
                </div>
              </div>
            </div>
            {fileGoogleLinks.map((linkInfo, index) => (
              <div key={index}>
                {renderGoogleLinkCard(linkInfo)}
              </div>
            ))}
            {message.content && (
              <div className="text-sm pr-16">{linkifyText(message.content)}</div>
            )}
          </div>
        );

      case 'voice':
        const voiceGoogleLinks = extractGoogleLinks(message.content || '');
        
        return (
          <div className="space-y-2 pr-20">
            <div className="flex items-center gap-3">
              {/* Voice icon/play button */}
              <div className="flex-shrink-0">
                <Button
                  size="sm"
                  variant="ghost"
                  onClick={handleVoicePlay}
                  className="w-10 h-10 p-0 rounded-full bg-accent-red/20 hover:bg-accent-red/30 border border-accent-red/30"
                >
                  <Play size={16} className="text-accent-red" />
                </Button>
              </div>
              
              {/* Voice info and progress */}
              <div className="flex-1 min-w-0">
                <div className="text-sm font-medium text-white mb-1">
                  Голосовое сообщение
                </div>
                <div className="text-xs text-white/70 mb-2">
                  {formatVoiceDuration(message.voice_duration)} • <button 
                    onClick={handleDownload}
                    className="text-white/70 hover:text-white underline"
                  >
                    скачать
                  </button>
                </div>
                {/* Static progress bar */}
                <div className="w-full h-[2px] bg-white/20 rounded-full">
                  <div 
                    className="h-[2px] bg-accent-red rounded-full"
                    style={{ width: '0%' }}
                  ></div>
                </div>
              </div>
            </div>
            {voiceGoogleLinks.map((linkInfo, index) => (
              <div key={index}>
                {renderGoogleLinkCard(linkInfo)}
              </div>
            ))}
            {message.content && (
              <div className="text-sm">{linkifyText(message.content)}</div>
            )}
          </div>
        );

      case 'interactive':
        return (
          <div className="pr-16">
            {renderInteractiveContent()}
          </div>
        );

      case 'system':
        return (
          <div className="text-center text-sm text-muted-foreground italic">
            {message.content}
          </div>
        );

      default:
        return <div className="pr-16">{message.content}</div>;
    }
  };

  if (message.message_type === 'system') {
    return (
      <div className={`py-2 ${className}`}>
        {renderContent()}
      </div>
    );
  }

  return (
    <>
      <div className={`w-full max-w-4xl mx-auto group ${className}`} data-message-id={message.id}>
        <div className={`flex gap-4 items-start ${isOwn ? 'flex-row-reverse' : ''}`}>
          
          {/* Только аватар без рамки */}
          <Avatar className="w-8 h-8 flex-shrink-0">
            {(() => {
              const shouldGrayAvatar = !isOwn && /WW/i.test(message.metadata?.role_label || '');
              
              return avatarUrl ? (
                <>
                  <AvatarImage 
                    src={avatarUrl} 
                    onLoad={handleAvatarLoad}
                    loading="eager"
                    className={`transition-opacity duration-200 ${shouldGrayAvatar ? 'grayscale' : ''} ${avatarLoaded ? 'opacity-100' : 'opacity-0'}`}
                  />
                  <AvatarFallback className={`
                    text-xs font-medium border transition-opacity duration-200
                    ${shouldGrayAvatar 
                      ? "bg-[#414145] text-white/80 border-white/10" 
                      : "bg-accent-red/20 text-accent-red border-accent-red"
                    }
                    ${avatarLoaded ? 'opacity-0 absolute inset-0' : 'opacity-100'}
                  `}>
                    {getUserInitials()}
                  </AvatarFallback>
                </>
              ) : (
                <AvatarFallback className={shouldGrayAvatar 
                  ? "text-xs font-medium bg-[#414145] text-white/80 border border-white/10" 
                  : "text-xs font-medium bg-accent-red/20 text-accent-red border-2 border-accent-red"
                }>
                  {getUserInitials()}
                </AvatarFallback>
              );
            })()}
          </Avatar>

          {/* Пузырь сообщения с именем внутри */}
          <div className={`flex-1 flex ${isOwn ? 'justify-end' : 'justify-start'}`}>
            <div 
              className={`
                message-bubble relative rounded-2xl min-w-0
                ${message.message_type === 'image' ? 
                  (message.metadata?.imageDimensions?.aspectRatio && message.metadata.imageDimensions.aspectRatio < 1 
                    ? 'inline-block w-auto' // Портретные изображения - автоширина по содержимому
                    : 'w-[92%] sm:w-[min(70%,450px)]' // Горизонтальные и квадратные - шире
                  ) 
                  : 'max-w-[66.666%]'
                }
                ${isOwn 
                  ? 'bg-accent-red/20 text-white rounded-br-md border border-accent-red/30' 
                  : 'bg-[hsl(var(--light-gray))] text-white rounded-bl-md border border-white/10'
                }
              `}
            >
              {/* Имя и тип пользователя внутри сообщения */}
              <div className="px-3 pt-2 pb-1 border-b border-white/10">
                <div className={`text-xs font-medium text-white/90 flex items-center gap-2 ${isOwn ? 'justify-end' : 'justify-start'}`}>
                  {isOwn && (
                    <Badge 
                      variant="outline" 
                      className={`text-[10px] py-0 px-1 h-4 bg-accent-red/20 border-red-400/30 ${
                        message.metadata?.role_label === 'Нет роли' ? 'text-accent-red' : 'text-red-300'
                      }`}
                    >
                      {message.metadata?.role_label || 'Нет роли'}
                    </Badge>
                  )}
                  <div className="flex items-center gap-1">
                    <span className={isOwn ? "" : "text-[#969699]"}>{displayName}</span>
                    {isFromTelegram && (
                      <TelegramIcon className="w-3 h-3 text-blue-400" />
                    )}
                  </div>
                  {!isOwn && (
                    <Badge 
                      variant="outline" 
                      className={`text-[10px] py-0 px-1 h-4 bg-white/10 border-white/20 ${
                        message.metadata?.role_label === 'Нет роли' ? 'text-accent-red' : 'text-white/60'
                      }`}
                    >
                      {message.metadata?.role_label || 'Нет роли'}
                    </Badge>
                  )}
                </div>
                
                {/* Telegram indicators */}
                {message.telegram_forward_data && (
                  <div className="mt-1">
                    <TelegramMessageBubble message={message} />
                  </div>
                )}
              </div>

              {/* Reply bubble - показываем если есть reply_to_id */}
              {message.reply_to_id && (
                <div className="px-3 pt-2">
                  <ReplyMessageBubble 
                    replyMessage={message.reply_to || {
                      id: message.reply_to_id,
                      chat_id: message.chat_id,
                      sender_id: null,
                      content: null,
                      message_type: 'text',
                      file_url: null,
                      file_name: null,
                      file_type: null,
                      file_size: null,
                      voice_duration: null,
                      reply_to_id: null,
                      interactive_data: null,
                      created_at: message.created_at,
                      updated_at: message.created_at,
                      is_edited: false,
                      is_deleted: false,
                      metadata: {},
                      sender_profile: null,
                      telegram_user_data: null,
                      reply_to: null,
                      read_by: []
                    }}
                    onReplyClick={(messageId) => {
                      // Scrolling logic with smart history loading
                      const scrollAndHighlight = (targetMessageId: string) => {
                        const messageElement = document.querySelector(`[data-message-id="${targetMessageId}"]`);
                        if (messageElement) {
                          messageElement.scrollIntoView({ 
                            behavior: 'smooth', 
                            block: 'center' 
                          });
                          // Add highlight effect
                          messageElement.classList.add('highlight-reply');
                          setTimeout(() => {
                            messageElement.classList.remove('highlight-reply');
                          }, 3500);
                        } else {
                          logger.warn('Message element not found in DOM after load', { messageId: targetMessageId });
                        }
                      };

                      // First check if message element exists in DOM
                      const messageElement = document.querySelector(`[data-message-id="${messageId}"]`);
                      if (messageElement) {
                        // Message is visible, scroll to it immediately
                        scrollAndHighlight(messageId);
                      } else {
                        // Message not in DOM, dispatch event to load history
                        logger.info('Message not in DOM, requesting smart scroll', { messageId, component: 'MessageBubble' });
                        
                        window.dispatchEvent(new CustomEvent('chat:findReplyMessage', {
                          detail: {
                            replyToId: messageId,
                            onFound: scrollAndHighlight
                          }
                        }));
                      }
                    }}
                  />
                </div>
              )}

              <div className="p-3">
                {renderContent()}
              </div>

              {/* Время и статус прочтения - только если НЕ inline */}
              {!needsInlineTimestamp(message) && (
                <div className="absolute bottom-2 right-3">
                  {renderTimeAndStatus()}
                </div>
              )}

              {/* Кнопки действий */}
              <div className={`
                absolute top-0 opacity-0 group-hover:opacity-100 transition-opacity flex gap-1
                ${isOwn ? '-left-20' : '-right-20'}
              `}>
                {isOwn ? (
                  // Для отправленных сообщений: точки слева, стрелка справа
                  <>
                    <Button
                      size="sm"
                      variant="ghost"
                      className="h-8 w-8 p-0"
                    >
                      <MoreHorizontal size={14} />
                    </Button>
                    {onReply && (
                      <Button
                        size="sm"
                        variant="ghost"
                        className="h-8 w-8 p-0"
                        onClick={() => onReply(message)}
                      >
                        <Reply size={14} className="scale-x-[-1]" />
                      </Button>
                    )}
                  </>
                ) : (
                  // Для полученных сообщений: оставляем как есть
                  <>
                    {onReply && (
                      <Button
                        size="sm"
                        variant="ghost"
                        className="h-8 w-8 p-0"
                        onClick={() => onReply(message)}
                      >
                        <Reply size={14} />
                      </Button>
                    )}
                    <Button
                      size="sm"
                      variant="ghost"
                      className="h-8 w-8 p-0"
                    >
                      <MoreHorizontal size={14} />
                    </Button>
                  </>
                )}
              </div>
            </div>
          </div>
          
        </div>
      </div>

      {/* Image Preview Dialog */}
      {message.message_type === 'image' && message.file_url && (
        <Dialog open={imagePreviewOpen} onOpenChange={setImagePreviewOpen}>
          <DialogContent className="max-w-4xl bg-black/90 border-white/20 p-2">
            <div className="relative">
              <Button
                size="sm"
                variant="ghost"
                className="absolute top-2 right-2 z-10 text-white hover:bg-white/20"
                onClick={() => setImagePreviewOpen(false)}
              >
                <X size={16} />
              </Button>
              <img
                src={message.file_url}
                alt={message.file_name || 'Изображение'}
                className="w-full h-auto max-h-[80vh] object-contain rounded-lg"
              />
            </div>
          </DialogContent>
        </Dialog>
      )}
    </>
  );
}
