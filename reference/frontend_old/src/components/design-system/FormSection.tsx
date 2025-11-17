import { cn } from '@/lib/utils';
import { GlassCard } from './GlassCard';
interface FormSectionProps {
  title: string;
  description?: string;
  children: React.ReactNode;
  className?: string;
  actions?: React.ReactNode;
}

/**
 * FormSection - секция формы с заголовком и описанием
 * 
 * @param title - заголовок секции
 * @param description - описание секции
 * @param actions - кнопки действий
 */
export const FormSection: React.FC<FormSectionProps> = ({
  title,
  description,
  children,
  className,
  actions
}) => {
  return <GlassCard className={cn('space-y-6', className)} hover={false}>
      <div className="space-y-2">
        
        {description && <p className="text-text-gray-400 text-sm leading-relaxed">
            {description}
          </p>}
      </div>
      
      <div className="space-y-4">
        {children}
      </div>
      
      {actions && <div className="flex justify-end gap-3 pt-4 border-t border-glass-border">
          {actions}
        </div>}
    </GlassCard>;
};