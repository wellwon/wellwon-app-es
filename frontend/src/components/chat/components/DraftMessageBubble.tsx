import React, { useState } from 'react';
import { Check, X, Zap, ShoppingCart, FileText, Calculator, CreditCard, Edit3 } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Avatar, AvatarFallback, AvatarImage } from '@/components/ui/avatar';
import { Badge } from '@/components/ui/badge';
import { useAuth } from '@/contexts/AuthContext';
import { useToast } from '@/hooks/use-toast';
import { InlineChatTemplateEdit } from './InlineChatTemplateEdit';
import { MessageTemplateService } from '@/services/MessageTemplateService';
import type { MessageTemplate } from '@/utils/messageTemplates';

interface DraftMessageBubbleProps {
  template: MessageTemplate;
  onConfirm: () => void;
  onCancel: () => void;
  onEdit?: () => void;
  onTemplateChange?: (updatedTemplate: MessageTemplate) => void;
}

export const DraftMessageBubble: React.FC<DraftMessageBubbleProps> = ({
  template,
  onConfirm,
  onCancel,
  onEdit,
  onTemplateChange
}) => {
  const { user } = useAuth();
  const { toast } = useToast();
  const [avatarLoaded, setAvatarLoaded] = useState(false);
  const [isEditing, setIsEditing] = useState(false);

  const displayName = user?.user_metadata?.full_name || 'Пользователь';
  const avatarUrl = user?.user_metadata?.avatar_url;

  const getUserInitials = () => {
    if (user?.user_metadata?.full_name) {
      const names = user.user_metadata.full_name.split(' ');
      const firstName = names[0]?.charAt(0)?.toUpperCase() || '';
      const lastName = names[1]?.charAt(0)?.toUpperCase() || '';
      return (firstName + lastName) || 'П';
    }
    return 'П';
  };

  const handleButtonAction = (action: string, buttonData?: any) => {
    
  };

  const getButtonIcon = (action: string) => {
    switch (action) {
      case 'order':
        return <ShoppingCart size={14} />;
      case 'calculate':
        return <Calculator size={14} />;
      case 'payment':
        return <CreditCard size={14} />;
      case 'document':
        return <FileText size={14} />;
      default:
        return <Zap size={14} />;
    }
  };

  const renderInteractiveContent = () => {
    const data = template.template_data;
    const title = data.title || template.name;
    const description = data.description || template.description;
    const buttons = data.buttons || [];
    const imageUrl = data.image_url;

    return (
      <div className="space-y-3">
        <div className={`${imageUrl ? `flex gap-3 items-start ${template.template_data.image_position === 'right' ? 'flex-row-reverse' : ''}` : ''}`}>
          {imageUrl && (
            <div className="w-24 h-24 rounded-lg overflow-hidden bg-gray-800/50 flex-shrink-0">
              <img 
                src={imageUrl} 
                alt={title || 'Message image'} 
                className="w-full h-full object-cover"
                onError={(e) => {
                  e.currentTarget.style.display = 'none';
                }}
              />
            </div>
          )}
          
          <div className="space-y-1 flex-1">
            <div className="font-medium text-sm">{title}</div>
            {description && (
              <div className="text-sm text-white/80">{description}</div>
            )}
          </div>
        </div>
        
        {buttons.length > 0 && (
          <div className="flex flex-wrap gap-3 px-2">
            {buttons.map((button: any, index: number) => {
              const buttonStyle = button.style || 'secondary';
              let buttonVariant: 'default' | 'secondary' | 'outline' = 'secondary';
              
              if (buttonStyle === 'primary') buttonVariant = 'default';
              else if (buttonStyle === 'outline') buttonVariant = 'outline';
              
              return (
                <Button
                  key={index}
                  variant={buttonVariant}
                  size="sm"
                  className="px-4 py-2 gap-2 flex-shrink-0"
                  onClick={() => handleButtonAction(button.action, button)}
                >
                  {getButtonIcon(button.action)}
                  {button.text}
                </Button>
              );
            })}
          </div>
        )}
      </div>
    );
  };

  return (
    <div className="w-full max-w-4xl mx-auto group mb-4">
      <div className="flex gap-4 items-start flex-row-reverse">
        
        {/* Avatar and buttons */}
        <div className="flex flex-col items-center gap-2">
          <Avatar className="w-8 h-8 flex-shrink-0">
            {avatarUrl ? (
              <>
                <AvatarImage 
                  src={avatarUrl} 
                  onLoad={() => setAvatarLoaded(true)}
                  className={`transition-opacity duration-200 ${avatarLoaded ? 'opacity-100' : 'opacity-0'}`}
                />
                <AvatarFallback className={`text-xs font-medium bg-accent-red/20 text-accent-red border-2 border-accent-red transition-opacity duration-200 ${avatarLoaded ? 'opacity-0' : 'opacity-100'}`}>
                  {getUserInitials()}
                </AvatarFallback>
              </>
            ) : (
              <AvatarFallback className="text-xs font-medium bg-accent-red/20 text-accent-red border-2 border-accent-red">
                {getUserInitials()}
              </AvatarFallback>
            )}
          </Avatar>

          {/* Confirmation buttons under avatar */}
          <div className="flex flex-col gap-1">
            <Button
              size="sm"
              onClick={onConfirm}
              className="h-8 w-8 p-0 rounded-full bg-green-600 hover:bg-green-700 transition-all duration-200"
            >
              <Check size={14} />
            </Button>
            <Button
              size="sm"
              variant="outline"
              onClick={onCancel}
              className="h-8 w-8 p-0 rounded-full bg-red-600 hover:bg-red-700 border-red-600 text-white transition-all duration-200"
            >
              <X size={14} />
            </Button>
            <Button
              size="sm"
              variant="outline"
              onClick={() => setIsEditing(!isEditing)}
              className="h-8 w-8 p-0 rounded-full bg-blue-600 hover:bg-blue-700 border-blue-600 text-white transition-all duration-200"
            >
              <Edit3 size={14} />
            </Button>
          </div>
        </div>

        {/* Message bubble */}
        <div className="flex-1 flex justify-end">
          <div className="relative rounded-2xl max-w-[66.666%] min-w-0 bg-accent-red/20 text-white rounded-br-md border border-accent-red/30">
            
            {/* Name and type inside message */}
            <div className="px-3 pt-2 pb-1 border-b border-white/10">
              <div className="text-xs font-medium text-white/90 flex items-center gap-2 justify-end">
                <Badge variant="outline" className="text-[10px] py-0 px-1 h-4 bg-accent-red/20 text-red-300 border-red-400/30">
                  Админ
                </Badge>
                <span>{displayName}</span>
              </div>
            </div>

            <div className="p-3 pr-16">
              {renderInteractiveContent()}
            </div>

            {/* Time */}
            <div className="absolute bottom-2 right-3 flex items-center gap-1 text-xs text-white/80">
              <span>Черновик</span>
            </div>

          </div>
        </div>
        
      </div>

      {/* Inline Edit Form */}
      {isEditing && (
        <div className="mt-2">
          <InlineChatTemplateEdit
            template={template}
            isOpen={isEditing}
            onClose={() => setIsEditing(false)}
            onSave={async (updatedTemplate) => {
              try {
                const success = await MessageTemplateService.updateTemplate(template.id, updatedTemplate);
                if (success) {
                  onTemplateChange?.(updatedTemplate);
                  setIsEditing(false);
                  toast({
                    title: "Шаблон сохранен",
                    description: "Изменения успешно сохранены в базе данных",
                  });
                } else {
                  toast({
                     variant: "error",
                    title: "Ошибка сохранения",
                    description: "Не удалось сохранить изменения шаблона",
                  });
                }
              } catch (error) {
                
                toast({
                  variant: "error",
                  title: "Ошибка сохранения",
                  description: "Произошла ошибка при сохранении шаблона",
                });
              }
            }}
            onChange={onTemplateChange}
          />
        </div>
      )}
    </div>
  );
};