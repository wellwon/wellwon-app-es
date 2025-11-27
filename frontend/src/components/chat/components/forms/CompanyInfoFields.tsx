import React from 'react';
import { GlassInput } from '@/components/design-system/GlassInput';
import { Search, Loader2, Building } from 'lucide-react';

interface CompanyInfoFieldsProps {
  formData: any;
  setFormData: (data: any) => void;
  errors: Record<string, string>;
  isEditing: boolean;
  isProject: boolean;
  isSearching: boolean;
  onSearchByINN: () => void;
  getFieldIndicatorColor: (fieldName: string) => string;
  isLightTheme?: boolean;
}

export const CompanyInfoFields: React.FC<CompanyInfoFieldsProps> = ({
  formData,
  setFormData,
  errors,
  isEditing,
  isProject,
  isSearching,
  onSearchByINN,
  getFieldIndicatorColor,
  isLightTheme = false
}) => {
  // Theme styles
  const titleClass = isLightTheme ? 'text-gray-900' : 'text-white';
  const searchButtonClass = isLightTheme
    ? 'bg-gray-100 border-gray-300 hover:bg-gray-200 text-accent-red'
    : 'bg-white/5 border-white/10 hover:bg-white/10 text-accent-red';

  return (
    <div className="space-y-6">
      <h3 className={`font-semibold text-xl mb-6 flex items-center gap-3 ${titleClass}`}>
        <Building className="w-6 h-6 text-accent-red" />
        {isProject ? 'Информация о проекте' : 'Информация о компании'}
      </h3>

      {!isProject && (
        <>
          {/* ИНН и Название компании на одной строке */}
          <div className="flex gap-4">
            <div className="flex-[0.77]">
              <div className="flex gap-2 items-end">
                <GlassInput
                  label="ИНН *"
                  value={formData.vat || ''}
                  onChange={(e) => setFormData(prev => ({
                    ...prev,
                    vat: e.target.value
                  }))}
                  placeholder="1234567890"
                  disabled={!isEditing}
                  error={errors.vat}
                  isLightTheme={isLightTheme}
                />
                {isEditing && (
                  <button
                    type="button"
                    onClick={onSearchByINN}
                    disabled={isSearching || !formData.vat}
                    className={`h-10 w-10 shrink-0 rounded-xl border flex items-center justify-center disabled:opacity-50 ${searchButtonClass}`}
                  >
                    {isSearching ? (
                      <Loader2 className="h-4 w-4 animate-spin" />
                    ) : (
                      <Search className="h-4 w-4" />
                    )}
                  </button>
                )}
              </div>
            </div>

            <div className="flex-[1.3]">
              <GlassInput
                label="Название компании *"
                value={formData.company_name || ''}
                onChange={(e) => setFormData(prev => ({
                  ...prev,
                  company_name: e.target.value
                }))}
                placeholder="ООО Пример"
                disabled={!isEditing}
                error={errors.company_name}
                isLightTheme={isLightTheme}
              />
            </div>
          </div>

          {/* КПП и ОГРН на второй строке */}
          <div className="grid grid-cols-2 gap-4">
            <GlassInput
              label="КПП"
              value={formData.kpp || ''}
              onChange={(e) => setFormData(prev => ({ ...prev, kpp: e.target.value }))}
              placeholder="123456789"
              disabled={!isEditing}
              error={errors.kpp}
              isLightTheme={isLightTheme}
            />

            <GlassInput
              label="ОГРН"
              value={formData.ogrn || ''}
              onChange={(e) => setFormData(prev => ({ ...prev, ogrn: e.target.value }))}
              placeholder="1234567890123"
              disabled={!isEditing}
              error={errors.ogrn}
              isLightTheme={isLightTheme}
            />
          </div>
        </>
      )}

      {isProject && (
        <div className="flex gap-4">
          <div className="flex-[2]">
            <GlassInput
              label="Название проекта *"
              value={formData.company_name || ''}
              onChange={(e) => setFormData(prev => ({
                ...prev,
                company_name: e.target.value
              }))}
              placeholder="Мой проект"
              disabled={!isEditing}
              error={errors.company_name}
              isLightTheme={isLightTheme}
            />
          </div>

          <div className="flex-[1]">
            <GlassInput
              label="Страна"
              value={formData.country || ''}
              onChange={(e) => setFormData(prev => ({
                ...prev,
                country: e.target.value
              }))}
              placeholder="Россия"
              disabled={!isEditing}
              error={errors.country}
              isLightTheme={isLightTheme}
            />
          </div>
        </div>
      )}
    </div>
  );
};