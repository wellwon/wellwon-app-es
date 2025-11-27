import React from 'react';
import { GlassInput } from '@/components/design-system/GlassInput';
import { Phone } from 'lucide-react';

interface ContactInfoFieldsProps {
  formData: any;
  setFormData: (data: any) => void;
  errors: Record<string, string>;
  isEditing: boolean;
  getFieldIndicatorColor: (fieldName: string) => string;
  isLightTheme?: boolean;
}

export const ContactInfoFields: React.FC<ContactInfoFieldsProps> = ({
  formData,
  setFormData,
  errors,
  isEditing,
  getFieldIndicatorColor,
  isLightTheme = false
}) => {
  // Theme styles
  const titleClass = isLightTheme ? 'text-gray-900' : 'text-white';

  return (
    <div className="space-y-6">
      <h3 className={`font-semibold text-xl mb-6 flex items-center gap-3 ${titleClass}`}>
        <Phone className="w-6 h-6 text-accent-red" />
        Контактная информация
      </h3>

      <GlassInput
        label="Директор"
        value={formData.director || ''}
        onChange={(e) => setFormData(prev => ({ ...prev, director: e.target.value }))}
        placeholder="Иванов Иван Иванович"
        disabled={!isEditing}
        error={errors.director}
        isLightTheme={isLightTheme}
      />

      <div className="grid grid-cols-2 gap-4">
        <GlassInput
          label="Телефон"
          type="tel"
          value={formData.phone || ''}
          onChange={(e) => setFormData(prev => ({ ...prev, phone: e.target.value }))}
          placeholder="+7 (999) 123-45-67"
          disabled={!isEditing}
          error={errors.phone}
          isLightTheme={isLightTheme}
        />

        <GlassInput
          label="Email"
          type="email"
          value={formData.email || ''}
          onChange={(e) => setFormData(prev => ({ ...prev, email: e.target.value }))}
          placeholder="info@example.com"
          disabled={!isEditing}
          error={errors.email}
          isLightTheme={isLightTheme}
        />
      </div>
    </div>
  );
};