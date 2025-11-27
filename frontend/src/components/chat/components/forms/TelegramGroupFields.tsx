import React from 'react';
import { GlassCard } from '@/components/design-system/GlassCard';
import { GlassInput } from '@/components/design-system/GlassInput';
import { TelegramIcon } from '@/components/ui/TelegramIcon';
interface TelegramGroupData {
  title: string;
  description: string;
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
  const handleTitleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setGroupData({
      ...groupData,
      title: e.target.value
    });
  };
  const handleDescriptionChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setGroupData({
      ...groupData,
      description: e.target.value
    });
  };
  return (
    <div className="space-y-4">
      <GlassInput
        label="Название рабочей группы"
        value={groupData.title}
        onChange={handleTitleChange}
        placeholder="Введите название группы"
        required
        isLightTheme={isLightTheme}
      />

      <GlassInput
        label="Описание группы"
        value={groupData.description}
        onChange={handleDescriptionChange}
        placeholder="Введите описание группы"
        required
        isLightTheme={isLightTheme}
      />
    </div>
  );
};