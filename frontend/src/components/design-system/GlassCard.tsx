
import { cn } from '@/lib/utils';

interface GlassCardProps {
  children: React.ReactNode;
  className?: string;
  variant?: 'default' | 'accent' | 'elevated';
  padding?: 'sm' | 'md' | 'lg' | 'xl';
  onClick?: () => void;
  hover?: boolean;
}

/**
 * GlassCard - базовый компонент карточки с glass эффектом
 * Самодостаточный компонент без зависимости от DesignSystemContext
 * 
 * @param variant - стиль карточки (default, accent, elevated)
 * @param padding - внутренние отступы
 * @param hover - включить hover эффект
 */
export const GlassCard: React.FC<GlassCardProps> = ({
  children,
  className,
  variant = 'default',
  padding = 'lg',
  onClick,
  hover = true,
  ...props
}) => {

  const baseClasses = [
    'glass-card',
    'backdrop-blur-sm',
    'border',
    'transition-all',
    'duration-300',
  ];

  const variantClasses = {
    default: [
      'bg-medium-gray/60',
      'border-white/10',
      ...(hover ? ['hover:bg-medium-gray/80', 'hover:border-white/20', 'hover:-translate-y-1'] : []),
    ],
    accent: [
      'bg-accent-red/10',
      'border-accent-red/20',
      ...(hover ? ['hover:bg-accent-red/15', 'hover:border-accent-red/25', 'hover:shadow-lg', 'hover:shadow-accent-red/10'] : []),
    ],
    elevated: [
      'bg-medium-gray/80',
      'border-white/15',
      'shadow-lg',
      ...(hover ? ['hover:shadow-xl', 'hover:border-white/25', 'hover:-translate-y-2'] : []),
    ],
  };

  const paddingClasses = {
    sm: 'p-3',
    md: 'p-4',
    lg: 'p-6',
    xl: 'p-8',
  };

  return (
    <div
      className={cn(
        ...baseClasses,
        ...variantClasses[variant].filter(Boolean),
        paddingClasses[padding],
        'rounded-xl',
        hover && 'hover-enabled',
        onClick && 'cursor-pointer',
        className
      )}
      onClick={onClick}
      {...props}
    >
      {children}
    </div>
  );
};