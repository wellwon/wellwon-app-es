import React from 'react';
import { GlassInput } from '@/components/design-system/GlassInput';

interface AddressFieldsProps {
  formData: any;
  setFormData: (data: any) => void;
  errors: Record<string, string>;
  isEditing: boolean;
  isProject: boolean;
  getFieldIndicatorColor: (fieldName: string) => string;
  isLightTheme?: boolean;
}

export const AddressFields: React.FC<AddressFieldsProps> = ({
  formData,
  setFormData,
  errors,
  isEditing,
  isProject,
  getFieldIndicatorColor,
  isLightTheme = false
}) => {
  return (
    <div className="space-y-6">
      {isProject ? (
        // Режим проекта: Адрес и Город в одной строке
        <div className="flex gap-4">
          <div className="flex-[2]">
            <GlassInput
              label="Адрес *"
              value={formData.street || ''}
              onChange={(e) => setFormData(prev => ({ ...prev, street: e.target.value }))}
              placeholder="г. Москва, ул. Примерная, д. 1"
              disabled={!isEditing}
              error={errors.street}
              isLightTheme={isLightTheme}
            />
          </div>
          <div className="flex-[1]">
            <GlassInput
              label="Город *"
              value={formData.city || ''}
              onChange={(e) => setFormData(prev => ({ ...prev, city: e.target.value }))}
              placeholder="Москва"
              disabled={!isEditing}
              error={errors.city}
              isLightTheme={isLightTheme}
            />
          </div>
        </div>
      ) : (
        // Режим компании: стандартная компоновка
        <>
          <GlassInput
            label="Адрес *"
            value={formData.street || ''}
            onChange={(e) => setFormData(prev => ({ ...prev, street: e.target.value }))}
            placeholder="г. Москва, ул. Примерная, д. 1"
            disabled={!isEditing}
            error={errors.street}
            isLightTheme={isLightTheme}
          />

          <div className="grid grid-cols-3 gap-4">
            <GlassInput
              label="Город *"
              value={formData.city || ''}
              onChange={(e) => setFormData(prev => ({ ...prev, city: e.target.value }))}
              placeholder="Москва"
              disabled={!isEditing}
              error={errors.city}
              isLightTheme={isLightTheme}
            />

            <GlassInput
              label="Индекс"
              value={formData.postal_code || ''}
              onChange={(e) => setFormData(prev => ({ ...prev, postal_code: e.target.value }))}
              placeholder="123456"
              disabled={!isEditing}
              error={errors.postal_code}
              isLightTheme={isLightTheme}
            />

            <GlassInput
              label="Страна *"
              value={formData.country || ''}
              onChange={(e) => setFormData(prev => ({ ...prev, country: e.target.value }))}
              placeholder="Россия"
              disabled={!isEditing}
              error={errors.country}
              isLightTheme={isLightTheme}
            />
          </div>
        </>
      )}
    </div>
  );
};