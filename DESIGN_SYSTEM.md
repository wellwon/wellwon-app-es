# WellWon Design System

**Version:** 3.0  
**Based on:** `/test-app` implementation  
**Last Updated:** 2025-11-25

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
9. [Status Color Mapping](#9-status-color-mapping)
10. [Component Patterns](#10-component-patterns)
11. [Accessibility Guidelines](#11-accessibility-guidelines)

---

## 1. Color Palette

All colors are defined in HEX format for precision and universality.

### 1.1 Theme Colors (Light/Dark Toggle)

| Token | Light Mode | Dark Mode | Usage |
|-------|------------|-----------|-------|
| **Page Background** | `#f4f4f4` | `#1a1a1d` | Main application background |
| **Card Background** | `#ffffff` | `#232328` | Cards, panels, containers |
| **Header Background** | `#ffffff` | `#232328` | Top header bar |

### 1.2 Sidebar Colors (Always Dark)

The sidebar **always uses dark theme** regardless of content area theme.

| Token | HEX Value | Usage |
|-------|-----------|-------|
| **Background** | `#232328` | Sidebar main background |
| **Hover Background** | `#2a2a30` | Interactive element hover state |
| **Border** | `rgba(255, 255, 255, 0.1)` | Dividers, borders (translucent white) |

### 1.3 Text Colors

| Token | Light Mode | Dark Mode | Usage |
|-------|------------|-----------|-------|
| **Primary Text** | `#111827` | `#ffffff` | Headings, main content |
| **Secondary Text** | `#6b7280` | `#9ca3af` | Descriptions, labels, metadata |
| **Muted Text** | `#9ca3af` | `#6b7280` | Disabled, inactive text |

### 1.4 Accent Colors (Theme-Independent)

These colors remain consistent across light and dark themes.

| Name | HEX Value | RGB | Usage |
|------|-----------|-----|-------|
| **Red (Primary)** | `#ea3857` | `rgb(234, 56, 87)` | Primary CTA, active states, errors, critical actions |
| **Green (Success)** | `#13b981` | `rgb(19, 185, 129)` | Success states, completed tasks, positive metrics |
| **Yellow (Warning)** | `#f59e0b` | `rgb(245, 158, 11)` | Warnings, processing states, attention needed |
| **Purple (Info)** | `#a855f7` | `rgb(168, 85, 247)` | Informational badges, documents, neutral states |

### 1.5 Border Colors

| Theme | HEX Value | Usage |
|-------|-----------|-------|
| **Light Mode** | `#d1d5db` | Card borders, dividers, input borders |
| **Dark Mode** | `rgba(255, 255, 255, 0.1)` | Translucent white borders (glassmorphism effect) |

### 1.6 Stats Card Icon Backgrounds

Icon backgrounds use accent colors with 10% opacity:

| Color | Base HEX | Background with 10% Opacity | Usage |
|-------|----------|------------------------------|-------|
| **Red** | `#ea3857` | `rgba(234, 56, 87, 0.1)` | Revenue, critical metrics icons |
| **Green** | `#13b981` | `rgba(19, 185, 129, 0.1)` | Shipments, success metrics icons |
| **Yellow** | `#f59e0b` | `rgba(245, 158, 11, 0.1)` | Pending tasks, processing icons |
| **Purple** | `#a855f7` | `rgba(168, 85, 247, 0.1)` | Documents, informational icons |

---

## 2. Typography System

### 2.1 Font Families

| Token | Font Stack | Usage |
|-------|------------|-------|
| **Sans (UI)** | `Inter, system-ui, -apple-system, sans-serif` | All UI text, headings, body content |
| **Mono (Data)** | `"JetBrains Mono", "Courier New", monospace` | IDs, codes, numbers, technical data |

### 2.2 Type Scale

| Token | Size (px) | Size (rem) | Usage |
|-------|-----------|------------|-------|
| **xs** | 12px | 0.75rem | Small labels, badges, metadata |
| **sm** | 14px | 0.875rem | Body text, secondary content |
| **base** | 16px | 1rem | Default body text |
| **lg** | 18px | 1.125rem | Subheadings, prominent text |
| **xl** | 20px | 1.25rem | Card titles, section headers |
| **2xl** | 24px | 1.5rem | **Stats values, large numbers** |
| **3xl** | 30px | 1.875rem | Page titles, hero text |
| **4xl** | 36px | 2.25rem | Main dashboard headings |

### 2.3 Font Weights

| Token | Value | Usage |
|-------|-------|-------|
| **Normal** | 400 | Body text, paragraphs |
| **Medium** | 500 | UI elements, buttons, navigation |
| **Semibold** | 600 | Headings, card titles |
| **Bold** | 700 | Stats values, emphasis, important text |

### 2.4 Line Heights

| Token | Value | Usage |
|-------|-------|-------|
| **Tight** | 1.25 | Headings, stats values |
| **Normal** | 1.5 | Default body text |
| **Relaxed** | 1.75 | Long-form content, descriptions |

---

## 3. Spacing System

Based on **4px base unit** for consistent rhythm.

| Token | px | rem | Usage |
|-------|-----|-----|-------|
| **xs** | 4px | 0.25rem | Tight spacing, badges |
| **sm** | 8px | 0.5rem | Small gaps, icon spacing |
| **md** | 12px | 0.75rem | Standard gaps, form fields |
| **base** | 16px | 1rem | Default spacing, padding |
| **lg** | 24px | 1.5rem | **Card padding (standard)** |
| **xl** | 32px | 2rem | Section spacing, page margins |
| **2xl** | 48px | 3rem | Large section gaps |
| **3xl** | 64px | 4rem | Hero sections, page separators |

---

## 4. Border Radius

| Token | px | Tailwind Class | Usage |
|-------|-----|----------------|-------|
| **sm** | 6px | `rounded-sm` | Inputs, small buttons, badges |
| **md** | 12px | `rounded-md` | Buttons, dropdowns, tabs |
| **lg** | 16px | `rounded-lg` | Small cards, panels |
| **xl** | 12px | `rounded-xl` | ⚠️ Tailwind default (not 24px) |
| **2xl** | 16px | `rounded-2xl` | **STANDARD FOR CARDS** (default) |
| **3xl** | 24px | `rounded-3xl` | Large hero cards, modals |
| **full** | 9999px | `rounded-full` | Circles, pills, avatar badges |

**⚠️ Important:** Tailwind CSS default border radius values differ from custom design tokens. The standard card border radius is `rounded-2xl` (**16px**), not 24px. If you need 24px radius, use `rounded-3xl` or define custom values in `tailwind.config.ts`.

---

## 5. Layout Dimensions

### 5.1 Sidebar

| State | Width | Tailwind Class | Usage |
|-------|-------|----------------|-------|
| **Expanded** | 264px | `w-[264px]` | Full navigation with labels |
| **Collapsed** | 80px | `w-20` | Icons only |

### 5.2 Header

| Element | Height | Tailwind Class |
|---------|--------|----------------|
| **Header Bar** | 64px | `h-16` |

### 5.3 Content Padding

| Element | Padding | Tailwind Class |
|---------|---------|----------------|
| **Main Content Area** | 32px | `p-8` |
| **Card Internal Padding** | 24px | `p-6` |

---

## 6. Shadows

### 6.1 Light Theme Shadows

| Token | CSS Value | Usage |
|-------|-----------|-------|
| **sm** | `0 1px 2px rgba(0, 0, 0, 0.05)` | Subtle elevation (cards, inputs) |
| **DEFAULT** | `0 1px 3px rgba(0, 0, 0, 0.1), 0 1px 2px rgba(0, 0, 0, 0.06)` | Standard cards |
| **md** | `0 4px 6px rgba(0, 0, 0, 0.07), 0 2px 4px rgba(0, 0, 0, 0.05)` | Hover states, dropdowns |

### 6.2 Dark Theme Shadows

Dark theme uses **minimal shadows** to preserve glassmorphism aesthetic.

| Token | CSS Value | Usage |
|-------|-----------|-------|
| **Subtle** | `0 2px 8px rgba(0, 0, 0, 0.3)` | Cards, modals |

---

## 7. Hybrid Theme Architecture

**Critical Design Decision:** The application uses a **hybrid theme system**.

### 7.1 Theme Zones

| Zone | Theme Behavior | Background Color |
|------|----------------|------------------|
| **Sidebar** | **ALWAYS DARK** (never changes) | `#232328` |
| **Content Area** | Toggles Light/Dark | `#f4f4f4` (Light) / `#1a1a1e` (Dark) |
| **Header** | Follows Content Area theme | `#ffffff` (Light) / `#232328` (Dark) |

### 7.2 Theme Toggle Button

Located in the **Header Bar** (top right).

- **Light Mode Icon:** Moon (🌙)
- **Dark Mode Icon:** Sun (☀️)

---

## 8. Animation Policy

### 8.1 Instant Transitions (No Animation)

These elements **MUST transition instantly** without animation:

| Element | Duration | Rule |
|---------|----------|------|
| **Theme Toggle** | `0ms` | `transition: none` |
| **Sidebar Expand/Collapse** | `0ms` | `transition: none` |

**Rationale:** Provides immediate visual feedback, similar to VS Code and modern IDEs.

### 8.2 Fast Transitions (Micro-Interactions)

| Element | Duration | Timing Function |
|---------|----------|-----------------|
| **Button Hover** | `200ms` | `ease-out` |
| **Table Row Hover** | `150ms` | `ease-out` |
| **Input Focus** | `150ms` | `ease-out` |
| **Dropdown Open** | `200ms` | `ease-out` |

**Maximum Duration:** 200ms for any hover/focus effect.

---

## 9. Status Color Mapping

Consistent status colors across all components.

| Status | Color Name | HEX Value | Usage |
|--------|-----------|-----------|-------|
| **Completed / Success** | Green | `#13b981` | Completed shipments, successful operations |
| **Processing / Warning** | Yellow | `#f59e0b` | In-transit, pending approval, processing |
| **Error / Failed** | Red | `#ea3857` | Failed operations, errors, critical alerts |
| **Pending / Inactive** | Gray | `#9ca3af` | Inactive, draft, pending start |
| **Info / Documents** | Purple | `#a855f7` | Informational badges, document types |

---

## 10. Component Patterns

### 10.1 Stats Cards

**Structure:**

```
┌─────────────────────────────────────┐
│ [Icon] Revenue                      │
│ $128,459   +12.5%                   │
└─────────────────────────────────────┘
```

**Specifications:**

- **Icon Background:** Accent color at 10% opacity (see §1.6)
- **Value:** `text-2xl font-mono font-bold` (24px, monospace, bold)
- **Label:** `text-sm font-medium` (14px, medium weight)
- **Change Badge:** Small pill with green/red background

### 10.2 Data Tables

**Specifications:**

- **Header Background:** 
  - Light: `#f9fafb`
  - Dark: `rgba(255, 255, 255, 0.05)`
- **Row Hover:**
  - Light: `#f9fafb`
  - Dark: `rgba(255, 255, 255, 0.05)`
- **Border:**
  - Light: `#d1d5db`
  - Dark: `rgba(255, 255, 255, 0.1)`

### 10.3 Status Badges

**Specifications:**

- **Border Radius:** `rounded-full` (pill shape)
- **Padding:** `px-2.5 py-1` (10px horizontal, 4px vertical)
- **Font:** `text-xs font-medium` (12px, medium weight)
- **Colors:** Follow Status Color Mapping (§9)

### 10.4 Navigation (Sidebar)

**Active State:**

- **Border:** Left border, 2px, accent red (`#ea3857`)
- **Background:** Slightly lighter than sidebar (`#2a2a30`)
- **Text Color:** Accent red (`#ea3857`)

**Inactive State (Collapsed):**

- **Border:** `border border-white/10` (translucent white)
- **Background:** Transparent
- **Text Color:** Secondary text color

**Hover State:**

- **Border:** `hover:border-accent-red/50` (50% opacity red)
- **Background:** `hover:bg-medium-gray/80`
- **Text Color:** `hover:text-accent-red`

---

## 11. Accessibility Guidelines

### 11.1 Contrast Ratios

All text must meet **WCAG 2.1 AA** standards:

| Text Size | Minimum Contrast Ratio |
|-----------|------------------------|
| **Normal Text** (<18px) | 4.5:1 |
| **Large Text** (≥18px or ≥14px bold) | 3:1 |

### 11.2 Color Contrast Verification

| Combination | Light Mode | Dark Mode | Contrast Ratio |
|-------------|------------|-----------|----------------|
| Primary Text / Page BG | `#111827` / `#f4f4f4` | `#ffffff` / `#1a1a1e` | ✅ >7:1 |
| Secondary Text / Page BG | `#6b7280` / `#f4f4f4` | `#9ca3af` / `#1a1a1e` | ✅ >4.5:1 |
| Accent Red / Page BG | `#ea3857` / `#f4f4f4` | `#ea3857` / `#1a1a1e` | ✅ >4.5:1 |

### 11.3 Focus States

All interactive elements must have visible focus indicators:

- **Outline:** `ring-2 ring-accent-red ring-offset-2`
- **Offset Color:** Matches background (light: white, dark: `#1a1a1e`)

### 11.4 Keyboard Navigation

- **Tab Order:** Logical, follows visual hierarchy
- **Skip Links:** Provide "Skip to main content" for screen readers
- **Escape Key:** Closes modals and dropdowns

### 11.5 ARIA Labels

All icons and interactive elements without visible text must have:

- `aria-label` attribute describing the action
- Example: `<button aria-label="Toggle theme">🌙</button>`

---

## Appendix: Design Tokens Summary

### Quick Reference Table

| Category | Token Example | Value | Section |
|----------|---------------|-------|---------|
| **Color** | Page BG (Dark) | `#1a1a1d` | §1.1 |
| **Color** | Sidebar BG | `#232328` | §1.2 |
| **Color** | Accent Red | `#ea3857` | §1.4 |
| **Typography** | Sans Font | Inter | §2.1 |
| **Typography** | Mono Font | JetBrains Mono | §2.1 |
| **Typography** | Stats Value | 24px / 2xl | §2.2 |
| **Spacing** | Card Padding | 24px / lg | §3 |
| **Radius** | Card Standard | 16px / 2xl | §4 |
| **Layout** | Sidebar Expanded | 264px | §5.1 |
| **Animation** | Theme Toggle | 0ms (instant) | §8.1 |
| **Status** | Success | Green `#13b981` | §9 |

---

## Version History

| Version | Date | Changes |
|---------|------|---------|
| **3.0** | 2025-11-25 | Complete rewrite with HEX colors from `/test-app` audit |
| **2.0** | 2025-10-15 | Added hybrid theme architecture, glassmorphism specs |
| **1.0** | 2025-08-01 | Initial design system documentation |

---

## 12. Tailwind CSS Mapping

This section maps design tokens to their exact Tailwind CSS classes for clarity.

### 12.1 Color Classes

| Design Token | HEX | Tailwind Class (Light) | Tailwind Class (Dark) |
|--------------|-----|------------------------|-----------------------|
| Page Background | `#f4f4f4` / `#1a1a1d` | `bg-[#f4f4f4]` | `bg-[#1a1a1d]` |
| Card Background | `#ffffff` / `#232328` | `bg-white` | `bg-[#232328]` |
| Primary Text | `#111827` / `#ffffff` | `text-gray-900` | `text-white` |
| Secondary Text | `#6b7280` / `#9ca3af` | `text-gray-500` | `text-gray-400` |
| Accent Red | `#ea3857` | `text-[#ea3857]` / `bg-[#ea3857]` | Same |
| Accent Green | `#13b981` | `text-[#13b981]` / `bg-[#13b981]` | Same |
| Accent Yellow | `#f59e0b` | `text-[#f59e0b]` / `bg-[#f59e0b]` | Same |
| Accent Purple | `#a855f7` | `text-[#a855f7]` / `bg-[#a855f7]` | Same |

**Note:** Use CSS variables from `index.css` (`--accent-red`, `--dark-gray`, etc.) when possible for better theme consistency.

**HSL to HEX Reference:**
- `--dark-gray: 240 6% 11%` = `#1a1a1d`
- `--medium-gray: 240 7% 15%` = `#232328`

### 12.2 Typography Classes

| Design Token | Tailwind Class | Usage |
|--------------|----------------|-------|
| Sans Font | `font-sans` | All UI text |
| Mono Font | `font-mono` | IDs, numbers, technical data |
| Text xs | `text-xs` | 12px, badges, labels |
| Text sm | `text-sm` | 14px, body text |
| Text base | `text-base` | 16px, default |
| Text lg | `text-lg` | 18px, subheadings |
| Text xl | `text-xl` | 20px, card titles |
| Text 2xl | `text-2xl` | 24px, stats values |
| Text 3xl | `text-3xl` | 30px, page titles |
| Font Normal | `font-normal` | 400 weight |
| Font Medium | `font-medium` | 500 weight |
| Font Semibold | `font-semibold` | 600 weight |
| Font Bold | `font-bold` | 700 weight |

### 12.3 Spacing Classes

| Design Token | Tailwind Class | px Value |
|--------------|----------------|----------|
| xs | `p-1` / `m-1` | 4px |
| sm | `p-2` / `m-2` | 8px |
| md | `p-3` / `m-3` | 12px |
| base | `p-4` / `m-4` | 16px |
| lg | `p-6` / `m-6` | 24px |
| xl | `p-8` / `m-8` | 32px |
| 2xl | `p-12` / `m-12` | 48px |
| 3xl | `p-16` / `m-16` | 64px |

### 12.4 Border Radius Classes

| Design Token | Tailwind Class | px Value |
|--------------|----------------|----------|
| sm | `rounded-sm` | 6px |
| md | `rounded-md` | 12px |
| lg | `rounded-lg` | 16px |
| xl | `rounded-xl` | 12px ⚠️ |
| 2xl | `rounded-2xl` | **16px** (standard for cards) |
| 3xl | `rounded-3xl` | 24px |
| full | `rounded-full` | 9999px |

**⚠️ Critical:** Default Tailwind `rounded-xl` is **12px**, NOT 24px. Use `rounded-2xl` (16px) for standard cards.

### 12.5 Layout Classes

| Design Token | Tailwind Class | Value |
|--------------|----------------|-------|
| Sidebar Expanded | `w-[264px]` | 264px |
| Sidebar Collapsed | `w-20` | 80px |
| Header Height | `h-16` | 64px |
| Content Padding | `p-8` | 32px |
| Card Padding | `p-6` | 24px |

### 12.6 Animation Classes

| Design Token | Tailwind Class | Duration |
|--------------|----------------|----------|
| No Animation | `transition-none` | 0ms (instant) |
| Fast Transition | `transition-colors duration-200` | 200ms |
| Hover Effects | `transition-all duration-150` | 150ms |

---

**End of Design System Documentation**
