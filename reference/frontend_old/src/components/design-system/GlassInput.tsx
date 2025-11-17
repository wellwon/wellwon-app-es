
import React, { forwardRef } from 'react';
import { cn } from '@/lib/utils';
import { Eye, EyeOff, CheckCircle, XCircle } from 'lucide-react';

interface GlassInputProps extends React.InputHTMLAttributes<HTMLInputElement> {
  label?: string;
  error?: string;
  success?: boolean;
  icon?: React.ReactNode;
  showPasswordToggle?: boolean;
}

/**
 * GlassInput - поле ввода с glass эффектом
 * 
 * @param label - подпись к полю
 * @param error - текст ошибки
 * @param success - состояние успеха
 * @param icon - иконка в поле
 * @param showPasswordToggle - показать переключатель пароля
 */
export const GlassInput = forwardRef<HTMLInputElement, GlassInputProps>(({
  className,
  type,
  label,
  error,
  success,
  icon,
  showPasswordToggle,
  ...props
}, ref) => {
  const [showPassword, setShowPassword] = React.useState(false);
  const [isFocused, setIsFocused] = React.useState(false);

  const inputType = showPasswordToggle && showPassword ? 'text' : type;

  const baseClasses = [
    'glass-input',
    'flex',
    'h-12',
    'w-full',
    'rounded-xl',
    'border',
    'border-1',
    'bg-[#1a1a1d]',
    'backdrop-blur-sm',
    'px-4',
    'py-3',
    'text-sm',
    'text-white',
    'placeholder:text-sm',
    'placeholder:text-gray-400',
    'transition-all',
    'duration-300',
    'focus-visible:outline-none',
    'disabled:cursor-not-allowed',
    'disabled:opacity-50',
  ];

  const stateClasses = {
    default: [
      'border-white/10',
      'hover:border-white/20',
      'focus:border-accent-red',
    ],
    error: [
      'border-accent-red/50',
      'focus:border-accent-red',
    ],
    success: [
      'border-green-500/50',
      'focus:border-green-500',
    ],
  };

  const currentState = error ? 'error' : success ? 'success' : 'default';

  // Расчет отступов для иконок валидации
  const hasValidationIcon = success || error;
  const hasPasswordToggle = showPasswordToggle;
  
  let rightPadding = 'pr-4';
  if (hasPasswordToggle && hasValidationIcon) {
    rightPadding = 'pr-16'; // Место для обеих иконок
  } else if (hasPasswordToggle || hasValidationIcon) {
    rightPadding = 'pr-10'; // Место для одной иконки
  }

  return (
    <div className="space-y-2">
      {label && (
        <label className="text-sm font-medium text-white">
          {label}
        </label>
      )}
      
      <div className="relative">
        {icon && (
          <div className="absolute left-3 top-1/2 transform -translate-y-1/2 text-white z-10">
            {icon}
          </div>
        )}
        
        <input
          type={inputType}
          className={cn(
            ...baseClasses,
            ...stateClasses[currentState],
            rightPadding,
            className
          )}
          ref={ref}
          onFocus={() => setIsFocused(true)}
          onBlur={() => setIsFocused(false)}
          {...props}
        />
        
        {/* Validation Icons */}
        {hasValidationIcon && (
          <div className={cn(
            "absolute top-1/2 transform -translate-y-1/2 transition-all duration-300",
            hasPasswordToggle ? "right-10" : "right-3"
          )}>
            {success && (
              <CheckCircle 
                size={18} 
                className="text-green-400 animate-fade-in" 
              />
            )}
            {error && (
              <XCircle 
                size={18} 
                className="text-accent-red animate-fade-in" 
              />
            )}
          </div>
        )}
        
        {showPasswordToggle && (
          <button
            type="button"
            className="absolute right-3 top-1/2 transform -translate-y-1/2 text-white/60 hover:text-white transition-colors z-10"
            onClick={() => setShowPassword(!showPassword)}
          >
            {showPassword ? <EyeOff size={18} /> : <Eye size={18} />}
          </button>
        )}
      </div>
    </div>
  );
});

GlassInput.displayName = 'GlassInput';
