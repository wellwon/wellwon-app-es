import React from 'react';
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from '@/components/ui/alert-dialog';
import { GlassButton } from '@/components/design-system';
import { LucideIcon } from 'lucide-react';

interface AppConfirmDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onConfirm: () => void;
  title: string;
  description: string;
  confirmText?: string;
  cancelText?: string;
  variant?: 'default' | 'destructive';
  icon?: LucideIcon;
  iconColor?: string;
}

const AppConfirmDialog: React.FC<AppConfirmDialogProps> = ({
  open,
  onOpenChange,
  onConfirm,
  title,
  description,
  confirmText,
  cancelText,
  variant = 'default',
  icon: Icon,
  iconColor = 'text-accent-red'
}) => {
  const handleConfirm = () => {
    onConfirm();
    onOpenChange(false);
  };

  return (
    <AlertDialog open={open} onOpenChange={onOpenChange}>
      <AlertDialogContent className="bg-card/95 backdrop-blur-xl border-white/20 shadow-2xl max-w-md">
        <AlertDialogHeader className="text-center space-y-4">
          {Icon && (
            <div className="flex justify-center">
              <div className="p-4 rounded-full bg-primary/20 border border-primary/30">
                <Icon className="w-8 h-8 text-primary" />
              </div>
            </div>
          )}
          <AlertDialogTitle className="text-foreground text-lg font-semibold text-center">
            {title}
          </AlertDialogTitle>
          <AlertDialogDescription className="text-muted-foreground text-sm leading-relaxed text-center">
            {description}
          </AlertDialogDescription>
        </AlertDialogHeader>
        
        <AlertDialogFooter className="flex flex-col gap-2 sm:flex-row sm:justify-center">
          <GlassButton
            variant="secondary"
            onClick={() => onOpenChange(false)}
            className="flex-1"
          >
            {cancelText || 'Отмена'}
          </GlassButton>
          <GlassButton
            variant={variant === 'destructive' ? 'destructive' : 'primary'}
            onClick={handleConfirm}
            className="flex-1"
          >
            {confirmText || 'Подтвердить'}
          </GlassButton>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  );
};

export default AppConfirmDialog;