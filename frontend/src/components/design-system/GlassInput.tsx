
import React, { forwardRef } from 'react';
import { cn } from '@/lib/utils';
import { Eye, EyeOff, CheckCircle, XCircle } from 'lucide-react';

interface GlassInputProps extends React.InputHTMLAttributes<HTMLInputElement> {
  label?: string;
  error?: string;
  success?: boolean;
  icon?: React.ReactNode;
  showPasswordToggle?: boolean;
  isLightTheme?: boolean;
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
  isLightTheme = false,
  ...props
}, ref) => {
  const [showPassword, setShowPassword] = React.useState(false);
  const [isFocused, setIsFocused] = React.useState(false);

  const inputType = showPasswordToggle && showPassword ? 'text' : type;

  // Theme-aware classes per DESIGN_SYSTEM.md §17
  const themeClasses = isLightTheme ? [
    'bg-gray-50',
    'border-gray-300',
    'text-gray-900',
    'placeholder:text-gray-400',
  ] : [
    'bg-[#1e1e22]',
    'border-white/10',
    'text-white',
    'placeholder:text-gray-500',
  ];

  const baseClasses = [
    'flex',
    'h-10',
    'w-full',
    'rounded-xl',
    'border',
    'px-3',
    'py-2',
    'text-sm',
    'placeholder:text-sm',
    'focus-visible:outline-none',
    'focus:outline-none',
    'focus:ring-0',
    'transition-none',
    'disabled:cursor-not-allowed',
    'disabled:opacity-50',
    ...themeClasses,
  ];

  const stateClasses = {
    default: isLightTheme ? [
      'hover:border-gray-400',
    ] : [
      'hover:border-white/20',
    ],
    error: [
      'border-red-500/50',
    ],
    success: [
      'border-green-500/50',
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
    <div className="space-y-1.5">
      {label && (
        <label className={`text-sm ${isLightTheme ? 'text-gray-700' : 'text-white'}`}>
          {label}
        </label>
      )}

      <div className="relative">
        {icon && (
          <div className={`absolute left-3 top-1/2 transform -translate-y-1/2 z-10 ${isLightTheme ? 'text-gray-500' : 'text-white'}`}>
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
