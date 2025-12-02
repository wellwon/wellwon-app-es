import React, { useState } from 'react';
import {
  AlertDialog,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogHeader,
  AlertDialogTitle,
} from '@/components/ui/alert-dialog';
import { GlassButton } from '@/components/design-system';
import { Trash2, Building, AlertTriangle, Loader2 } from 'lucide-react';

interface DeleteGroupDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  groupTitle: string;
  companyId?: number | string | null;
  companyName?: string | null;
  onDeleteAll: () => Promise<void>;
  onPreserveCompany: () => Promise<void>;
  onDeleteGroupOnly?: () => Promise<void>;
}

/**
 * Enhanced delete dialog with options:
 * - Delete everything (company + telegram group + chats)
 * - Preserve company (delete only telegram group, keep company for future linking)
 */
const DeleteGroupDialog: React.FC<DeleteGroupDialogProps> = ({
  open,
  onOpenChange,
  groupTitle,
  companyId,
  companyName,
  onDeleteAll,
  onPreserveCompany,
  onDeleteGroupOnly,
}) => {
  const [isDeleting, setIsDeleting] = useState(false);
  const [deleteType, setDeleteType] = useState<'all' | 'preserve' | 'group' | null>(null);

  const handleDeleteAll = async () => {
    setDeleteType('all');
    setIsDeleting(true);
    try {
      await onDeleteAll();
      onOpenChange(false);
    } finally {
      setIsDeleting(false);
      setDeleteType(null);
    }
  };

  const handlePreserveCompany = async () => {
    setDeleteType('preserve');
    setIsDeleting(true);
    try {
      await onPreserveCompany();
      onOpenChange(false);
    } finally {
      setIsDeleting(false);
      setDeleteType(null);
    }
  };

  const handleDeleteGroupOnly = async () => {
    setDeleteType('group');
    setIsDeleting(true);
    try {
      if (onDeleteGroupOnly) {
        await onDeleteGroupOnly();
      } else {
        await onPreserveCompany();
      }
      onOpenChange(false);
    } finally {
      setIsDeleting(false);
      setDeleteType(null);
    }
  };

  const hasCompany = !!companyId;

  return (
    <AlertDialog open={open} onOpenChange={onOpenChange}>
      <AlertDialogContent className="bg-card/95 backdrop-blur-xl border-white/20 shadow-2xl max-w-md">
        <AlertDialogHeader className="text-center space-y-4">
          <div className="flex justify-center">
            <div className="p-4 rounded-full bg-red-500/20 border border-red-500/30">
              <AlertTriangle className="w-8 h-8 text-red-400" />
            </div>
          </div>
          <AlertDialogTitle className="text-foreground text-lg font-semibold text-center">
            Удалить группу?
          </AlertDialogTitle>
          <AlertDialogDescription className="text-muted-foreground text-sm leading-relaxed text-center">
            Группа "<span className="text-white font-medium">{groupTitle}</span>" будет удалена.
            {hasCompany && companyName && (
              <>
                <br />
                <span className="text-yellow-400">Привязана к компании: {companyName}</span>
              </>
            )}
          </AlertDialogDescription>
        </AlertDialogHeader>

        <div className="space-y-3 mt-4">
          {hasCompany ? (
            <>
              {/* Option 1: Delete everything */}
              <GlassButton
                variant="destructive"
                onClick={handleDeleteAll}
                disabled={isDeleting}
                className="w-full justify-center gap-2"
              >
                {isDeleting && deleteType === 'all' ? (
                  <Loader2 className="w-4 h-4 animate-spin" />
                ) : (
                  <Trash2 className="w-4 h-4" />
                )}
                Удалить всё
                <span className="text-xs opacity-70 ml-1">(компанию, чаты, группу)</span>
              </GlassButton>

              {/* Option 2: Preserve company */}
              <GlassButton
                variant="secondary"
                onClick={handlePreserveCompany}
                disabled={isDeleting}
                className="w-full justify-center gap-2 border-yellow-500/30 hover:border-yellow-500/50"
              >
                {isDeleting && deleteType === 'preserve' ? (
                  <Loader2 className="w-4 h-4 animate-spin" />
                ) : (
                  <Building className="w-4 h-4 text-yellow-400" />
                )}
                Сохранить компанию
                <span className="text-xs opacity-70 ml-1">(для привязки к другой группе)</span>
              </GlassButton>
            </>
          ) : (
            /* No company - just delete group */
            <GlassButton
              variant="destructive"
              onClick={handleDeleteGroupOnly}
              disabled={isDeleting}
              className="w-full justify-center gap-2"
            >
              {isDeleting && deleteType === 'group' ? (
                <Loader2 className="w-4 h-4 animate-spin" />
              ) : (
                <Trash2 className="w-4 h-4" />
              )}
              Удалить группу
            </GlassButton>
          )}

          {/* Cancel button */}
          <GlassButton
            variant="ghost"
            onClick={() => onOpenChange(false)}
            disabled={isDeleting}
            className="w-full justify-center"
          >
            Отмена
          </GlassButton>
        </div>

        {/* Warning message */}
        <p className="text-xs text-center text-muted-foreground mt-4">
          Это действие нельзя отменить
        </p>
      </AlertDialogContent>
    </AlertDialog>
  );
};

export default DeleteGroupDialog;
