import React from 'react';
import { Button } from '@/components/ui/button';
import { Loader2, X, Users } from 'lucide-react';
import { GlassButton } from '@/components/design-system/GlassButton';

interface FormActionsProps {
  isEditing: boolean;
  isSaving: boolean;
  hasChanges: boolean;
  onCancel: () => void;
  onSave: () => void;
  isProject?: boolean;
  isCreatingGroup?: boolean;
}

export const FormActions: React.FC<FormActionsProps> = ({
  isSaving,
  onCancel,
  onSave,
  isProject = false,
  isCreatingGroup = false
}) => {
  
  return (
    <div className="flex justify-center gap-3 pt-6 border-t border-glass-border">
      <Button
        type="button"
        variant="outline"
        onClick={onCancel}
        disabled={isSaving}
        className="flex items-center gap-2 bg-glass-surface border-glass-border hover:bg-glass-surface/80"
      >
        <X className="h-4 w-4" />
        Отмена
      </Button>
      
      <GlassButton
        onClick={onSave}
        disabled={isSaving}
        variant="primary"
        className="flex items-center gap-2"
      >
        {isSaving ? (
          <Loader2 className="h-4 w-4 animate-spin" />
        ) : (
          <Users className="h-4 w-4" />
        )}
        {isSaving 
          ? (isCreatingGroup ? 'Создаётся компания и группа...' : isProject ? 'Создаётся проект...' : 'Создаётся компания...') 
          : (isProject ? 'Создать проект и группу' : 'Создать компанию и группу Telegram')
        }
      </GlassButton>
    </div>
  );
};