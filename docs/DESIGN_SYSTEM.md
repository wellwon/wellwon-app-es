# WellWon Design System

**Version:** 5.0
**Based on:** Declarant page implementation (`/platform-pro/declarant`)
**Last Updated:** 2025-11-30

---

## Table of Contents

1. [Color Palette](#1-color-palette)
2. [Typography System](#2-typography-system)
3. [Spacing System](#3-spacing-system)
4. [Border Radius](#4-border-radius)
5. [Layout Dimensions](#5-layout-dimensions)
6. [Shadows](#6-shadows)
7. [Hybrid Theme Architecture](#7-hybrid-theme-architecture)
8. [Animation Policy](#8-animation-policy)
9. [Button System](#9-button-system)
10. [Form Input Fields](#10-form-input-fields)
11. [Select Components](#11-select-components)
12. [Filter Section](#12-filter-section)
13. [Modal Forms](#13-modal-forms)
14. [Data Tables](#14-data-tables)
15. [Document Tables](#15-document-tables)
16. [Pagination](#16-pagination)
17. [Status Colors & Badges](#17-status-colors--badges)
18. [Sidebar Navigation](#18-sidebar-navigation)
19. [Dropdown Menus](#19-dropdown-menus)
20. [Drag-Drop Upload Zone](#20-drag-drop-upload-zone)
21. [UI State Persistence](#21-ui-state-persistence)
22. [Accessibility](#22-accessibility)
23. [Routing Structure](#23-routing-structure)

---

## 1. Color Palette

### 1.1 Background Colors (Three-Level Hierarchy)

| Level | Element | Dark Mode | Light Mode | Tailwind |
|-------|---------|-----------|------------|----------|
| **1** | Page background | `#1a1a1e` | `#f4f4f4` | `bg-[#1a1a1e]` / `bg-[#f4f4f4]` |
| **2** | Cards, panels | `#232328` | `#ffffff` | `bg-[#232328]` / `bg-white` |
| **3** | Input fields | `#1e1e22` | `#f9fafb` | `bg-[#1e1e22]` / `bg-gray-50` |

### 1.2 Text Colors

| Token | Dark Mode | Light Mode | Tailwind |
|-------|-----------|------------|----------|
| **Primary** | `#ffffff` | `#111827` | `text-white` / `text-gray-900` |
| **Secondary** | `#9ca3af` | `#6b7280` | `text-gray-400` / `text-gray-600` |
| **Muted** | `#6b7280` | `#9ca3af` | `text-gray-500` |

### 1.3 Border Colors

| Theme | Value | Tailwind |
|-------|-------|----------|
| **Dark** | `rgba(255,255,255,0.1)` | `border-white/10` |
| **Dark hover** | `rgba(255,255,255,0.2)` | `border-white/20` |
| **Light** | `#d1d5db` | `border-gray-300` |
| **Light hover** | `#9ca3af` | `border-gray-400` |

### 1.4 Accent Colors (Theme-Independent)

| Name | HEX | Tailwind | Usage |
|------|-----|----------|-------|
| **Red** | `#ea3857` | `bg-accent-red` / `text-accent-red` | Primary CTA, errors, delete |
| **Green** | `#13b981` | `text-green-500` | Success, validation |
| **Yellow** | `#f59e0b` | `text-yellow-500` | Warnings, processing |
| **Purple** | `#a855f7` | `text-purple-500` | Info, documents |

### 1.5 Opacity Patterns (Dark Theme)

| Opacity | Usage | Example |
|---------|-------|---------|
| `white/[0.02]` | Subtle hover on drag-drop | `hover:bg-white/[0.02]` |
| `white/[0.03]` | Table row hover | `hover:bg-white/[0.03]` |
| `white/5` | Button backgrounds, light hover | `bg-white/5` |
| `white/10` | Borders, hover backgrounds | `border-white/10`, `hover:bg-white/10` |
| `white/20` | Hover borders, drag-drop active | `hover:border-white/20` |
| `white/40` | Active drag-drop border | `border-white/40` |
| `accent-red/10` | Danger button backgrounds | `bg-accent-red/10` |
| `accent-red/20` | Danger button hover | `hover:bg-accent-red/20` |

### 1.6 Table Row Hover Colors

| Theme | Color | Tailwind |
|-------|-------|----------|
| **Dark** | `rgba(255,255,255,0.03)` | `hover:bg-white/[0.03]` |
| **Light** | `#f4f4f6` | `hover:bg-[#f4f4f6]` |

**Important:** Use exact HEX value `#f4f4f6` for light theme table hover, not `hover:bg-gray-50`.

### 1.7 Semi-Transparent Filter Colors

Active filter chips use semi-transparent backgrounds matching their status:

| Color | Background | Text | Border |
|-------|------------|------|--------|
| **Orange** | `bg-orange-500/20` | `text-orange-500` | `border-orange-500/30` |
| **Red** | `bg-accent-red/10` | `text-accent-red` | `border-accent-red/20` |
| **Green** | `bg-green-500/10` | `text-green-500` | `border-green-500/30` |

---

## 2. Typography System

### 2.1 Font Families

| Token | Font Stack | Usage |
|-------|------------|-------|
| **Sans** | `Inter, system-ui, sans-serif` | All UI text |
| **Mono** | `"JetBrains Mono", monospace` | IDs, codes, numbers |

### 2.2 Type Scale

| Token | Size | Tailwind | Usage |
|-------|------|----------|-------|
| **xs** | 12px | `text-xs` | Badges, small labels |
| **sm** | 14px | `text-sm` | **Buttons, body text, inputs** |
| **base** | 16px | `text-base` | Default body |
| **lg** | 18px | `text-lg` | Subheadings |
| **xl** | 20px | `text-xl` | Card titles |
| **2xl** | 24px | `text-2xl` | Stats values |
| **3xl** | 30px | `text-3xl` | Page titles |

### 2.3 Font Weights

| Token | Value | Tailwind | Usage |
|-------|-------|----------|-------|
| **Normal** | 400 | `font-normal` | Body text |
| **Medium** | 500 | `font-medium` | **Buttons, labels, UI elements** |
| **Semibold** | 600 | `font-semibold` | Headings |
| **Bold** | 700 | `font-bold` | Stats, emphasis |

### 2.4 Button Typography Standard

**All buttons with text must use:**
```tsx
className="text-sm font-medium"
// text-sm = 14px
// font-medium = 500
```

---

## 3. Spacing System

Based on **4px base unit**.

| Token | px | Tailwind | Usage |
|-------|-----|----------|-------|
| **xs** | 4px | `p-1` / `gap-1` | Tight spacing |
| **sm** | 8px | `p-2` / `gap-2` | Icon spacing, button gaps |
| **md** | 12px | `p-3` / `gap-3` | Element gaps |
| **base** | 16px | `p-4` / `gap-4` | Section gaps |
| **lg** | 24px | `p-6` / `gap-6` | **Card padding** |
| **xl** | 32px | `p-8` / `gap-8` | Page margins |

---

## 4. Border Radius

| Token | px | Tailwind | Usage |
|-------|-----|----------|-------|
| **sm** | 2px | `rounded-sm` | — |
| **md** | 6px | `rounded-md` | Small elements |
| **lg** | 8px | `rounded-lg` | **Small buttons (h-8)**, icon buttons |
| **xl** | 12px | `rounded-xl` | **Medium buttons (h-10)**, inputs |
| **2xl** | 16px | `rounded-2xl` | **Cards, panels** |
| **3xl** | 24px | `rounded-3xl` | Large modals |
| **full** | 9999px | `rounded-full` | Pills, badges |

---

## 5. Layout Dimensions

### 5.1 Sidebar

| State | Width | Tailwind |
|-------|-------|----------|
| **Expanded** | 264px | `w-[264px]` |
| **Collapsed** | 80px | `w-20` |

### 5.2 Common Dimensions

| Element | Size | Tailwind |
|---------|------|----------|
| Header height | 64px | `h-16` |
| Content padding | 32px | `p-8` |
| Card padding | 24px | `p-6` |

---

## 6. Shadows

| Theme | Shadow | Usage |
|-------|--------|-------|
| **Light** | `shadow-sm` | Cards, buttons |
| **Dark** | None | Glassmorphism aesthetic |

**Pattern:**
```tsx
className={`... ${!isDark ? 'shadow-sm' : ''}`}
```

---

## 7. Hybrid Theme Architecture

### 7.1 Theme Zones

| Zone | Behavior | Background |
|------|----------|------------|
| **Sidebar** | **Always dark** | `#232328` |
| **Content** | Toggles | `#f4f4f4` / `#1a1a1e` |
| **Header** | Follows content | `#ffffff` / `#232328` |

### 7.2 Theme Object Pattern

```tsx
const theme = isDark ? {
  page: 'bg-[#1a1a1e]',
  card: { background: 'bg-[#232328]', border: 'border-white/10' },
  text: { primary: 'text-white', secondary: 'text-gray-400' },
  button: { default: 'text-gray-300 hover:text-white hover:bg-white/10' },
  table: { row: 'hover:bg-white/5', border: 'border-white/10' }
} : {
  page: 'bg-[#f4f4f4]',
  card: { background: 'bg-white', border: 'border-gray-300 shadow-sm' },
  text: { primary: 'text-gray-900', secondary: 'text-gray-600' },
  button: { default: 'text-gray-600 hover:text-gray-900 hover:bg-gray-100' },
  table: { row: 'hover:bg-gray-50', border: 'border-gray-300' }
};
```

---

## 8. Animation Policy

### 8.1 No Animation (Instant)

| Element | Rule |
|---------|------|
| Theme toggle | `transition-none` |
| Sidebar collapse | `transition-none` |
| Input focus | `transition-none` |
| **Table row borders** | No `transition-colors` |

**Important:** Remove `transition-colors` from table rows to prevent border flash on theme switch. Use inline conditional classes instead of theme object for borders:

```tsx
// WRONG - causes flash on theme switch
<tr className={`border-b ${theme.table.border} transition-colors`}>

// CORRECT - no transition, no flash
<tr className={`border-b ${isDark ? 'border-white/10' : 'border-gray-200'}`}>
```

### 8.2 Allowed Animations

| Element | Duration | Class |
|---------|----------|-------|
| Button hover | 150ms | `transition-all` |
| Dropdown chevron | 150ms | `transition-transform` |
| Icon button scale | 150ms | `hover:scale-105 transition-all` |
| Drag-drop zone | 150ms | `transition-colors` |

---

## 9. Button System

### 9.1 Button Sizes

| Size | Height | Padding | Radius | Usage |
|------|--------|---------|--------|-------|
| **Large** | h-12 (48px) | px-6 | rounded-xl | Modal forms |
| **Medium** | h-10 (40px) | px-4 | rounded-xl | Action panels |
| **Small** | h-8 (32px) | px-3 | rounded-lg | Tables |
| **Icon** | w-8 h-8 / w-10 h-10 | — | rounded-lg / rounded-xl | Icon only |

### 9.2 Primary Button (CTA)

```tsx
<button className={`px-4 h-10 rounded-xl flex items-center gap-2 text-sm font-medium
  bg-accent-red text-white hover:bg-accent-red/90 ${!isDark ? 'shadow-sm' : ''}`}>
  <Plus className="w-4 h-4" />
  Создать
</button>
```

### 9.3 Secondary Button (Text only)

```tsx
<button className={`px-4 h-10 rounded-xl flex items-center gap-2 text-sm font-medium ${
  isDark
    ? 'text-gray-300 hover:text-white hover:bg-white/10'
    : 'text-gray-600 hover:text-gray-900 hover:bg-gray-100'
}`}>
  <Download className="w-4 h-4" />
  Экспорт
</button>
```

### 9.4 Ghost Button (With border)

```tsx
<button className={`px-4 h-10 rounded-xl flex items-center gap-2 text-sm font-medium border ${
  isDark
    ? 'bg-[#1e1e22] border-white/10 text-gray-300 hover:bg-[#252529] hover:text-white'
    : 'bg-gray-50 border-gray-300 text-gray-600 hover:bg-gray-100 hover:text-gray-900'
}`}>
  <SlidersHorizontal className="w-4 h-4" />
  Фильтры
</button>
```

### 9.5 Danger Button

```tsx
<button className="h-8 px-3 rounded-lg flex items-center justify-center
  bg-accent-red/10 text-accent-red border border-accent-red/20
  hover:bg-accent-red/20 hover:border-accent-red/30">
  <Trash2 className="h-4 w-4" />
</button>
```

### 9.6 Icon Button (Sidebar/Toolbar)

```tsx
// Size: h-8 w-8 with hover:scale-105
<button className={`h-8 w-8 rounded-lg flex items-center justify-center border transition-all ${
  isDark
    ? 'bg-white/5 border-white/10 text-gray-400 hover:bg-white/10 hover:border-white/20 hover:text-white hover:scale-105'
    : 'bg-white border-gray-300 text-gray-600 hover:bg-gray-50 hover:border-gray-400 hover:text-gray-900 hover:scale-105'
}`}>
  <ChevronLeft className="w-4 h-4" />
</button>
```

### 9.7 Table Action Button (Glass)

```tsx
<button className={`h-8 px-3 rounded-lg flex items-center justify-center border ${
  isDark
    ? 'bg-white/5 text-gray-300 border-white/10 hover:bg-white/10 hover:text-white hover:border-white/20'
    : 'bg-gray-100 text-gray-600 border-gray-200 hover:bg-gray-200 hover:text-gray-900'
}`}>
  <Copy className="h-4 w-4" />
</button>
```

### 9.8 Cancel Button (Modal)

```tsx
<button className={`h-12 px-6 rounded-xl flex items-center gap-2 border text-sm font-medium ${
  isDark
    ? 'bg-[#232328] text-gray-300 border-white/10 hover:bg-[#2a2a30]'
    : 'bg-white text-gray-700 border-gray-300 hover:bg-gray-50'
}`}>
  <X className="h-4 w-4" />
  Отмена
</button>
```

---

## 10. Form Input Fields

### 10.1 Standard Input

| Property | Value |
|----------|-------|
| Height | `h-10` (40px) |
| Radius | `rounded-xl` |
| Padding | `px-3 py-2` |
| Font | `text-sm` |
| Focus | `focus:outline-none focus:ring-0 transition-none` |

```tsx
<input className={`h-10 w-full rounded-xl border px-3 py-2 text-sm
  focus:outline-none focus:ring-0 transition-none ${
  isDark
    ? 'bg-[#1e1e22] border-white/10 text-white placeholder:text-gray-500 hover:border-white/20'
    : 'bg-gray-50 border-gray-300 text-gray-900 placeholder:text-gray-400 hover:border-gray-400'
}`} />
```

### 10.2 Label

```tsx
<label className={`text-sm ${isDark ? 'text-white' : 'text-gray-700'}`}>
  Label *
</label>
```

**Spacing:** `space-y-1.5` between label and input

### 10.3 Validation States

| State | Border |
|-------|--------|
| Default | `border-white/10` / `border-gray-300` |
| Error | `border-red-500/50` |
| Success | `border-green-500/50` |

### 10.4 Search Input with Icon

```tsx
<div className="relative flex-1">
  <Search className={`absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 ${
    isDark ? 'text-gray-400' : 'text-gray-500'
  }`} />
  <input className={`pl-10 h-10 w-full rounded-xl border text-sm
    focus:outline-none focus:ring-0 transition-none ${
    isDark
      ? 'bg-[#1e1e22] border-white/10 text-white placeholder:text-gray-500'
      : 'bg-gray-50 border-gray-300 text-gray-900 placeholder:text-gray-400'
  }`} placeholder="Поиск..." />
</div>
```

### 10.5 Action Button with Validation

Кнопка меняет состояние в зависимости от валидности данных (например, поиск по ИНН).

```tsx
const isValid = /^\d{10,12}$/.test(value);

<button
  disabled={!isValid}
  className={`h-10 w-10 shrink-0 rounded-xl border flex items-center justify-center transition-none ${
    isValid
      ? 'bg-green-500/10 border-green-500 hover:bg-green-500/20'
      : isDark
        ? 'bg-[#1e1e22] border-white/10 opacity-50 cursor-not-allowed'
        : 'bg-white border-gray-300 opacity-50 cursor-not-allowed'
  }`}
>
  <Search className={`h-4 w-4 ${isValid ? 'text-green-500' : 'text-gray-400'}`} />
</button>
```

---

## 11. Select Components

### 11.1 Standard Select (Form)

```tsx
<SelectTrigger className={`w-full h-10 rounded-xl focus:outline-none focus:ring-0 transition-none ${
  isDark
    ? 'bg-[#1e1e22] border-white/10 text-white'
    : 'bg-gray-50 border-gray-300 text-gray-900'
}`}>
  <SelectValue />
</SelectTrigger>

<SelectContent className={isDark ? 'bg-[#232328] border-white/10' : 'bg-white border-gray-200'}>
  <SelectItem className={isDark ? 'focus:bg-white/10 text-white' : 'focus:bg-gray-100 text-gray-900'}>
    Option
  </SelectItem>
</SelectContent>
```

### 11.2 SelectItem (Without Check Indicator)

SelectItem should NOT have a check indicator or left padding shift on selection. Use equal horizontal padding:

```tsx
// In components/ui/select.tsx
const SelectItem = React.forwardRef<...>(({ className, children, ...props }, ref) => (
  <SelectPrimitive.Item
    ref={ref}
    className={cn(
      "relative flex w-full cursor-default select-none items-center rounded-sm py-1.5 px-2 text-sm outline-none focus:bg-accent focus:text-accent-foreground data-[disabled]:pointer-events-none data-[disabled]:opacity-50",
      className
    )}
    {...props}
  >
    <SelectPrimitive.ItemText>{children}</SelectPrimitive.ItemText>
  </SelectPrimitive.Item>
))
```

**Key points:**
- Use `px-2` for equal left/right padding
- Remove `ItemIndicator` component entirely
- No `pl-8` that causes text shift on selection

### 11.3 Rows Per Page Select (Pagination)

Без бордера, как кнопки пагинации:

```tsx
<SelectTrigger className={`w-[70px] h-8 border-0 focus:outline-none focus:ring-0 transition-none ${
  isDark
    ? 'bg-white/5 text-white hover:bg-white/10'
    : 'bg-gray-100 text-gray-900 hover:bg-gray-200'
}`}>
  <SelectValue />
</SelectTrigger>
```

---

## 12. Filter Section

### 12.1 Structure

```
┌──────────────────────────────────────────────────────────┐
│ [🔍 Поиск...              ] [⚙ Фильтры ▼][✕]            │
│                                                          │
│ ┌───────────┐ ┌───────────┐ ┌───────────┐               │
│ │ Статус ▼  │ │ Дата ▼    │ │ Тип ▼     │               │
│ └───────────┘ └───────────┘ └───────────┘               │
└──────────────────────────────────────────────────────────┘
```

### 12.2 Height Consistency

Все элементы в строке фильтров: **h-10** (40px)

| Element | Classes |
|---------|---------|
| Search input | `h-10 rounded-xl` |
| Filter button | `h-10 rounded-xl` |
| Reset button | `h-10 px-3 rounded-xl` |

### 12.3 Filter Button with X Reset

Кнопка X появляется рядом с кнопкой фильтров когда есть активные фильтры. **Важно:** X уменьшает padding кнопки Фильтры, а не сдвигает другие элементы.

```tsx
<div className="flex items-center gap-1">
  <button
    className={`flex items-center gap-2 h-10 rounded-xl border text-sm font-medium
      ${hasActiveFilters ? 'pl-4 pr-2' : 'px-4'}
      ${isDark
        ? 'bg-[#1e1e22] border-white/10 text-gray-300 hover:bg-[#252529] hover:text-white'
        : 'bg-gray-50 border-gray-300 text-gray-600 hover:bg-gray-100 hover:text-gray-900'
      }`}
  >
    <SlidersHorizontal size={16} />
    <span>Фильтры</span>
    <ChevronDown size={16} />
  </button>

  {hasActiveFilters && (
    <button
      onClick={() => clearFilters()}
      className="h-10 px-3 rounded-xl flex items-center justify-center
        bg-accent-red/10 text-accent-red border border-accent-red/20
        hover:bg-accent-red/20 hover:border-accent-red/30"
    >
      <X size={16} />
    </button>
  )}
</div>
```

**Key points:**
- Wrap both buttons in `flex items-center gap-1` container
- Filters button changes from `px-4` to `pl-4 pr-2` when X appears
- X button is same height `h-10` but narrower `px-3`

### 12.4 Quick Filter Chips

Быстрые фильтры должны совпадать по высоте с кнопкой Filters:

```tsx
<button className={`h-10 px-3 rounded-xl border text-sm font-medium flex items-center gap-2 ${
  isActive
    ? 'bg-orange-500/20 text-orange-500 border-orange-500/30'
    : isDark
      ? 'bg-[#1e1e22] border-white/10 text-gray-300 hover:bg-[#252529]'
      : 'bg-gray-50 border-gray-300 text-gray-600 hover:bg-gray-100'
}`}>
  {label}
</button>
```

**Important:** Active state uses semi-transparent colors (e.g., `bg-orange-500/20`), not solid colors.

---

## 13. Modal Forms

### 13.1 Color Hierarchy

| Level | Element | Dark | Light |
|-------|---------|------|-------|
| 1 | Modal background | `#1a1a1e` | `#f4f4f4` |
| 2 | Card sections | `#232328` | `#ffffff` |
| 3 | Input fields | `#1e1e22` | `#f9fafb` |

### 13.2 Theme Object

```tsx
const theme = isLightTheme ? {
  modal: { bg: 'bg-[#f4f4f4]', border: 'border-gray-300' },
  card: { bg: 'bg-white', border: 'border-gray-300', shadow: 'shadow-sm' },
  text: { primary: 'text-gray-900', secondary: 'text-gray-600' },
  closeButton: 'hover:bg-gray-100 text-gray-500'
} : {
  modal: { bg: 'bg-[#1a1a1e]', border: 'border-white/10' },
  card: { bg: 'bg-[#232328]', border: 'border-white/10', shadow: '' },
  text: { primary: 'text-white', secondary: 'text-gray-400' },
  closeButton: 'hover:bg-white/10 text-gray-400'
};
```

### 13.3 Form Actions

**Container:** `flex justify-center gap-3`

**Buttons:** h-12 px-6 rounded-xl (Large size)

---

## 14. Data Tables

### 14.1 Table Styles

```tsx
// Header
<th className={`px-4 py-3 text-left text-xs font-medium uppercase tracking-wider ${
  isDark ? 'text-gray-400 border-white/10' : 'text-gray-500 border-gray-300'
}`}>

// Row - note hover color
<tr className={`${isDark ? 'hover:bg-white/[0.03]' : 'hover:bg-[#f4f4f6]'}`}>

// Cell
<td className={`px-4 py-3 text-sm ${isDark ? 'text-white' : 'text-gray-900'}`}>
```

### 14.2 Row Actions

Use **h-8** buttons with **rounded-lg**:
- Glass button for neutral actions (copy, edit, view)
- Danger button for delete

---

## 15. Document Tables

Document tables (inside cards/panels like "Основные документы", "Документы по товарам") have special styling for full-width hover highlighting.

### 15.1 Full-Width Hover Structure

To achieve edge-to-edge hover highlighting within a card:

```tsx
{/* Wrapper with negative margins to extend to card edges */}
<div className="-mx-6 -mb-6">
  <table className="w-full table-fixed">
    <colgroup>
      <col className="w-14" />          {/* Checkbox column */}
      <col className="w-[45%]" />       {/* Document name */}
      <col />                           {/* Flexible column */}
      <col className="w-32" />          {/* Actions column */}
    </colgroup>
    <thead>
      <tr className={`border-b ${isDark ? 'border-white/10' : 'border-gray-200'}`}>
        <th className="py-2 pl-6 pr-2">...</th>
        <th className="py-2 pr-4">...</th>
        <th className="py-2 pr-4">...</th>
        <th className="py-2 pr-6">...</th>
      </tr>
    </thead>
    <tbody>
      {items.map((item, index) => (
        <tr
          key={item.id}
          className={`
            ${index < items.length - 1
              ? `border-b ${isDark ? 'border-white/10' : 'border-gray-200'}`
              : 'rounded-b-2xl'
            }
            ${isDark ? 'hover:bg-white/[0.03]' : 'hover:bg-[#f4f4f6]'}
          `}
        >
          <td className="py-2.5 pl-6 pr-2 align-top">...</td>
          <td className="py-2.5 pr-4 align-top">...</td>
          <td className="py-2.5 pr-4 align-top">...</td>
          <td className="py-2.5 pr-6 align-top">...</td>
        </tr>
      ))}
    </tbody>
  </table>
</div>
```

### 15.2 Key Points

| Rule | Implementation |
|------|----------------|
| **Full-width hover** | `-mx-6 -mb-6` wrapper extends table to card edges |
| **Fixed columns** | `table-fixed` + `<colgroup>` for precise column widths |
| **No top divider on header** | Don't use `border-t` on header row |
| **Last row styling** | No `border-b`, add `rounded-b-2xl` for rounded corners |
| **Cell alignment** | Use `align-top` on all cells |
| **Edge padding** | Left edge `pl-6`, right edge `pr-6` |
| **Inner padding** | Middle columns use `pr-4` |

### 15.3 Column Widths

| Column | Width | Usage |
|--------|-------|-------|
| Checkbox | `w-14` | Fixed width for checkbox |
| Primary content | `w-[45%]` | Document name, title |
| Flexible | (no width) | Status, date, auto-fills |
| Actions | `w-32` | Action buttons |

### 15.4 Border Colors (No Transition)

**Important:** Use inline conditional for borders, not theme object, to prevent flash on theme switch:

```tsx
// CORRECT
className={`border-b ${isDark ? 'border-white/10' : 'border-gray-200'}`}

// WRONG - causes flash
className={`border-b ${theme.table.border} transition-colors`}
```

---

## 16. Pagination

### 16.1 Structure

```
[10 ▼] строк на странице   Показано 1-10 из 25   [<] [1] [2] [>]
```

### 16.2 Navigation Buttons

| State | Classes |
|-------|---------|
| Active | `bg-white/5 hover:bg-white/10` (dark) / `bg-gray-100 hover:bg-gray-200` (light) |
| Disabled | `opacity-50 cursor-not-allowed` |
| Current page | `bg-accent-red text-white` |

**Size:** `w-8 h-8 rounded-lg`

---

## 17. Status Colors & Badges

### 17.1 Status Mapping

| Status | Color | HEX |
|--------|-------|-----|
| Success | Green | `#13b981` |
| Warning | Yellow | `#f59e0b` |
| Error | Red | `#ea3857` |
| Info | Purple | `#a855f7` |
| Inactive | Gray | `#9ca3af` |

### 17.2 Badge Style

```tsx
<span className="px-2.5 py-1 rounded-full text-xs font-medium bg-green-500/10 text-green-500">
  Завершено
</span>
```

---

## 18. Sidebar Navigation

### 18.1 Collapsed State (Icon only)

```tsx
<button className={`w-12 h-12 flex items-center justify-center rounded-xl border ${
  active
    ? 'bg-accent-red/20 border-accent-red/30 text-accent-red'
    : 'border-white/10 text-gray-400 hover:bg-white/10 hover:border-accent-red/50 hover:text-accent-red'
}`}>
  <Icon className="w-5 h-5" />
</button>
```

### 18.2 Expanded State

```tsx
<div className={`flex items-center px-3 py-2.5 rounded-xl cursor-pointer ${
  active
    ? 'bg-accent-red/10 border border-accent-red/30 text-accent-red shadow-sm'
    : `${theme.button.default}`
}`}>
  <Icon className="w-5 h-5 mr-3" />
  <span className="text-sm font-medium">Label</span>
</div>
```

---

## 19. Dropdown Menus

Dropdown menus (e.g., "Добавить" buttons with menu) should match Select styling.

### 19.1 Dropdown Content

```tsx
<DropdownMenuContent
  className={`min-w-[200px] rounded-xl border p-1 ${
    isDark
      ? 'bg-[#232328] border-white/10'
      : 'bg-white border-gray-200'
  }`}
>
  <DropdownMenuItem
    className={`rounded-lg px-3 py-2 text-sm cursor-pointer ${
      isDark
        ? 'text-white focus:bg-white/10'
        : 'text-gray-900 focus:bg-gray-100'
    }`}
  >
    Option
  </DropdownMenuItem>
</DropdownMenuContent>
```

### 19.2 Key Styling Points

| Element | Dark Theme | Light Theme |
|---------|------------|-------------|
| Background | `bg-[#232328]` | `bg-white` |
| Border | `border-white/10` | `border-gray-200` |
| Item focus | `focus:bg-white/10` | `focus:bg-gray-100` |
| Text | `text-white` | `text-gray-900` |

**Important:** Use `focus:bg-*` instead of `hover:bg-*` for menu items (keyboard navigation support).

---

## 20. Drag-Drop Upload Zone

### 20.1 Basic Structure

```tsx
<label
  className={`
    flex-1 border-2 border-dashed rounded-xl flex flex-col items-center justify-center gap-3 p-6
    transition-colors cursor-pointer
    ${isDragOver
      ? isDark
        ? 'border-white/40 bg-white/[0.02]'
        : 'border-gray-400 bg-gray-50'
      : isDark
        ? 'border-white/20 hover:border-white/40 hover:bg-white/[0.02]'
        : 'border-gray-300 hover:border-gray-400 hover:bg-gray-50'
    }
  `}
  onDragOver={(e) => { e.preventDefault(); setIsDragOver(true); }}
  onDragLeave={() => setIsDragOver(false)}
  onDrop={(e) => { e.preventDefault(); setIsDragOver(false); handleFiles(e.dataTransfer.files); }}
>
  <input
    type="file"
    multiple
    className="hidden"
    onChange={(e) => handleFiles(e.target.files)}
  />
  <Upload className={`w-8 h-8 ${isDark ? 'text-gray-400' : 'text-gray-500'}`} />
  <div className="text-center">
    <p className={`text-sm ${isDark ? 'text-gray-300' : 'text-gray-700'}`}>
      Перетащите файлы сюда
    </p>
    <p className={`text-xs mt-1 ${isDark ? 'text-gray-500' : 'text-gray-400'}`}>
      или нажмите для выбора
    </p>
  </div>
</label>
```

### 20.2 Key Points

| Feature | Implementation |
|---------|----------------|
| **Clickable** | Use `<label>` wrapping hidden `<input type="file">` |
| **Dashed border** | `border-2 border-dashed` |
| **Hover state** | `hover:border-white/40 hover:bg-white/[0.02]` (dark) |
| **Drag state** | Track with `isDragOver` state, increase opacity |
| **Transition** | `transition-colors` allowed for smooth drag feedback |
| **Multi-file** | `multiple` attribute on input |

### 20.3 Panel Toggle (Upload/Journal)

For switchable panels, use toggle button at top of panel:

```tsx
<button
  onClick={() => setMode(mode === 'upload' ? 'journal' : 'upload')}
  className={`p-2 rounded-lg ${
    isDark
      ? 'text-gray-400 hover:text-white hover:bg-white/10'
      : 'text-gray-500 hover:text-gray-900 hover:bg-gray-100'
  }`}
>
  {mode === 'upload' ? <MessageSquare size={16} /> : <Upload size={16} />}
</button>
```

---

## 21. UI State Persistence

### 21.1 Storage Keys

| Key | Type | Default |
|-----|------|---------|
| `{module}_theme` | `'dark' \| 'light'` | `'light'` |
| `{module}_sidebarCollapsed` | `boolean` | `false` |
| `{module}_rowsPerPage` | `number` | `10` |

### 21.2 Pattern

```tsx
const [isDark, setIsDark] = useState(() => {
  return localStorage.getItem('module_theme') === 'dark';
});

const toggleTheme = () => {
  const newValue = !isDark;
  setIsDark(newValue);
  localStorage.setItem('module_theme', newValue ? 'dark' : 'light');
};
```

---

## 22. Accessibility

### 22.1 Focus States

**Important:** No colored ring on focus. Use neutral approach:

```tsx
className="focus:outline-none focus:ring-0"
```

### 22.2 Contrast Ratios

All text meets WCAG 2.1 AA (4.5:1 for normal, 3:1 for large text).

### 22.3 Keyboard Navigation

- Tab order follows visual hierarchy
- Escape closes modals/dropdowns
- Enter activates buttons

### 22.4 ARIA Labels

```tsx
<button aria-label="Toggle theme">
  <Moon className="w-4 h-4" />
</button>
```

---

## 23. Routing Structure

### 23.1 Declarant Module Routes

| Route | Page | Description |
|-------|------|-------------|
| `/platform-pro/declarant` | DeclarantContent | Main list page |
| `/platform-pro/declarant/package/:packageId` | CreateDeclarationPage | Package editing |
| `/platform-pro/declaration/:declarationId?` | CreateDeclarationPage | Declaration creation/editing |

### 23.2 Context Navigation

Use `usePlatformPro()` context for navigation within declarant module:

```tsx
const {
  declarantViewMode,     // 'list' | 'package' | 'declaration'
  packageId,             // string | null
  declarationId,         // string | null
  navigateToPackage,     // (pkgId: string) => void
  navigateToDeclaration, // (declId?: string) => void
  navigateToDeclarantList // () => void
} = usePlatformPro();
```

### 23.3 View Mode Detection

```tsx
const declarantViewMode: DeclarantViewMode = (() => {
  const path = location.pathname;
  if (path.includes('/platform-pro/declaration')) {
    return 'declaration';
  }
  if (path.includes('/platform-pro/declarant/package/')) {
    return 'package';
  }
  return 'list';
})();
```

---

## Quick Reference

### Button Sizes

| Size | Height | Padding | Radius | Usage |
|------|--------|---------|--------|-------|
| Large | h-12 | px-6 | rounded-xl | Modals |
| Medium | h-10 | px-4 | rounded-xl | Actions |
| Small | h-8 | px-3 | rounded-lg | Tables |
| Icon | h-8/h-10 | — | rounded-lg | Icon only |

### Common Patterns

```tsx
// All buttons with text
className="text-sm font-medium"

// No focus ring
className="focus:outline-none focus:ring-0"

// No transition on theme switch
className="transition-none"

// Icon button hover
className="hover:scale-105 transition-all"

// Flex centering
className="flex items-center justify-center"
className="flex items-center gap-2"
```

### Color Reference

| Element | Dark | Light |
|---------|------|-------|
| Page bg | `#1a1a1e` | `#f4f4f4` |
| Card bg | `#232328` | `#ffffff` |
| Input bg | `#1e1e22` | `gray-50` |
| Border | `white/10` | `gray-300` |
| Primary text | `white` | `gray-900` |
| Secondary text | `gray-400` | `gray-600` |
| Accent | `#ea3857` | `#ea3857` |
| **Table row hover** | `white/[0.03]` | `#f4f4f6` |

---

## Version History

| Version | Date | Changes |
|---------|------|---------|
| **5.0** | 2025-11-30 | Document tables, full-width hover, filter buttons, drag-drop upload, dropdown menus, routing structure, SelectItem without check indicator |
| **4.0** | 2025-11-28 | Complete rewrite: consolidated duplicates, removed outdated info, aligned with declarant implementation |
| **3.4** | 2025-11-28 | Button System consolidation |
| **3.3** | 2025-11-28 | Added Form Inputs, Modal Forms, Validation Buttons |
| **3.0** | 2025-11-25 | Initial v3 with HEX colors |

---

**End of Design System Documentation**
