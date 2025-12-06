import React from 'react';
import { GlassCard } from '@/components/design-system/GlassCard';
import { GlassInput } from '@/components/design-system/GlassInput';
import { TelegramIcon } from '@/components/ui/TelegramIcon';
import { Phone, AtSign } from 'lucide-react';
import { FormSection } from '@/components/design-system/FormSection';

export interface TelegramGroupData {
  title: string;
  description: string;
  // Client contact fields for auto-invite after group creation
  // Note: client name is derived from company_name (for ImportContactsRequest)
  clientPhone: string;
  clientUsername: string;
}

interface TelegramGroupFieldsProps {
  groupData: TelegramGroupData;
  setGroupData: (data: TelegramGroupData) => void;
  isLightTheme?: boolean;
}

export const TelegramGroupFields: React.FC<TelegramGroupFieldsProps> = ({
  groupData,
  setGroupData,
  isLightTheme = false
}) => {
  const handleChange = (field: keyof TelegramGroupData) => (e: React.ChangeEvent<HTMLInputElement>) => {
    setGroupData({
      ...groupData,
      [field]: e.target.value
    });
  };

  // Detect contact type for visual hint
  const hasPhone = groupData.clientPhone?.trim().length > 0;
  const hasUsername = groupData.clientUsername?.trim().length > 0;

  return (
    <div className="space-y-6">
      {/* Group Settings */}
      <div className="space-y-4">
        <GlassInput
          label="Название рабочей группы"
          value={groupData.title}
          onChange={handleChange('title')}
          placeholder="Введите название группы"
          required
          isLightTheme={isLightTheme}
        />

        <GlassInput
          label="Описание группы"
          value={groupData.description}
          onChange={handleChange('description')}
          placeholder="Введите описание группы"
          required
          isLightTheme={isLightTheme}
        />
      </div>

      {/* Client Telegram Contact - for auto-invite */}
      <FormSection
        title="Telegram контакт клиента"
        description="Клиент будет автоматически приглашен в группу после создания"
      >
        <div className="space-y-4">
          <div className="grid grid-cols-2 gap-4">
            <div className="relative">
              <GlassInput
                label="Телефон Telegram"
                value={groupData.clientPhone || ''}
                onChange={handleChange('clientPhone')}
                placeholder="+79001234567"
                isLightTheme={isLightTheme}
              />
              {hasPhone && (
                <Phone className="absolute right-3 top-9 h-4 w-4 text-muted-foreground" />
              )}
            </div>

            <div className="relative">
              <GlassInput
                label="Username Telegram"
                value={groupData.clientUsername || ''}
                onChange={handleChange('clientUsername')}
                placeholder="@username"
                isLightTheme={isLightTheme}
              />
              {hasUsername && (
                <AtSign className="absolute right-3 top-9 h-4 w-4 text-muted-foreground" />
              )}
            </div>
          </div>

          <p className="text-xs text-muted-foreground">
            Укажите телефон или @username клиента. После создания группы клиент будет автоматически приглашен.
            Если оставить пустым, можно скопировать ссылку-приглашение.
          </p>
        </div>
      </FormSection>
    </div>
  );
};