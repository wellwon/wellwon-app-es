
import React from 'react';
import { cn } from '@/lib/utils';
import { colors, animations } from '@/styles/design-tokens';

interface GlassButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  children: React.ReactNode;
  variant?: 'primary' | 'secondary' | 'outline' | 'ghost' | 'accent' | 'destructive';
  size?: 'sm' | 'md' | 'lg' | 'icon';
  loading?: boolean;
  rippleEffect?: boolean;
}

/**
 * GlassButton - кнопка с glass эффектом и анимациями
 * 
 * @param variant - стиль кнопки
 * @param size - размер кнопки
 * @param loading - состояние загрузки
 * @param rippleEffect - включить ripple эффект при клике
 */
export const GlassButton = React.forwardRef<HTMLButtonElement, GlassButtonProps>(({
  children,
  className,
  variant = 'primary',
  size = 'md',
  loading = false,
  rippleEffect = true,
  onClick,
  disabled,
  ...props
}, ref) => {
  const createRipple = (event: React.MouseEvent<HTMLButtonElement>) => {
    if (!rippleEffect) return;
    
    const button = event.currentTarget;
    const circle = document.createElement('span');
    const diameter = Math.max(button.clientWidth, button.clientHeight);
    const radius = diameter / 2;
    
    circle.style.width = circle.style.height = `${diameter}px`;
    circle.style.left = `${event.clientX - button.offsetLeft - radius}px`;
    circle.style.top = `${event.clientY - button.offsetTop - radius}px`;
    circle.classList.add('ripple-effect');
    circle.style.position = 'absolute';
    circle.style.borderRadius = '50%';
    circle.style.background = 'rgba(255, 255, 255, 0.3)';
    circle.style.transform = 'scale(0)';
    circle.style.animation = 'ripple-animation 0.6s linear';
    circle.style.pointerEvents = 'none';
    
    const existingRipple = button.getElementsByClassName('ripple-effect')[0];
    if (existingRipple) {
      existingRipple.remove();
    }
    
    button.appendChild(circle);
    setTimeout(() => circle.remove(), 600);
  };

  const handleClick = (event: React.MouseEvent<HTMLButtonElement>) => {
    if (rippleEffect) createRipple(event);
    onClick?.(event);
  };

  const baseClasses = [
    'glass-button',
    'inline-flex',
    'items-center',
    'justify-center',
    'gap-2',
    'font-medium',
    'transition-all',
    'duration-300',
    'focus-visible:outline-none',
    'disabled:pointer-events-none',
    'disabled:opacity-50',
    'relative',
    'overflow-hidden',
  ];

  const variantClasses = {
    primary: [
      'bg-accent-red',
      'text-text-white',
      'hover:bg-accent-red/90',
      'hover:scale-105',
      'shadow-sm',
    ],
    secondary: [
      'bg-white/5',
      'text-gray-300',
      'border',
      'border-white/10',
      'hover:bg-white/10',
      'hover:text-white',
      'hover:border-white/20',
      'hover:scale-105',
    ],
    outline: [
      'border-2',
      'border-accent-red',
      'bg-dark-gray/40',
      'text-accent-red',
      'hover:bg-accent-red',
      'hover:text-white',
      'backdrop-blur-sm',
    ],
    ghost: [
      'bg-white/5',
      'text-gray-300',
      'border',
      'border-white/10',
      'hover:bg-white/10',
      'hover:border-white/20',
      'hover:scale-105',
    ],
    accent: [
      'bg-accent-red',
      'text-white',
      'hover:-translate-y-2',
      'shadow-lg',
      'hover:shadow-xl',
      'border',
      'border-white/10',
    ],
    destructive: [
      'bg-accent-red',
      'text-text-white',
      'hover:bg-accent-red/90',
      'hover:scale-105',
      'shadow-sm',
      'border',
      'border-accent-red/20',
    ],
  };

  const sizeClasses = {
    sm: 'h-10 px-4 py-2 rounded-lg text-sm',
    md: 'h-12 px-6 py-3 rounded-xl text-sm',
    lg: 'h-14 px-8 py-4 rounded-2xl text-lg',
    icon: 'h-12 w-12 rounded-xl',
  };

  return (
    <button
      ref={ref}
      className={cn(
        ...baseClasses,
        ...variantClasses[variant],
        sizeClasses[size],
        className
      )}
      onClick={handleClick}
      disabled={disabled || loading}
      {...props}
    >
      {loading && (
        <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-current" />
      )}
      {children}
    </button>
  );
});

GlassButton.displayName = "GlassButton";