
import React, { forwardRef } from 'react';
import { cn } from '@/lib/utils';
import { Eye, EyeOff, CheckCircle, XCircle } from 'lucide-react';

interface GlassInputProps extends React.InputHTMLAttributes<HTMLInputElement> {
  label?: string;
  error?: string;
  success?: boolean;
  icon?: React.ReactNode;
  showPasswordToggle?: boolean;
  /** Light theme mode - uses DESIGN_SYSTEM.md §17 colors */
  isLightTheme?: boolean;
}

/**
 * GlassInput - поле ввода с поддержкой светлой и тёмной темы
 *
 * Согласно DESIGN_SYSTEM.md §17:
 * - Dark: bg-[#1e1e22], border-white/10, text-white, placeholder:text-gray-500
 * - Light: bg-gray-50, border-gray-300, text-gray-900, placeholder:text-gray-400
 *
 * @param label - подпись к полю
 * @param error - текст ошибки
 * @param success - состояние успеха
 * @param icon - иконка в поле
 * @param showPasswordToggle - показать переключатель пароля
 * @param isLightTheme - светлая тема (по умолчанию тёмная)
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

  // Base classes according to DESIGN_SYSTEM.md §17.5
  const baseClasses = [
    'flex',
    'h-10',  // §17.5: h-10 (40px)
    'w-full',
    'rounded-xl',  // §17.5: rounded-xl
    'border',
    'px-4',
    'py-2',
    'text-sm',
    'transition-none',  // §17.6: NO transitions for instant theme switch
    'focus-visible:outline-none',
    'focus:ring-0',  // §14.3: no ring
    'disabled:cursor-not-allowed',
    'disabled:opacity-50',
  ];

  // Theme-specific classes according to DESIGN_SYSTEM.md §17.4
  const themeClasses = isLightTheme ? [
    'bg-gray-50',           // §17.4: bg-gray-50 (#f9fafb)
    'border-gray-300',      // §17.4: border-gray-300
    'text-gray-900',        // §17.4: text-gray-900
    'placeholder:text-gray-400',  // §17.4: placeholder:text-gray-400
  ] : [
    'bg-[#1e1e22]',         // §17.4: bg-[#1e1e22]
    'border-white/10',      // §17.4: border-white/10
    'text-white',           // §17.4: text-white
    'placeholder:text-gray-500',  // §17.4: placeholder:text-gray-500
  ];

  // Error state classes
  const errorClasses = error ? [
    'border-accent-red/50',
    'focus:border-accent-red',
  ] : [];

  // Success state classes
  const successClasses = success ? [
    'border-green-500/50',
    'focus:border-green-500',
  ] : [];

  // Расчет отступов для иконок валидации
  const hasValidationIcon = success || error;
  const hasPasswordToggle = showPasswordToggle;

  let rightPadding = 'pr-4';
  if (hasPasswordToggle && hasValidationIcon) {
    rightPadding = 'pr-16';
  } else if (hasPasswordToggle || hasValidationIcon) {
    rightPadding = 'pr-10';
  }

  // Label color based on theme
  const labelClass = isLightTheme ? 'text-gray-900' : 'text-white';

  // Icon color based on theme
  const iconClass = isLightTheme ? 'text-gray-500' : 'text-white';

  return (
    <div className="space-y-2">
      {label && (
        <label className={`text-sm font-medium ${labelClass}`}>
          {label}
        </label>
      )}

      <div className="relative">
        {icon && (
          <div className={`absolute left-3 top-1/2 transform -translate-y-1/2 ${iconClass} z-10`}>
            {icon}
          </div>
        )}

        <input
          type={inputType}
          className={cn(
            ...baseClasses,
            ...themeClasses,
            ...errorClasses,
            ...successClasses,
            rightPadding,
            icon && 'pl-10',
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
            "absolute top-1/2 transform -translate-y-1/2",
            hasPasswordToggle ? "right-10" : "right-3"
          )}>
            {success && (
              <CheckCircle
                size={18}
                className="text-green-400"
              />
            )}
            {error && (
              <XCircle
                size={18}
                className="text-accent-red"
              />
            )}
          </div>
        )}

        {showPasswordToggle && (
          <button
            type="button"
            className={`absolute right-3 top-1/2 transform -translate-y-1/2 z-10 ${
              isLightTheme ? 'text-gray-400 hover:text-gray-600' : 'text-white/60 hover:text-white'
            }`}
            onClick={() => setShowPassword(!showPassword)}
          >
            {showPassword ? <EyeOff size={18} /> : <Eye size={18} />}
          </button>
        )}
      </div>

      {/* Error message */}
      {error && (
        <p className="text-xs text-accent-red">{error}</p>
      )}
    </div>
  );
});

GlassInput.displayName = 'GlassInput';
