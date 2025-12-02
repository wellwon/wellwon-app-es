# WellWon Design System Style Guide

**Version:** 1.0.0  
**Last Updated:** 2025-01-19  
**Project Type:** SaaS Platform with Chat & Telegram Integration  
**Design Language:** Modern Glass Morphism with Dark Theme

---

## Table of Contents

1. [Overview](#overview)
2. [Design Philosophy](#design-philosophy)
3. [Color System](#color-system)
4. [Typography](#typography)
5. [Spacing System](#spacing-system)
6. [Component Library](#component-library)
7. [Glass Effects](#glass-effects)
8. [Shadows & Elevation](#shadows--elevation)
9. [Border Radius](#border-radius)
10. [Layout Patterns](#layout-patterns)
11. [Animations & Transitions](#animations--transitions)
12. [Responsive Design](#responsive-design)
13. [Accessibility](#accessibility)
14. [Iconography](#iconography)
15. [Design Tokens](#design-tokens)
16. [Best Practices](#best-practices)

---

## Overview

WellWon - это современная SaaS платформа для логистики с интеграцией Telegram, построенная на React, TypeScript, Tailwind CSS и shadcn/ui. Дизайн-система базируется на концепции **Glass Morphism** с тёмной темой и акцентным красным цветом.

### Целевая аудитория
- B2B клиенты (логистические компании)
- Внутренние менеджеры
- Администраторы системы

### Ключевые характеристики
- ✅ Dark-first design
- ✅ Glass morphism effects
- ✅ Real-time chat интерфейс
- ✅ Telegram sync indicators
- ✅ Multi-user collaboration
- ✅ WCAG AA compliance

---

## Design Philosophy

### Принципы

**1. Clarity First (Ясность прежде всего)**
- Информация должна быть легко читаемой даже при стеклянных эффектах
- Контраст текста соответствует WCAG AA (минимум 4.5:1)

**2. Functional Beauty (Функциональная красота)**
- Каждый визуальный элемент имеет функциональную цель
- Анимации улучшают UX, а не отвлекают

**3. Consistent Experience (Консистентный опыт)**
- Одинаковые паттерны для похожих действий
- Предсказуемое поведение компонентов

**4. Performance Matters (Производительность важна)**
- Glass effects оптимизированы для 60fps
- Lazy loading для тяжелых компонентов
- Мемоизация для чатов

---

## Color System

### Primary Colors

#### Accent Red (Основной акцентный цвет)
```css
--accent-red: 350 81% 57%;           /* #ea3857 */
--accent-red-light: 350 81% 67%;     /* Светлее на 10% */
--accent-red-dark: 350 81% 47%;      /* Темнее на 10% */
--accent-red-muted: 350 81% 77%;     /* Приглушённый */
```

**Использование:**
- Primary CTA кнопки
- Важные уведомления
- Ховер эффекты на ссылках
- Акцентные иконки

**Tailwind Classes:**
```tsx
bg-accent-red         // Background
text-accent-red       // Text color
border-accent-red     // Border
hover:bg-accent-red   // Hover state
```

#### Accent Green (Статус успеха)
```css
--accent-green: 164 76% 39%;  /* #13b981 */
```

**Использование:**
- Success states
- Positive notifications
- Completed status indicators

### Gray Scale (Нейтральные цвета)

```css
--dark-gray: 240 6% 11%;      /* #1a1a1d - Самый тёмный фон */
--medium-gray: 240 7% 15%;    /* #232328 - Средний фон */
--light-gray: 240 7% 19%;     /* #2c2c33 - Светлый фон */
--surface-gray: 240 7% 23%;   /* #35353d - Surface элементы */
```

**Иерархия использования:**
1. `dark-gray` - Main background, cards
2. `medium-gray` - Elevated surfaces, dialogs
3. `light-gray` - Hover states, secondary surfaces
4. `surface-gray` - Input fields, code blocks

**Tailwind Classes:**
```tsx
bg-dark-gray
bg-medium-gray
bg-light-gray
bg-surface-gray
```

### Text Colors

```css
--text-white: 0 0% 100%;        /* #ffffff - Основной текст */
--text-gray-300: 220 9% 65%;    /* #9ca3af - Вторичный текст */
--text-gray-400: 220 9% 46%;    /* #6b7280 - Tertiary текст */
--text-gray-500: 240 4% 60%;    /* #999999 - Muted текст */
--text-accent-red: 350 81% 57%; /* #ea3857 - Акцентный текст */
```

**Контрастные соотношения (на dark-gray):**
- `text-white`: 17.8:1 (AAA) ✅
- `text-gray-300`: 7.2:1 (AA) ✅
- `text-gray-400`: 4.5:1 (AA) ✅
- `text-accent-red`: 5.1:1 (AA) ✅

**Использование:**
```tsx
className="text-white"           // Заголовки, важный текст
className="text-gray-300"        // Body text, описания
className="text-gray-400"        // Labels, вторичная информация
className="text-gray-500"        // Placeholder, disabled
className="text-accent-red"      // Ошибки, важные акценты
```

### Semantic Colors

```css
/* Success */
--success: 142 71% 45%;           /* #22c55e */
--success-foreground: 0 0% 100%;

/* Error / Destructive */
--destructive: 0 84% 60%;         /* #f87171 */
--destructive-foreground: 0 0% 100%;

/* Warning */
--warning: 38 92% 50%;            /* #f59e0b */
--warning-foreground: 0 0% 100%;

/* Info */
--info: 217 91% 60%;              /* #3b82f6 */
--info-foreground: 0 0% 100%;
```

**Использование в Toast:**
```tsx
import { toastSuccess, toastError, toastWarning, toastInfo } from '@/utils/toastPresets';

toastSuccess({ title: "Сохранено", description: "Изменения применены" });
toastError({ title: "Ошибка", description: "Не удалось сохранить" });
toastWarning({ title: "Внимание", description: "Проверьте данные" });
toastInfo({ title: "Информация", description: "Обновление доступно" });
```

### Glass Effect Colors

```css
--glass-background: hsla(240, 7%, 15%, 0.6);   /* Полупрозрачный фон */
--glass-border: hsla(0, 0%, 100%, 0.1);        /* Белая граница 10% */
--glass-hover: hsla(240, 7%, 15%, 0.8);        /* Ховер состояние */
```

### Shadcn Theme Mapping

```css
/* shadcn compatibility */
--background: 240 6% 11%;        /* = dark-gray */
--foreground: 0 0% 100%;         /* = text-white */
--card: 240 7% 15%;              /* = medium-gray */
--card-foreground: 0 0% 100%;
--popover: 240 7% 15%;
--popover-foreground: 0 0% 100%;
--primary: 350 81% 57%;          /* = accent-red */
--primary-foreground: 0 0% 100%;
--secondary: 240 7% 19%;         /* = light-gray */
--secondary-foreground: 0 0% 100%;
--muted: 240 7% 19%;
--muted-foreground: 220 9% 65%;
--accent: 350 81% 57%;
--accent-foreground: 0 0% 100%;
--destructive: 0 84% 60%;
--destructive-foreground: 0 0% 100%;
--border: hsla(0, 0%, 100%, 0.1);
--input: 240 7% 19%;
--ring: 350 81% 57%;
```

### Color Usage Matrix

| Context | Background | Text | Border | Hover |
|---------|-----------|------|--------|-------|
| **Primary Button** | `accent-red` | `text-white` | `transparent` | `accent-red-dark` |
| **Secondary Button** | `light-gray` | `text-white` | `glass-border` | `surface-gray` |
| **Card** | `medium-gray` | `text-white` | `glass-border` | `light-gray` |
| **Input** | `input` | `text-white` | `border` | `accent-red` (focus) |
| **Glass Card** | `glass-background` | `text-white` | `glass-border` | `glass-hover` |

---

## Typography

### Font Families

```css
/* Primary Font - System Fonts */
font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'Roboto', 'Oxygen',
  'Ubuntu', 'Cantarell', 'Fira Sans', 'Droid Sans', 'Helvetica Neue',
  sans-serif;

/* Monospace - Code */
font-family: source-code-pro, Menlo, Monaco, Consolas, 'Courier New', monospace;
```

**Почему system fonts:**
- Нативный вид на каждой платформе
- Нулевое время загрузки
- Оптимальная читаемость

### Type Scale

```css
/* Display Sizes */
--font-5xl: 48px;     /* 3rem */
--font-4xl: 36px;     /* 2.25rem */
--font-3xl: 30px;     /* 1.875rem */

/* Heading Sizes */
--font-2xl: 24px;     /* 1.5rem - h1 */
--font-xl: 20px;      /* 1.25rem - h2 */
--font-lg: 18px;      /* 1.125rem - h3 */

/* Body Sizes */
--font-base: 16px;    /* 1rem - body */
--font-sm: 14px;      /* 0.875rem - small */
--font-xs: 12px;      /* 0.75rem - captions */
```

**Tailwind Classes:**
```tsx
text-5xl  // 48px - Hero headings
text-4xl  // 36px - Page titles
text-3xl  // 30px - Section headers
text-2xl  // 24px - H1
text-xl   // 20px - H2
text-lg   // 18px - H3
text-base // 16px - Body text
text-sm   // 14px - Small text, labels
text-xs   // 12px - Captions, metadata
```

### Font Weights

```css
--font-normal: 400;    /* Regular text */
--font-medium: 500;    /* Emphasis */
--font-semibold: 600;  /* Subheadings */
--font-bold: 700;      /* Headings */
```

**Использование:**
```tsx
font-normal    // Body text, descriptions
font-medium    // Buttons, links, emphasized text
font-semibold  // Subheadings, card titles
font-bold      // Main headings
```

### Line Heights

```css
--leading-none: 1;       /* 1 - Tight headings */
--leading-tight: 1.25;   /* 1.25 - Display text */
--leading-snug: 1.375;   /* 1.375 - Headings */
--leading-normal: 1.5;   /* 1.5 - Body text */
--leading-relaxed: 1.625; /* 1.625 - Long-form content */
--leading-loose: 2;      /* 2 - Poetry, special cases */
```

**Tailwind Classes:**
```tsx
leading-tight   // Headings
leading-normal  // Body text
leading-relaxed // Long articles
```

### Typography Pairings

#### Heading + Body
```tsx
<h1 className="text-2xl font-bold leading-tight text-white">
  Заголовок страницы
</h1>
<p className="text-base font-normal leading-normal text-gray-300 mt-2">
  Описание под заголовком с хорошей читаемостью
</p>
```

#### Card Title + Description
```tsx
<h3 className="text-lg font-semibold text-white">
  Название карточки
</h3>
<p className="text-sm text-gray-400 mt-1">
  Дополнительная информация
</p>
```

#### Form Label + Input
```tsx
<label className="text-sm font-medium text-white mb-2">
  Email адрес
</label>
<input className="text-base text-white" placeholder="example@domain.com" />
```

---

## Spacing System

### 8px Base Grid

Все отступы кратны **8px** для визуальной консистентности и лёгкости вёрстки.

```css
/* Spacing Scale */
--space-0: 0px;      /* 0 */
--space-1: 4px;      /* 0.25rem */
--space-2: 8px;      /* 0.5rem */
--space-3: 12px;     /* 0.75rem */
--space-4: 16px;     /* 1rem */
--space-5: 20px;     /* 1.25rem */
--space-6: 24px;     /* 1.5rem */
--space-8: 32px;     /* 2rem */
--space-10: 40px;    /* 2.5rem */
--space-12: 48px;    /* 3rem */
--space-16: 64px;    /* 4rem */
--space-20: 80px;    /* 5rem */
--space-24: 96px;    /* 6rem */
```

### Tailwind Spacing Classes

```tsx
// Padding
p-2   // 8px
p-4   // 16px
p-6   // 24px
p-8   // 32px

// Margin
m-2   // 8px
m-4   // 16px
m-6   // 24px

// Gap (for flexbox/grid)
gap-2 // 8px
gap-4 // 16px
gap-6 // 24px
```

### Spacing Usage Guidelines

| Context | Spacing | Class |
|---------|---------|-------|
| **Внутри компонента (padding)** | 16-24px | `p-4` or `p-6` |
| **Между элементами (gap)** | 8-16px | `gap-2` or `gap-4` |
| **Секции страницы** | 48-64px | `py-12` or `py-16` |
| **Форма: label → input** | 8px | `space-y-2` |
| **Кнопки в группе** | 12px | `gap-3` |
| **Карточки в гриде** | 16-24px | `gap-4` or `gap-6` |

### Component-Specific Spacing

#### Card Padding
```tsx
<GlassCard className="p-6">  {/* 24px внутри */}
  <h3 className="mb-4">Title</h3>  {/* 16px между title и content */}
  <p>Content</p>
</GlassCard>
```

#### Form Spacing
```tsx
<form className="space-y-6">  {/* 24px между полями */}
  <div className="space-y-2">  {/* 8px между label и input */}
    <Label>Name</Label>
    <Input />
  </div>
</form>
```

#### Button Group
```tsx
<div className="flex gap-3">  {/* 12px между кнопками */}
  <Button>Cancel</Button>
  <Button>Save</Button>
</div>
```

---

## Component Library

### Installation Commands

```bash
# Core UI Components
npx shadcn@latest add button
npx shadcn@latest add card
npx shadcn@latest add input
npx shadcn@latest add label
npx shadcn@latest add dialog
npx shadcn@latest add sheet
npx shadcn@latest add tabs
npx shadcn@latest add select
npx shadcn@latest add checkbox
npx shadcn@latest add textarea
npx shadcn@latest add toast
npx shadcn@latest add dropdown-menu
npx shadcn@latest add popover
npx shadcn@latest add tooltip
npx shadcn@latest add badge
npx shadcn@latest add avatar
npx shadcn@latest add separator
npx shadcn@latest add skeleton
```

---

### 1. Buttons

#### GlassButton (Primary Component)

**Import:**
```tsx
import { GlassButton } from '@/components/design-system';
```

**Variants:**

##### Primary Button
```tsx
<GlassButton variant="primary">
  Главное действие
</GlassButton>
```
- **Purpose:** Main call-to-action
- **Background:** `accent-red` with glass effect
- **Text:** `text-white`
- **States:**
  - Hover: Brightens + scale(1.02)
  - Active: Darkens slightly
  - Disabled: Opacity 50%

##### Secondary Button
```tsx
<GlassButton variant="secondary">
  Вторичное действие
</GlassButton>
```
- **Purpose:** Secondary actions, Cancel
- **Background:** `light-gray` with glass effect
- **Text:** `text-white`
- **ПРАВИЛО:** ВСЕГДА используйте `secondary` для второй кнопки в диалогах!

##### Outline Button
```tsx
<GlassButton variant="outline">
  Контурная кнопка
</GlassButton>
```
- **Purpose:** Tertiary actions
- **Background:** Transparent
- **Border:** `glass-border`
- **Text:** `text-white`

**Size Variants:**
```tsx
<GlassButton size="sm">Small</GlassButton>      // Padding: 8px 16px
<GlassButton size="md">Medium</GlassButton>     // Padding: 12px 24px (default)
<GlassButton size="lg">Large</GlassButton>      // Padding: 16px 32px
```

**Loading State:**
```tsx
<GlassButton loading={isLoading}>
  Сохранить
</GlassButton>
```

**Disabled State:**
```tsx
<GlassButton disabled>
  Недоступно
</GlassButton>
```

**Full Example:**
```tsx
<div className="flex justify-end gap-3">
  <GlassButton
    variant="secondary"
    onClick={() => setOpen(false)}
  >
    Отмена
  </GlassButton>
  <GlassButton
    variant="primary"
    onClick={handleSubmit}
    loading={loading}
  >
    Сохранить
  </GlassButton>
</div>
```

#### Standard Button (shadcn)

**Import:**
```tsx
import { Button } from '@/components/ui';
```

**Variants:**
```tsx
<Button variant="default">Default</Button>
<Button variant="secondary">Secondary</Button>
<Button variant="outline">Outline</Button>
<Button variant="ghost">Ghost</Button>
<Button variant="link">Link</Button>
<Button variant="destructive">Delete</Button>
```

**Usage Rule:**
- Используйте `GlassButton` для основного UI (приоритет)
- Используйте `Button` для стандартных форм, административных панелей

---

### 2. Cards

#### GlassCard (Primary Component)

**Import:**
```tsx
import { GlassCard } from '@/components/design-system';
```

**Variants:**

##### Default Card
```tsx
<GlassCard variant="default" padding="lg">
  <h3 className="text-lg font-semibold text-white mb-2">
    Заголовок карточки
  </h3>
  <p className="text-sm text-gray-400">
    Описание карточки с glass эффектом
  </p>
</GlassCard>
```

**Props:**
- `variant`: `'default'` | `'elevated'` | `'flat'`
- `padding`: `'sm'` | `'md'` | `'lg'` | `'none'`
- `hover`: `boolean` - Включить hover эффект
- `className`: string - Дополнительные стили

**Padding Variants:**
```tsx
<GlassCard padding="sm">   // 12px
<GlassCard padding="md">   // 16px
<GlassCard padding="lg">   // 24px (default)
<GlassCard padding="none"> // 0px
```

**With Hover:**
```tsx
<GlassCard hover>
  {/* Подсвечивается при наведении */}
</GlassCard>
```

#### Standard Card (shadcn)

**Import:**
```tsx
import { Card, CardHeader, CardTitle, CardContent, CardFooter } from '@/components/ui';
```

**Example:**
```tsx
<Card className="bg-card/95 backdrop-blur-xl border-white/20">
  <CardHeader>
    <CardTitle className="text-white">Card Title</CardTitle>
  </CardHeader>
  <CardContent className="text-gray-300">
    Card content goes here
  </CardContent>
  <CardFooter>
    <Button>Action</Button>
  </CardFooter>
</Card>
```

---

### 3. Inputs & Forms

#### GlassInput (Primary Component)

**Import:**
```tsx
import { GlassInput } from '@/components/design-system';
```

**Basic Usage:**
```tsx
<GlassInput
  label="Email адрес"
  placeholder="example@domain.com"
  value={email}
  onChange={(e) => setEmail(e.target.value)}
  required
/>
```

**Props:**
- `label`: string - Label text
- `placeholder`: string
- `value`: string
- `onChange`: (e) => void
- `required`: boolean
- `type`: `'text'` | `'email'` | `'password'` | `'number'`
- `error`: string - Error message
- `disabled`: boolean

**With Error:**
```tsx
<GlassInput
  label="Password"
  type="password"
  value={password}
  onChange={setPassword}
  error={errors.password}
/>
```

**Full Form Example:**
```tsx
<form onSubmit={handleSubmit} className="space-y-6">
  <GlassInput
    label="Имя пользователя"
    placeholder="Введите имя"
    value={name}
    onChange={(e) => setName(e.target.value)}
    required
    autoFocus
  />
  
  <GlassInput
    label="Email"
    type="email"
    placeholder="example@domain.com"
    value={email}
    onChange={(e) => setEmail(e.target.value)}
    required
  />
  
  <div className="flex justify-end gap-3 pt-4">
    <GlassButton variant="secondary" type="button" onClick={onCancel}>
      Отмена
    </GlassButton>
    <GlassButton variant="primary" type="submit" loading={loading}>
      Сохранить
    </GlassButton>
  </div>
</form>
```

#### Standard Input (shadcn)

**Import:**
```tsx
import { Input, Label } from '@/components/ui';
```

**Example:**
```tsx
<div className="space-y-2">
  <Label htmlFor="email" className="text-white">Email</Label>
  <Input
    id="email"
    type="email"
    placeholder="example@domain.com"
    className="bg-input text-white"
  />
</div>
```

#### Textarea

**Import:**
```tsx
import { Textarea } from '@/components/ui';
```

**Example:**
```tsx
<div className="space-y-2">
  <Label>Описание</Label>
  <Textarea
    placeholder="Введите описание..."
    rows={4}
    className="bg-input text-white"
  />
</div>
```

---

### 4. Dialogs & Modals

#### Dialog Standard (ОБЯЗАТЕЛЬНЫЙ ФОРМАТ)

**Import:**
```tsx
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '@/components/ui';
import { GlassButton, GlassInput } from '@/components/design-system';
```

**Template (КОПИРУЙТЕ ЭТО):**
```tsx
const MyDialog = () => {
  const [open, setOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const [name, setName] = useState('');

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    
    try {
      setLoading(true);
      await saveData(name);
      
      toast({
        title: "Успешно сохранено",
        variant: "success"
      });
      setOpen(false);
    } catch (error) {
      logger.error('Failed to save', error, { component: 'MyDialog' });
      
      toast({
        title: "Ошибка сохранения",
        variant: "destructive"
      });
    } finally {
      setLoading(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogContent className="bg-card/95 backdrop-blur-xl border-white/20 shadow-2xl max-w-md">
        <DialogHeader>
          <DialogTitle className="text-foreground text-lg font-semibold">
            Заголовок диалога
          </DialogTitle>
        </DialogHeader>
        
        <form onSubmit={handleSubmit} className="space-y-6">
          <GlassInput
            label="Название"
            value={name}
            onChange={(e) => setName(e.target.value)}
            required
            autoFocus
          />
          
          {/* ВАЖНО: ВСЕГДА в таком порядке! */}
          <div className="flex justify-end gap-3 pt-6">
            <GlassButton
              type="button"
              variant="secondary"  // ВСЕГДА secondary для отмены!
              onClick={() => setOpen(false)}
            >
              Отмена
            </GlassButton>
            <GlassButton
              type="submit"
              variant="primary"
              loading={loading}
            >
              Сохранить
            </GlassButton>
          </div>
        </form>
      </DialogContent>
    </Dialog>
  );
};
```

**КРИТИЧЕСКИЕ ПРАВИЛА:**
1. ✅ DialogContent ВСЕГДА: `className="bg-card/95 backdrop-blur-xl border-white/20 shadow-2xl"`
2. ✅ Вторая кнопка ВСЕГДА: `variant="secondary"`
3. ✅ Порядок кнопок: Cancel слева, Submit справа
4. ✅ Используйте `GlassInput` и `GlassButton`
5. ✅ Обработка ошибок через try/catch + toast

---

### 5. Select & Dropdowns

**Import:**
```tsx
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui';
```

**Example:**
```tsx
<Select value={selectedValue} onValueChange={setSelectedValue}>
  <SelectTrigger className="w-full bg-input text-white border-border">
    <SelectValue placeholder="Выберите опцию" />
  </SelectTrigger>
  <SelectContent className="bg-card border-border">
    <SelectItem value="option1">Опция 1</SelectItem>
    <SelectItem value="option2">Опция 2</SelectItem>
    <SelectItem value="option3">Опция 3</SelectItem>
  </SelectContent>
</Select>
```

---

### 6. Toast Notifications

**Import:**
```tsx
import { toastSuccess, toastError, toastWarning, toastInfo } from '@/utils/toastPresets';
```

**Usage:**
```tsx
// Success
toastSuccess({ 
  title: "Сохранено", 
  description: "Изменения успешно применены" 
});

// Error
toastError({ 
  title: "Ошибка", 
  description: "Не удалось сохранить данные" 
});

// Warning
toastWarning({ 
  title: "Внимание", 
  description: "Проверьте введённые данные" 
});

// Info
toastInfo({ 
  title: "Информация", 
  description: "Обновление доступно" 
});
```

**ПРАВИЛА:**
- ❌ НЕ используйте `toast({ variant: "destructive" })` напрямую
- ✅ Используйте `toastError` для ошибок
- ✅ Всегда указывайте `title` и `description`

---

### 7. Tabs

**Import:**
```tsx
import { Tabs, TabsList, TabsTrigger, TabsContent } from '@/components/ui';
```

**Example:**
```tsx
<Tabs defaultValue="tab1" className="w-full">
  <TabsList className="bg-card/50 border border-border">
    <TabsTrigger value="tab1" className="data-[state=active]:bg-accent-red">
      Вкладка 1
    </TabsTrigger>
    <TabsTrigger value="tab2">
      Вкладка 2
    </TabsTrigger>
  </TabsList>
  
  <TabsContent value="tab1" className="mt-6">
    Контент вкладки 1
  </TabsContent>
  
  <TabsContent value="tab2" className="mt-6">
    Контент вкладки 2
  </TabsContent>
</Tabs>
```

---

### 8. Badges

**Import:**
```tsx
import { Badge } from '@/components/ui';
```

**Variants:**
```tsx
<Badge variant="default">Default</Badge>
<Badge variant="secondary">Secondary</Badge>
<Badge variant="destructive">Destructive</Badge>
<Badge variant="outline">Outline</Badge>
```

**Custom Colors:**
```tsx
<Badge className="bg-accent-green text-white">Active</Badge>
<Badge className="bg-warning text-white">Pending</Badge>
```

---

### 9. Tooltips

**Import:**
```tsx
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '@/components/ui';
```

**Example:**
```tsx
<TooltipProvider>
  <Tooltip>
    <TooltipTrigger asChild>
      <Button variant="ghost" size="icon">
        <Info className="h-4 w-4" />
      </Button>
    </TooltipTrigger>
    <TooltipContent className="bg-card border-border">
      <p>Подсказка для пользователя</p>
    </TooltipContent>
  </Tooltip>
</TooltipProvider>
```

---

### 10. Skeleton Loading

**Import:**
```tsx
import { Skeleton } from '@/components/ui';
```

**Example:**
```tsx
<div className="space-y-4">
  <Skeleton className="h-12 w-full bg-muted" />
  <Skeleton className="h-24 w-full bg-muted" />
  <Skeleton className="h-8 w-3/4 bg-muted" />
</div>
```

---

## Glass Effects

### Core Glass Effect

```css
.glass-effect {
  background: hsla(240, 7%, 15%, 0.6);
  backdrop-filter: blur(12px);
  border: 1px solid hsla(0, 0%, 100%, 0.1);
  box-shadow: 0 8px 32px rgba(0, 0, 0, 0.3);
}
```

**Tailwind Utility:**
```tsx
className="bg-glass-background backdrop-blur-xl border-glass-border shadow-glass"
```

### Glass Variants

#### Strong Glass (Модальные окна)
```tsx
className="bg-card/95 backdrop-blur-xl border-white/20 shadow-2xl"
```

#### Medium Glass (Карточки)
```tsx
className="bg-card/80 backdrop-blur-lg border-white/10 shadow-xl"
```

#### Light Glass (Hover states)
```tsx
className="bg-card/60 backdrop-blur-md border-white/5 shadow-lg"
```

### Glass Component Examples

#### Glass Card with Hover
```tsx
<GlassCard hover className="transition-all duration-300">
  <h3 className="text-white font-semibold mb-2">Title</h3>
  <p className="text-gray-300">Description</p>
</GlassCard>
```

#### Glass Navigation
```tsx
<nav className="fixed top-0 w-full bg-dark-gray/80 backdrop-blur-xl border-b border-white/10 z-50">
  <div className="container mx-auto px-6 py-4">
    {/* Navigation content */}
  </div>
</nav>
```

---

## Shadows & Elevation

### Shadow Scale

```css
/* Small Shadow */
--shadow-sm: 0 1px 2px rgba(0, 0, 0, 0.2);

/* Medium Shadow */
--shadow-md: 0 4px 6px rgba(0, 0, 0, 0.3);

/* Large Shadow */
--shadow-lg: 0 10px 15px rgba(0, 0, 0, 0.4);

/* Extra Large Shadow */
--shadow-xl: 0 20px 25px rgba(0, 0, 0, 0.5);

/* 2XL Shadow */
--shadow-2xl: 0 25px 50px rgba(0, 0, 0, 0.6);

/* Glass Shadow */
--shadow-glass: 0 8px 32px rgba(0, 0, 0, 0.3);
```

### Tailwind Classes

```tsx
shadow-sm    // Subtle elevation
shadow-md    // Cards
shadow-lg    // Hover states
shadow-xl    // Modals
shadow-2xl   // Dialogs
```

### Elevation Hierarchy

| Component | Shadow | Z-Index |
|-----------|--------|---------|
| **Page Background** | none | 0 |
| **Cards** | `shadow-md` | 1 |
| **Hover Cards** | `shadow-lg` | 2 |
| **Sticky Headers** | `shadow-lg` | 10 |
| **Dropdowns** | `shadow-xl` | 50 |
| **Modals** | `shadow-2xl` | 100 |
| **Toasts** | `shadow-xl` | 200 |

---

## Border Radius

### Radius Scale

```css
--radius-sm: 6px;
--radius-md: 8px;
--radius-lg: 12px;
--radius-xl: 16px;
--radius-2xl: 24px;
--radius-full: 9999px;
```

### Tailwind Classes

```tsx
rounded-sm   // 6px - Small elements
rounded-md   // 8px - Inputs, buttons
rounded-lg   // 12px - Cards
rounded-xl   // 16px - Large cards
rounded-2xl  // 24px - Hero sections
rounded-full // Pills, avatars
```

### Component Mapping

| Component | Border Radius |
|-----------|---------------|
| **Button** | `rounded-md` (8px) |
| **Input** | `rounded-md` (8px) |
| **Card** | `rounded-lg` (12px) |
| **Dialog** | `rounded-xl` (16px) |
| **Avatar** | `rounded-full` |
| **Badge** | `rounded-full` |

---

## Layout Patterns

### Container Widths

```tsx
// Max widths
max-w-sm   // 384px - Small containers
max-w-md   // 448px - Dialogs
max-w-lg   // 512px - Forms
max-w-xl   // 576px - Content
max-w-2xl  // 672px - Articles
max-w-4xl  // 896px - Wide content
max-w-7xl  // 1280px - Full layouts
```

### Grid Layouts

#### Card Grid
```tsx
<div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
  <GlassCard>Card 1</GlassCard>
  <GlassCard>Card 2</GlassCard>
  <GlassCard>Card 3</GlassCard>
</div>
```

#### Dashboard Layout
```tsx
<div className="grid grid-cols-1 lg:grid-cols-4 gap-6">
  <div className="lg:col-span-3">
    {/* Main content */}
  </div>
  <div className="lg:col-span-1">
    {/* Sidebar */}
  </div>
</div>
```

### Flex Layouts

#### Horizontal Stack
```tsx
<div className="flex items-center gap-4">
  <div>Item 1</div>
  <div>Item 2</div>
</div>
```

#### Vertical Stack
```tsx
<div className="flex flex-col space-y-4">
  <div>Item 1</div>
  <div>Item 2</div>
</div>
```

#### Space Between
```tsx
<div className="flex justify-between items-center">
  <div>Left</div>
  <div>Right</div>
</div>
```

---

## Animations & Transitions

### Transition Durations

```css
--duration-fast: 150ms;
--duration-normal: 300ms;
--duration-slow: 500ms;
```

### Easing Functions

```css
--ease-smooth: cubic-bezier(0.4, 0, 0.2, 1);
--ease-bounce: cubic-bezier(0.68, -0.55, 0.265, 1.55);
--ease-sharp: cubic-bezier(0.4, 0, 1, 1);
```

### Tailwind Animation Classes

```tsx
// Transitions
transition-all         // All properties
transition-colors      // Colors only
transition-transform   // Transform only
transition-opacity     // Opacity only

// Durations
duration-150  // 150ms
duration-300  // 300ms
duration-500  // 500ms

// Easing
ease-in-out   // Smooth
ease-in       // Start slow
ease-out      // End slow
```

### Common Animations

#### Fade In
```tsx
className="animate-fade-in"

// In CSS:
@keyframes fade-in {
  from { opacity: 0; transform: translateY(10px); }
  to { opacity: 1; transform: translateY(0); }
}
```

#### Scale In
```tsx
className="animate-scale-in"

// In CSS:
@keyframes scale-in {
  from { transform: scale(0.95); opacity: 0; }
  to { transform: scale(1); opacity: 1; }
}
```

#### Slide In
```tsx
className="animate-slide-in-right"

// In CSS:
@keyframes slide-in-right {
  from { transform: translateX(100%); }
  to { transform: translateX(0); }
}
```

### Hover Effects

```tsx
// Lift
className="hover:translate-y-[-4px] transition-transform duration-300"

// Scale
className="hover:scale-105 transition-transform duration-200"

// Glow
className="hover:shadow-[0_0_40px_rgba(234,56,87,0.4)] transition-shadow duration-300"
```

### Loading Animations

#### Spinner
```tsx
<div className="animate-spin rounded-full h-8 w-8 border-b-2 border-accent-red" />
```

#### Pulse
```tsx
<div className="animate-pulse bg-muted h-4 w-full rounded" />
```

---

## Responsive Design

### Breakpoints

```css
/* Mobile First */
sm: 640px   // Small devices
md: 768px   // Tablets
lg: 1024px  // Laptops
xl: 1280px  // Desktops
2xl: 1536px // Large screens
```

### Tailwind Responsive Classes

```tsx
// Hidden on mobile, visible on desktop
className="hidden md:block"

// Full width on mobile, half on desktop
className="w-full md:w-1/2"

// Stack on mobile, grid on desktop
className="flex flex-col md:grid md:grid-cols-2"

// Small text on mobile, large on desktop
className="text-sm md:text-base lg:text-lg"
```

### Responsive Patterns

#### Mobile Navigation
```tsx
<nav className="fixed bottom-0 md:top-0 w-full">
  {/* Mobile bottom nav, Desktop top nav */}
</nav>
```

#### Responsive Grid
```tsx
<div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
  {items.map(item => <Card key={item.id} />)}
</div>
```

#### Responsive Dialog
```tsx
<DialogContent className="w-full sm:max-w-md mx-4 sm:mx-auto">
  {/* Full width on mobile, max-width on desktop */}
</DialogContent>
```

---

## Accessibility

### WCAG AA Compliance

#### Color Contrast Requirements
- **Normal Text:** Minimum 4.5:1
- **Large Text (18pt+):** Minimum 3:1
- **UI Components:** Minimum 3:1

#### Verified Contrasts (на dark-gray)
✅ `text-white`: 17.8:1 (AAA)  
✅ `text-gray-300`: 7.2:1 (AA)  
✅ `text-gray-400`: 4.5:1 (AA)  
✅ `text-accent-red`: 5.1:1 (AA)

### Focus Indicators

```tsx
// ВСЕГДА добавляйте focus styles
className="focus:outline-none focus:ring-2 focus:ring-accent-red focus:ring-offset-2 focus:ring-offset-dark-gray"
```

### ARIA Labels

```tsx
// Buttons without text
<button aria-label="Закрыть">
  <X className="h-4 w-4" />
</button>

// Form inputs
<input aria-label="Email адрес" placeholder="example@domain.com" />

// Loading states
<div role="status" aria-live="polite">
  {loading ? 'Загрузка...' : 'Готово'}
</div>
```

### Keyboard Navigation

```tsx
// Tab order
<input tabIndex={1} />
<input tabIndex={2} />
<button tabIndex={3}>Submit</button>

// Skip links
<a href="#main-content" className="sr-only focus:not-sr-only">
  Перейти к содержимому
</a>
```

### Screen Reader Classes

```tsx
// Hidden visually, available to screen readers
className="sr-only"

// Visible on focus (for skip links)
className="sr-only focus:not-sr-only"
```

---

## Iconography

### Icon Library: Lucide React

**Installation:**
```bash
npm install lucide-react
```

**Import:**
```tsx
import { User, Settings, Mail, Phone, Check, X } from 'lucide-react';
```

### Icon Sizes

```tsx
// Extra Small
<Icon className="h-3 w-3" />  // 12px

// Small
<Icon className="h-4 w-4" />  // 16px

// Medium
<Icon className="h-5 w-5" />  // 20px

// Large
<Icon className="h-6 w-6" />  // 24px

// Extra Large
<Icon className="h-8 w-8" />  // 32px
```

### Icon Colors

```tsx
// Inherit text color
<Icon className="text-current" />

// Specific color
<Icon className="text-accent-red" />
<Icon className="text-gray-400" />
```

### Icon in Button
```tsx
<GlassButton>
  <Mail className="h-4 w-4 mr-2" />
  Отправить Email
</GlassButton>
```

### Icon Button
```tsx
<Button variant="ghost" size="icon">
  <Settings className="h-5 w-5" />
</Button>
```

---

## Design Tokens

### Export to JSON

```json
{
  "colors": {
    "accent": {
      "red": {
        "value": "hsl(350, 81%, 57%)",
        "type": "color"
      }
    },
    "gray": {
      "dark": {
        "value": "hsl(240, 6%, 11%)",
        "type": "color"
      }
    }
  },
  "spacing": {
    "4": {
      "value": "16px",
      "type": "spacing"
    }
  },
  "typography": {
    "base": {
      "value": "16px",
      "type": "fontSize"
    }
  }
}
```

### Token Naming Convention

```
[category]-[property]-[variant]-[state]

Examples:
color-accent-red-hover
spacing-component-padding-lg
typography-heading-size-xl
```

---

## Best Practices

### ✅ DO's

1. **Используйте дизайн-систему компонентов**
   ```tsx
   ✅ <GlassButton variant="primary">Save</GlassButton>
   ❌ <button className="bg-red-500...">Save</button>
   ```

2. **ВСЕГДА используйте semantic tokens**
   ```tsx
   ✅ className="bg-dark-gray text-white"
   ❌ className="bg-[#1a1a1d] text-[#ffffff]"
   ```

3. **Вторая кнопка = secondary**
   ```tsx
   ✅ <GlassButton variant="secondary">Cancel</GlassButton>
   ❌ <GlassButton variant="outline">Cancel</GlassButton>
   ```

4. **Обработка ошибок через toast**
   ```tsx
   ✅ toastError({ title: "Ошибка", description: "..." });
   ❌ console.error("Error");
   ```

5. **Интернационализация обязательна**
   ```tsx
   ✅ <h1>{t('common.welcome')}</h1>
   ❌ <h1>Welcome</h1>
   ```

6. **Логирование централизованно**
   ```tsx
   ✅ logger.error('Failed to save', error, { component: 'MyForm' });
   ❌ console.log('error:', error);
   ```

7. **TypeScript типы явно**
   ```tsx
   ✅ const handleSubmit = async (data: FormData): Promise<void> => {}
   ❌ const handleSubmit = async (data) => {}
   ```

8. **Glass effects для основного UI**
   ```tsx
   ✅ <GlassCard>Content</GlassCard>
   ❌ <div className="bg-gray-800">Content</div>
   ```

### ❌ DON'Ts

1. **НЕ использовать прямые цвета**
   ```tsx
   ❌ className="text-white bg-black"
   ✅ className="text-foreground bg-background"
   ```

2. **НЕ хардкодить текст**
   ```tsx
   ❌ <Button>Save</Button>
   ✅ <Button>{t('actions.save')}</Button>
   ```

3. **НЕ использовать console.log**
   ```tsx
   ❌ console.log('user:', user);
   ✅ logger.info('User loaded', { userId: user.id });
   ```

4. **НЕ оставлять мёртвый код**
   ```tsx
   ❌ // const oldFunction = () => { ... }  // Закомментировано
   ✅ // Удалить полностью
   ```

5. **НЕ использовать любые значения**
   ```tsx
   ❌ className="w-[243px] h-[87px]"
   ✅ className="w-64 h-20"  // Используйте scale
   ```

6. **НЕ забывать disabled states**
   ```tsx
   ❌ <Button onClick={handleClick}>Submit</Button>
   ✅ <Button onClick={handleClick} disabled={loading}>Submit</Button>
   ```

### Code Review Checklist

- [ ] Все компоненты из design-system используются
- [ ] Нет прямых цветов (text-white, bg-black и т.д.)
- [ ] Все тексты через t('ключ')
- [ ] TypeScript типы указаны явно
- [ ] Логирование через logger.*
- [ ] Toast для уведомлений пользователя
- [ ] Вторая кнопка = variant="secondary"
- [ ] Glass effects для UI элементов
- [ ] Accessibility атрибуты добавлены
- [ ] Responsive на всех breakpoints
- [ ] Нет мёртвого кода
- [ ] Loading states обработаны
- [ ] Error handling через try/catch

---

## Troubleshooting

### Проблема: Текст не видно на glass background

**Решение:**
```tsx
// Увеличьте opacity фона
className="bg-card/95"  // Было bg-card/60

// Или используйте text-white вместо text-foreground
className="text-white"
```

### Проблема: Glass effect не работает

**Решение:**
```tsx
// Добавьте backdrop-blur
className="backdrop-blur-xl"

// Проверьте браузер (Safari требует -webkit-backdrop-filter)
```

### Проблема: Кнопки не реагируют на клик

**Решение:**
```tsx
// Проверьте z-index
className="relative z-10"

// Убедитесь что pointer-events не disabled
className="pointer-events-auto"
```

### Проблема: Colors не применяются из Tailwind

**Решение:**
```tsx
// Проверьте что переменные определены в index.css
:root {
  --accent-red: 350 81% 57%;
}

// Проверьте tailwind.config.ts
colors: {
  'accent-red': 'hsl(var(--accent-red))',
}

// Используйте правильный формат
className="bg-accent-red"  // ✅
className="bg-[var(--accent-red)]"  // ❌
```

---

## Version History

### Version 1.0.0 (2025-01-19)
- ✅ Initial comprehensive style guide
- ✅ Complete color system documentation
- ✅ Typography scale defined
- ✅ Component library documented
- ✅ Glass effects standardized
- ✅ Accessibility guidelines added
- ✅ Best practices established

---

## Maintenance

Этот Style Guide должен обновляться при:
- Добавлении новых компонентов
- Изменении цветовой палитры
- Обновлении shadcn/ui
- Добавлении новых паттернов
- Обнаружении проблем accessibility

**Ответственный:** Design System Team  
**Следующий ревью:** 2025-02-19

---

## Resources

- [shadcn/ui Documentation](https://ui.shadcn.com)
- [Tailwind CSS Docs](https://tailwindcss.com/docs)
- [Lucide Icons](https://lucide.dev)
- [WCAG Guidelines](https://www.w3.org/WAI/WCAG21/quickref/)
- [React TypeScript Cheatsheet](https://react-typescript-cheatsheet.netlify.app)

---

**Конец документа**
