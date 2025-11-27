import React from 'react';
import { Loader2, X, Users } from 'lucide-react';

interface FormActionsProps {
  isEditing: boolean;
  isSaving: boolean;
  hasChanges: boolean;
  onCancel: () => void;
  onSave: () => void;
  isProject?: boolean;
  isCreatingGroup?: boolean;
  isLightTheme?: boolean;
}

export const FormActions: React.FC<FormActionsProps> = ({
  isSaving,
  onCancel,
  onSave,
  isProject = false,
  isCreatingGroup = false,
  isLightTheme = false
}) => {

  // Theme styles according to DESIGN_SYSTEM.md §19
  const cancelButtonClass = isLightTheme
    ? 'bg-white text-gray-700 border-gray-300 hover:bg-gray-50'
    : 'bg-[#232328] text-gray-300 border-white/10 hover:bg-[#2a2a30]';

  return (
    <div className="flex justify-center gap-3">
      <button
        type="button"
        onClick={onCancel}
        disabled={isSaving}
        className={`h-12 px-6 py-3 rounded-xl flex items-center gap-2 border text-sm font-medium disabled:opacity-50 ${cancelButtonClass}`}
      >
        <X className="h-4 w-4" />
        Отмена
      </button>

      <button
        onClick={onSave}
        disabled={isSaving}
        className="h-12 px-6 py-3 rounded-xl flex items-center gap-2 bg-accent-red hover:bg-accent-red/90 text-white text-sm font-medium disabled:opacity-50"
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
      </button>
    </div>
  );
};