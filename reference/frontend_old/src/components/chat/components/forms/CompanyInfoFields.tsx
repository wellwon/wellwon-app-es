import React from 'react';
import { Label } from '@/components/ui/label';
import { GlassInput } from '@/components/design-system/GlassInput';
import { Button } from '@/components/ui/button';
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
}

export const CompanyInfoFields: React.FC<CompanyInfoFieldsProps> = ({
  formData,
  setFormData,
  errors,
  isEditing,
  isProject,
  isSearching,
  onSearchByINN,
  getFieldIndicatorColor
}) => {
  return (
    <div className="space-y-6">
      <h3 className="text-text-white font-semibold text-xl mb-6 flex items-center gap-3">
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
                />
                {isEditing && (
                  <Button
                    type="button"
                    variant="outline"
                    size="icon"
                    onClick={onSearchByINN}
                    disabled={isSearching || !formData.vat}
                    className="h-12 w-12 shrink-0 bg-glass-surface border-glass-border hover:bg-glass-surface/80"
                  >
                    {isSearching ? (
                      <Loader2 className="h-4 w-4 animate-spin text-accent-red" />
                    ) : (
                      <Search className="h-4 w-4 text-accent-red" />
                    )}
                  </Button>
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
            />
            
            <GlassInput
              label="ОГРН"
              value={formData.ogrn || ''}
              onChange={(e) => setFormData(prev => ({ ...prev, ogrn: e.target.value }))}
              placeholder="1234567890123"
              disabled={!isEditing}
              error={errors.ogrn}
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
            />
          </div>
        </div>
      )}
    </div>
  );
};