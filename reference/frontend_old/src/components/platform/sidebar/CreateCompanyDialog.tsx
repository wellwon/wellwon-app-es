import React from 'react';
import { Building } from 'lucide-react';
import { AppConfirmDialog } from '@/components/shared';

interface CreateCompanyDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onConfirm: () => void;
}

const CreateCompanyDialog = ({ open, onOpenChange, onConfirm }: CreateCompanyDialogProps) => {
  return (
    <AppConfirmDialog
      open={open}
      onOpenChange={onOpenChange}
      onConfirm={onConfirm}
      title="Создание новой компании"
      description="Вы точно хотите создать ещё одну компанию?"
      confirmText="Создать"
      cancelText="Отмена"
      icon={Building}
    />
  );
};

export default CreateCompanyDialog;