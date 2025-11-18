/**
 * WellWon Design Tokens
 * Централизованные токены дизайн-системы
 */

// Цвета - ТОЧНЫЕ значения из дизайн-схемы
export const colors = {
  accent: {
    red: 'hsl(350, 81%, 57%)', // #ea3857 - ТОЧНЫЙ цвет
    'red-light': 'hsl(350, 81%, 67%)', // светлее на 10%
    'red-dark': 'hsl(350, 81%, 47%)', // темнее на 10%
    'red-muted': 'hsl(350, 81%, 77%)', // приглушенный
    green: 'hsl(164, 76%, 39%)', // #13b981
  },
  
  gray: {
    dark: 'hsl(240, 6%, 11%)',    // #1a1a1d - ТОЧНЫЙ цвет
    medium: 'hsl(240, 7%, 15%)',  // #232328 - ТОЧНЫЙ цвет  
    light: 'hsl(240, 7%, 19%)',   // #2c2c33 - ТОЧНЫЙ цвет
  },
  
  text: {
    white: 'hsl(0, 0%, 100%)',     // #ffffff
    gray400: 'hsl(220, 9%, 46%)',  // #6b7280
    muted: 'hsl(240, 4%, 60%)',    // приглушенный текст
  },
  
  glass: {
    background: 'hsla(240, 7%, 15%, 0.6)',
    border: 'hsla(0, 0%, 100%, 0.1)',
    hover: 'hsla(240, 7%, 15%, 0.8)',
  },
  
  states: {
    success: 'hsl(142, 71%, 45%)',
    error: 'hsl(0, 84%, 60%)',
    warning: 'hsl(38, 92%, 50%)',
    info: 'hsl(217, 91%, 60%)',
  }
} as const;

// Размеры и отступы
export const spacing = {
  xs: '4px',
  sm: '8px',
  md: '16px',
  lg: '24px',
  xl: '32px',
  '2xl': '48px',
  '3xl': '64px',
} as const;

// Радиусы скругления
export const radius = {
  sm: '6px',
  md: '8px',
  lg: '12px',
  xl: '16px',
  '2xl': '24px',
  full: '9999px',
} as const;

// Размеры шрифтов
export const fontSize = {
  xs: '12px',
  sm: '14px',
  base: '16px',
  lg: '18px',
  xl: '20px',
  '2xl': '24px',
  '3xl': '30px',
  '4xl': '36px',
  '5xl': '48px',
} as const;

// Анимации
export const animations = {
  duration: {
    fast: '150ms',
    normal: '300ms',
    slow: '500ms',
  },
  
  easing: {
    smooth: 'cubic-bezier(0.4, 0, 0.2, 1)',
    bounce: 'cubic-bezier(0.68, -0.55, 0.265, 1.55)',
    sharp: 'cubic-bezier(0.4, 0, 1, 1)',
  },
} as const;

// Эффекты стекла
export const glassEffect = {
  backdrop: 'blur(12px)',
  background: colors.glass.background,
  border: `1px solid ${colors.glass.border}`,
  shadow: '0 8px 32px rgba(0, 0, 0, 0.3)',
} as const;

// Z-index слои
export const zIndex = {
  dropdown: 1000,
  sticky: 1020,
  fixed: 1030,
  modal: 1040,
  popover: 1050,
  tooltip: 1060,
} as const;

export type Colors = typeof colors;
export type Spacing = typeof spacing;
export type Radius = typeof radius;
export type FontSize = typeof fontSize;
export type Animations = typeof animations;
export type GlassEffect = typeof glassEffect;
